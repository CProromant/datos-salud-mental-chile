"""Tests de lectura robusta: encoding, separador y números en formato chileno."""

import math
from pathlib import Path

import pytest

from obsm.io import (
    Manifiesto,
    a_numero,
    detectar_encoding,
    detectar_separador,
    leer_primera_linea,
    leer_texto,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestNumeros:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("1.234,5", 1234.5),  # formato chileno
            ("1,234.5", 1234.5),  # formato anglosajón
            ("1234.5", 1234.5),
            ("12,7%", 12.7),
            ("  42 ", 42.0),
            ("$ 1.500", 1500.0),  # punto de miles chileno
            ("1.234.567", 1234567.0),  # varios puntos: inequívocamente miles
            ("-1.500", -1500.0),
            ("1,5", 1.5),
            ("0.005", 0.005),  # la excepción: parte entera 0 -> proporción
            ("12.75", 12.75),
            (7, 7.0),
            (3.5, 3.5),
        ],
    )
    def test_conversion(self, entrada, esperado):
        assert a_numero(entrada) == pytest.approx(esperado)

    @pytest.mark.parametrize("entrada", ["", None, "-", "s/i", "n/a"])
    def test_basura_da_nan_sin_lanzar(self, entrada):
        assert math.isnan(a_numero(entrada))

    def test_ambiguedad_documentada(self):
        """La regla del punto de miles tiene un costo conocido: una proporción
        escrita '1.000' se lee como mil. Se documenta y se exige `decimal` explícito
        para columnas de tasas."""
        assert a_numero("1.000") == 1000.0
        assert a_numero("1.000", decimal=".") == 1.0

    def test_decimal_forzado(self):
        assert a_numero("1,234", decimal=",") == pytest.approx(1.234)
        assert a_numero("1,234", decimal=".") == pytest.approx(1234.0)


class TestSeparador:
    def test_punto_y_coma(self):
        assert detectar_separador("a;b;c;d") == ";"

    def test_coma(self):
        assert detectar_separador("a,b,c,d") == ","

    def test_ignora_separadores_dentro_de_comillas(self):
        assert detectar_separador('"Santiago, Chile";b;c') == ";"


class TestEncoding:
    def test_detecta_latin1(self):
        enc = detectar_encoding(FIXTURES / "deis_defunciones" / "muestra_latin1.csv")
        assert enc in {"cp1252", "latin-1"}

    def test_detecta_utf8(self):
        assert detectar_encoding(FIXTURES / "deis_defunciones" / "muestra_utf8.csv") in {
            "utf-8",
            "utf-8-sig",
        }

    def test_ambos_archivos_dan_el_mismo_texto(self):
        """El punto de detectar encoding: que 'Valparaíso' sea la misma comuna
        venga como venga el archivo."""
        t1, _ = leer_texto(FIXTURES / "deis_defunciones" / "muestra_latin1.csv")
        t2, _ = leer_texto(FIXTURES / "deis_defunciones" / "muestra_utf8.csv")
        assert "Valparaíso" in t1
        assert t1 == t2


class TestManifiesto:
    def test_escribe_json_legible(self, tmp_path):
        m = Manifiesto(
            source_id="x",
            url="https://ejemplo.cl",
            fecha_extraccion="2026-07-26T00:00:00+00:00",
            sha256="abc",
            bytes=10,
            encoding="utf-8",
        )
        destino = m.escribir(tmp_path / "m.json")
        contenido = destino.read_text(encoding="utf-8")
        assert '"source_id": "x"' in contenido
        assert '"pipeline_version"' in contenido


class TestLeerPrimeraLinea:
    """Se agregó para no cargar 869 MB en RAM y leer solo el encabezado.

    Estaba sin tests, que es exactamente como una optimización de memoria se convierte
    en un bug de encoding: la función decide sola con qué encoding abrir el archivo.
    """

    def test_devuelve_encabezado_y_encoding_en_latin1(self, tmp_path):
        f = tmp_path / "latin1.csv"
        f.write_bytes("AÑO;COMUNA;DIAG2\n2020;Ñuñoa;X700\n".encode("latin-1"))
        linea, enc = leer_primera_linea(f)
        assert linea == "AÑO;COMUNA;DIAG2"
        assert enc.lower().replace("_", "-") in {"latin-1", "iso-8859-1", "cp1252"}

    def test_devuelve_encabezado_y_encoding_en_utf8(self, tmp_path):
        f = tmp_path / "utf8.csv"
        f.write_bytes("AÑO;COMUNA\n2020;Ñuñoa\n".encode())
        linea, enc = leer_primera_linea(f)
        assert linea == "AÑO;COMUNA"
        # utf-8-sig es la respuesta correcta aunque no haya BOM: ese códec lo quita si
        # está y decodifica utf-8 plano si no. Por eso encabeza ENCODINGS_CANDIDATOS.
        assert enc.lower().replace("_", "-") in {"utf-8", "utf8", "utf-8-sig"}

    def test_no_deja_el_retorno_de_carro_de_windows(self, tmp_path):
        f = tmp_path / "crlf.csv"
        f.write_bytes(b"a;b;c\r\n1;2;3\r\n")
        linea, _ = leer_primera_linea(f)
        assert linea == "a;b;c"  # un \r pegado rompe el nombre de la última columna

    def test_no_lee_el_resto_del_archivo(self, tmp_path):
        f = tmp_path / "grande.csv"
        with f.open("w", encoding="utf-8") as fh:
            fh.write("a;b\n")
            for i in range(200_000):
                fh.write(f"{i};{i}\n")
        linea, _ = leer_primera_linea(f)
        assert linea == "a;b"

    def test_archivo_de_una_sola_linea_sin_salto_final(self, tmp_path):
        f = tmp_path / "sola.csv"
        f.write_bytes(b"a;b;c")
        linea, _ = leer_primera_linea(f)
        assert linea == "a;b;c"

    def test_el_encoding_devuelto_sirve_para_leer_el_archivo(self, tmp_path):
        # El contrato real: quien recibe `enc` lo usa para abrir el archivo completo.
        f = tmp_path / "mixto.csv"
        f.write_bytes("comuna;valor\nAysén;1\nÑuñoa;2\n".encode("latin-1"))
        linea, enc = leer_primera_linea(f)
        assert linea == "comuna;valor"
        assert "Aysén" in f.read_text(encoding=enc)


class TestElegirTabla:
    """A-014: elegir el silver por orden alfabético del nombre de archivo.

    Con dos copias del mismo contenido da igual —así se descubrió—. Con dos versiones
    distintas de una fuente mueve todas las tasas publicadas en silencio. El denominador
    es la dependencia más peligrosa del pipeline: un error suyo no produce una celda rara,
    desplaza todo a la vez y en la misma dirección.
    """

    @pytest.fixture()
    def almacen(self, tmp_path, monkeypatch):
        from obsm import io

        monkeypatch.setattr(io, "DIR_DATOS", tmp_path)
        return tmp_path / "silver" / "ine_proyecciones"

    def test_sin_archivos_devuelve_none(self, almacen):
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        assert elegir_tabla("silver", "ine_proyecciones") is None

    def test_con_uno_lo_devuelve(self, almacen):
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        (almacen / "base_2017.parquet").write_bytes(b"x")
        assert elegir_tabla("silver", "ine_proyecciones").name == "base_2017.parquet"

    def test_con_dos_lanza_en_vez_de_elegir(self, almacen):
        from obsm.errors import SchemaDriftError
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        # El orden alfabético elegiría base_2024, que es el que un `sorted()[-1]` habría
        # tomado por accidente. Que acierte por casualidad es peor que fallar.
        (almacen / "base_2017.parquet").write_bytes(b"x")
        (almacen / "base_2024.parquet").write_bytes(b"y")
        with pytest.raises(SchemaDriftError, match="base_2017"):
            elegir_tabla("silver", "ine_proyecciones")

    def test_el_mensaje_dice_como_resolverlo(self, almacen):
        from obsm.errors import SchemaDriftError
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        (almacen / "a.parquet").write_bytes(b"x")
        (almacen / "b.parquet").write_bytes(b"y")
        with pytest.raises(SchemaDriftError) as exc:
            elegir_tabla("silver", "ine_proyecciones")
        mensaje = str(exc.value)
        assert "borrar el archivo obsoleto" in mensaje
        assert "--poblacion" in mensaje

    def test_el_desempate_explicito_es_aceptable(self, almacen):
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        (almacen / "base_2017.parquet").write_bytes(b"x")
        (almacen / "base_2024.parquet").write_bytes(b"y")
        # Elegir a mano es aceptable; elegir por accidente, no.
        elegido = elegir_tabla("silver", "ine_proyecciones", preferido="base_2017.parquet")
        assert elegido.name == "base_2017.parquet"

    def test_un_preferido_inexistente_falla(self, almacen):
        from obsm.errors import SchemaDriftError
        from obsm.io import elegir_tabla

        almacen.mkdir(parents=True)
        with pytest.raises(SchemaDriftError, match="no existe"):
            elegir_tabla("silver", "ine_proyecciones", preferido="fantasma.parquet")
