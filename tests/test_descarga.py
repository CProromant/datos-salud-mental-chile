"""Tests de la descarga y del orquestador de un solo comando.

Ninguno toca la red: se prueba la lógica alrededor de la descarga —verificación de hash,
extracción del ZIP, caché— que es donde están los errores que importan. Que `requests`
funcione es problema de `requests`.
"""

import zipfile

import pytest

from obsm.cli import _asegurar_raw
from obsm.errors import ObsmError, SourceUnavailableError
from obsm.io import USER_AGENT_NAVEGADOR, descargar, sha256_archivo
from obsm.registry import Fuente


class TestUserAgent:
    def test_el_agente_por_defecto_parece_un_navegador(self):
        """No es cosmético: los servidores reales devuelven 403 sin esto.

        `repositoriodeis.minsal.cl` y SUBDERE rechazan cualquier agente que no parezca
        un navegador. Con el user-agent honesto `obsm/x.y` la descarga no es lenta ni
        parcial: es imposible.
        """
        assert "Mozilla" in USER_AGENT_NAVEGADOR
        import inspect

        firma = inspect.signature(descargar)
        assert firma.parameters["user_agent"].default == USER_AGENT_NAVEGADOR


class TestVerificacionDeHash:
    """Una descarga que completó no es una descarga correcta."""

    def test_acepta_el_archivo_cuando_el_hash_coincide(self, tmp_path, monkeypatch):
        destino = tmp_path / "dato.csv"
        destino.write_bytes(b"a;b\n1;2\n")
        esperado = sha256_archivo(destino)
        # El archivo ya existe, así que `descargar` no toca la red.
        m = descargar("https://ejemplo.cl/dato.csv", destino, "demo", sha256_esperado=esperado)
        assert m.sha256 == esperado

    def test_rechaza_el_archivo_cuando_el_hash_no_coincide(self, tmp_path):
        destino = tmp_path / "dato.csv"
        destino.write_bytes(b"contenido distinto")
        with pytest.raises(SourceUnavailableError, match="hash declarado"):
            descargar("https://ejemplo.cl/dato.csv", destino, "demo", sha256_esperado="0" * 64)

    def test_el_error_explica_las_tres_causas_posibles(self, tmp_path):
        # Quien lo lea tiene que poder decidir qué hacer: reintentar, revisar la URL, o
        # verificar el contenido nuevo y actualizar el catálogo a mano.
        destino = tmp_path / "dato.csv"
        destino.write_bytes(b"x")
        with pytest.raises(SourceUnavailableError) as exc:
            descargar("https://ejemplo.cl/x", destino, "demo", sha256_esperado="0" * 64)
        texto = str(exc.value)
        assert "corrupta" in texto and "200" in texto and "republic" in texto

    def test_sin_hash_declarado_no_verifica_nada(self, tmp_path):
        # El catálogo puede no tener hash todavía; eso no debe impedir descargar.
        destino = tmp_path / "dato.csv"
        destino.write_bytes(b"x")
        assert descargar("https://ejemplo.cl/x", destino, "demo").sha256 == sha256_archivo(destino)


class TestAsegurarRaw:
    """Obtener el archivo crudo: caché, ZIP y validación del miembro extraído."""

    def _fuente(self, tmp_path, **extra):
        return Fuente(
            id="demo",
            nombre="Demo",
            estado="verificada",
            fecha_verificacion="2026-01-01",
            url_archivo="https://ejemplo.cl/datos.zip",
            extra=extra,
        )

    def _preparar_zip(self, dir_raw, nombre_csv, contenido=b"a;b\n1;2\n"):
        dir_raw.mkdir(parents=True, exist_ok=True)
        z = dir_raw / "datos.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr(nombre_csv, contenido)
        return z

    def test_extrae_el_miembro_declarado(self, tmp_path, monkeypatch):
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        self._preparar_zip(tmp_path / "raw" / "demo", "dato.csv")
        ruta = _asegurar_raw(self._fuente(tmp_path, archivo_extraido="dato.csv"))
        assert ruta.name == "dato.csv"
        assert ruta.read_bytes() == b"a;b\n1;2\n"

    def test_reutiliza_el_extraido_sin_volver_a_descomprimir(self, tmp_path, monkeypatch):
        # Es la diferencia entre 20 minutos y 20 segundos al reintentar el pipeline.
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        dir_raw = tmp_path / "raw" / "demo"
        dir_raw.mkdir(parents=True)
        (dir_raw / "dato.csv").write_bytes(b"ya estaba")
        ruta = _asegurar_raw(self._fuente(tmp_path, archivo_extraido="dato.csv"))
        assert ruta.read_bytes() == b"ya estaba"

    def test_falla_si_el_zip_no_trae_el_miembro_declarado(self, tmp_path, monkeypatch):
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        self._preparar_zip(tmp_path / "raw" / "demo", "otro_nombre.csv")
        with pytest.raises(ObsmError, match="no contiene"):
            _asegurar_raw(self._fuente(tmp_path, archivo_extraido="dato.csv"))

    def test_falla_si_es_zip_y_el_catalogo_no_dice_que_extraer(self, tmp_path, monkeypatch):
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        self._preparar_zip(tmp_path / "raw" / "demo", "dato.csv")
        with pytest.raises(ObsmError, match="archivo_extraido"):
            _asegurar_raw(self._fuente(tmp_path))

    def test_valida_el_hash_del_miembro_extraido(self, tmp_path, monkeypatch):
        # El ZIP puede tener el hash correcto y aun así traer otro contenido dentro si
        # el organismo lo republicó. Se validan las dos puntas.
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        self._preparar_zip(tmp_path / "raw" / "demo", "dato.csv")
        with pytest.raises(ObsmError, match="sha256_extraido"):
            _asegurar_raw(
                self._fuente(tmp_path, archivo_extraido="dato.csv", sha256_extraido="0" * 64)
            )

    def test_un_archivo_que_no_es_zip_se_devuelve_tal_cual(self, tmp_path, monkeypatch):
        monkeypatch.setattr("obsm.io.DIR_DATOS", tmp_path)
        dir_raw = tmp_path / "raw" / "demo"
        dir_raw.mkdir(parents=True)
        (dir_raw / "datos.zip").write_bytes(b"esto no es un zip")
        ruta = _asegurar_raw(self._fuente(tmp_path))
        assert ruta.read_bytes() == b"esto no es un zip"


class TestOrdenDelPipeline:
    def test_el_denominador_va_antes_que_el_numerador(self):
        """`build gold` necesita la población, y la ingesta del numerador tarda once
        minutos: fallar temprano cuesta menos."""
        from obsm.cli import PIPELINE_FASE_1

        assert PIPELINE_FASE_1.index("ine_proyecciones") < PIPELINE_FASE_1.index("deis_defunciones")
