"""Tests del lector parcial de ZIP remotos.

Ninguno toca la red: se inyecta un lector de rangos que sirve un archivo local. Lo que
se prueba es el manejo del formato ZIP —dónde está el índice, cómo se ubica un miembro,
qué pasa cuando algo no calza—, que es donde están los errores. Que HTTP funcione es
problema de HTTP.

Existe porque los ZIP del REM pesan 220 MB cada uno y solo interesa un diccionario de
medio mega. Para revisar 17 años, la diferencia es de 4 GB a 8 MB.
"""

import zipfile

import pytest

from obsm.errors import SourceUnavailableError
from obsm.io import extraer_de_zip_remoto, listar_zip_remoto


def _lector_local(ruta):
    """Simula peticiones de rango HTTP sobre un archivo del disco."""
    datos = ruta.read_bytes()

    def leer(_url, desde, hasta):
        if desde < 0:  # sintaxis de cola: los últimos N bytes
            return datos[desde:]
        return datos[desde : hasta + 1]

    return leer


@pytest.fixture()
def zip_demo(tmp_path):
    z = tmp_path / "demo.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        f.writestr("Datos/grande.txt", b"x" * 500_000)
        f.writestr("Diccionarios/dicc.xlsx", b"contenido del diccionario")
        f.writestr("sin_comprimir.txt", b"y" * 10, zipfile.ZIP_STORED)
    return z


class TestListar:
    def test_lista_los_miembros_sin_leer_el_archivo_entero(self, zip_demo):
        miembros = listar_zip_remoto("http://ejemplo/demo.zip", leer_rango=_lector_local(zip_demo))
        nombres = [m.nombre for m in miembros]
        assert nombres == ["Datos/grande.txt", "Diccionarios/dicc.xlsx", "sin_comprimir.txt"]

    def test_reporta_tamanos_comprimido_y_real(self, zip_demo):
        miembros = {
            m.nombre: m
            for m in listar_zip_remoto(
                "http://ejemplo/demo.zip", leer_rango=_lector_local(zip_demo)
            )
        }
        grande = miembros["Datos/grande.txt"]
        assert grande.bytes_reales == 500_000
        # Medio mega de la misma letra comprime muchísimo: es lo que permite decidir
        # si vale la pena bajar un miembro antes de pedirlo.
        assert grande.bytes_comprimidos < 10_000

    def test_un_archivo_que_no_es_zip_falla_diciendo_por_que(self, tmp_path):
        malo = tmp_path / "no_es.zip"
        malo.write_bytes(b"esto es texto plano, no un zip")
        with pytest.raises(SourceUnavailableError, match="índice central"):
            listar_zip_remoto("http://ejemplo/no_es.zip", leer_rango=_lector_local(malo))


class TestExtraer:
    def test_extrae_un_miembro_comprimido(self, zip_demo):
        leer = _lector_local(zip_demo)
        miembros = {m.nombre: m for m in listar_zip_remoto("u", leer_rango=leer)}
        datos = extraer_de_zip_remoto("u", miembros["Diccionarios/dicc.xlsx"], leer_rango=leer)
        assert datos == b"contenido del diccionario"

    def test_extrae_un_miembro_sin_comprimir(self, zip_demo):
        # El método 0 (almacenado) no pasa por zlib. Si el lector asumiera que todo
        # viene comprimido, este caso reventaría.
        leer = _lector_local(zip_demo)
        miembros = {m.nombre: m for m in listar_zip_remoto("u", leer_rango=leer)}
        assert (
            extraer_de_zip_remoto("u", miembros["sin_comprimir.txt"], leer_rango=leer) == b"y" * 10
        )

    def test_extrae_solo_el_miembro_pedido_y_no_el_resto(self, zip_demo):
        """La razón de ser de todo esto: no bajar los 500 KB para leer 25 bytes."""
        leer = _lector_local(zip_demo)
        pedidos = []

        def leer_contando(url, desde, hasta):
            datos = leer(url, desde, hasta)
            pedidos.append(len(datos))
            return datos

        miembros = {m.nombre: m for m in listar_zip_remoto("u", leer_rango=leer_contando)}
        pedidos.clear()
        extraer_de_zip_remoto("u", miembros["Diccionarios/dicc.xlsx"], leer_rango=leer_contando)
        assert sum(pedidos) < 20_000, (
            f"se pidieron {sum(pedidos)} bytes para un miembro de 25: el lector está bajando de más"
        )

    def test_un_offset_que_no_apunta_a_un_miembro_falla(self, zip_demo):
        from obsm.io import MiembroZip

        leer = _lector_local(zip_demo)
        falso = MiembroZip("inventado.txt", offset=12_345, bytes_comprimidos=10, bytes_reales=10)
        with pytest.raises(SourceUnavailableError, match="encabezado"):
            extraer_de_zip_remoto("u", falso, leer_rango=leer)


class TestIntegridad:
    def test_lo_extraido_coincide_con_lo_que_daria_descargar_todo(self, zip_demo):
        """El control que importa: leer por partes no puede dar algo distinto."""
        leer = _lector_local(zip_demo)
        remotos = {
            m.nombre: extraer_de_zip_remoto("u", m, leer_rango=leer)
            for m in listar_zip_remoto("u", leer_rango=leer)
        }
        with zipfile.ZipFile(zip_demo) as z:
            locales = {n: z.read(n) for n in z.namelist()}
        assert remotos == locales


class TestNombresConAcento:
    """Los nombres de archivo pueden venir en CP437 o en UTF-8, y el ZIP lo declara.

    Se detectó contra el archivo real de DEIS: un miembro llamado
    `DICCIONARIO CÓDIGOS SBS_23-1.4.xlsx` se leía como `DICCIONARIO CαDIGOS...`
    porque el lector asumía CP437 siempre. Con el nombre mal decodificado, buscar el
    miembro por su nombre deja de funcionar — y en este repositorio todos los archivos
    de las fuentes están en español.
    """

    def test_conserva_los_acentos(self, tmp_path):
        z = tmp_path / "acentos.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("DICCIONARIO CÓDIGOS ÑUÑOA.xlsx", b"datos")
        nombres = [m.nombre for m in listar_zip_remoto("u", leer_rango=_lector_local(z))]
        assert nombres == ["DICCIONARIO CÓDIGOS ÑUÑOA.xlsx"]

    def test_el_miembro_se_puede_encontrar_y_extraer_por_su_nombre(self, tmp_path):
        z = tmp_path / "acentos.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("Diccionarios/CÓDIGOS.xlsx", b"contenido")
        leer = _lector_local(z)
        ms = {m.nombre: m for m in listar_zip_remoto("u", leer_rango=leer)}
        assert (
            extraer_de_zip_remoto("u", ms["Diccionarios/CÓDIGOS.xlsx"], leer_rango=leer)
            == b"contenido"
        )

    def test_un_nombre_en_cp850_se_lee_con_sus_tildes(self, tmp_path):
        """El caso real de DEIS, reproducido byte a byte.

        `zipfile` de Python escribe los nombres no-ASCII con la bandera UTF-8, así que
        no puede generar este caso: hay que armar el ZIP a mano con el nombre en CP850
        y la bandera apagada, que es exactamente lo que hace el Windows en español que
        produjo los archivos del REM.
        """
        import struct

        nombre = "CÓDIGOS.txt".encode("cp850")  # la Ó queda como 0xE0
        datos = b"contenido"
        local = (
            b"PK\x03\x04"
            + struct.pack("<HHHHHIIIHH", 20, 0, 0, 0, 0, 0, len(datos), len(datos), len(nombre), 0)
            + nombre
            + datos
        )
        cd = (
            b"PK\x01\x02"
            + struct.pack(
                "<HHHHHHIIIHHHHHII",
                20,
                20,
                0,
                0,
                0,
                0,
                0,
                len(datos),
                len(datos),
                len(nombre),
                0,
                0,
                0,
                0,
                0,
                0,
            )
            + nombre
        )
        eocd = b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, 1, 1, len(cd), len(local), 0)
        z = tmp_path / "cp850.zip"
        z.write_bytes(local + cd + eocd)

        ms = listar_zip_remoto("u", leer_rango=_lector_local(z))
        assert ms[0].nombre == "CÓDIGOS.txt", (
            f"se leyó {ms[0].nombre!r}: si sale 'CαDIGOS.txt' el lector volvió a CP437"
        )
