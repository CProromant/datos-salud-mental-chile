"""Tests de lectura robusta: encoding, separador y números en formato chileno."""

import math
from pathlib import Path

import pytest

from obsm.io import Manifiesto, a_numero, detectar_encoding, detectar_separador, leer_texto

FIXTURES = Path(__file__).parent / "fixtures"


class TestNumeros:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("1.234,5", 1234.5),      # formato chileno
            ("1,234.5", 1234.5),      # formato anglosajón
            ("1234.5", 1234.5),
            ("12,7%", 12.7),
            ("  42 ", 42.0),
            ("$ 1.500", 1500.0),       # punto de miles chileno
            ("1.234.567", 1234567.0),  # varios puntos: inequívocamente miles
            ("-1.500", -1500.0),
            ("1,5", 1.5),
            ("0.005", 0.005),          # la excepción: parte entera 0 -> proporción
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
            "utf-8", "utf-8-sig"
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
            source_id="x", url="https://ejemplo.cl", fecha_extraccion="2026-07-26T00:00:00+00:00",
            sha256="abc", bytes=10, encoding="utf-8",
        )
        destino = m.escribir(tmp_path / "m.json")
        contenido = destino.read_text(encoding="utf-8")
        assert '"source_id": "x"' in contenido
        assert '"pipeline_version"' in contenido
