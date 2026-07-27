"""Tests de supresión, detección de totales y reconciliación."""

import pandas as pd
import pytest

from obsm.errors import ReconciliationError, SuppressionViolationError
from obsm.quality import (
    detectar_filas_total,
    suprimir_celdas_pequenas,
    validar_cobertura_territorial,
    validar_sin_duplicados,
    verificar_politica_publicacion,
    verificar_reconciliacion,
)


class TestFilasTotal:
    def test_detecta_variantes(self):
        df = pd.DataFrame({"comuna": ["Santiago", "TOTAL PAIS", "Total País", "subtotal", "Total"]})
        marca = detectar_filas_total(df)
        assert marca.tolist() == [False, True, True, True, True]

    def test_no_marca_nombres_legitimos(self):
        df = pd.DataFrame({"comuna": ["Totoral", "Talca", "Pais Vasco S.A."]})
        assert not detectar_filas_total(df).any()


class TestSupresion:
    def test_suprime_bajo_el_umbral_y_conserva_el_cero(self):
        df = pd.DataFrame({"comuna_cut": list("abcd"), "casos": [0, 3, 9, 25]})
        out, rep = suprimir_celdas_pequenas(df, "casos", k=10)
        assert out.loc[0, "casos"] == 0          # el cero informa y no identifica
        assert pd.isna(out.loc[1, "casos"])
        assert pd.isna(out.loc[2, "casos"])
        assert out.loc[3, "casos"] == 25
        assert rep.filas_suprimidas == 2

    def test_no_muta_la_entrada(self):
        df = pd.DataFrame({"casos": [1, 2, 100]})
        original = df.copy()
        suprimir_celdas_pequenas(df, "casos", k=10)
        pd.testing.assert_frame_equal(df, original)

    def test_supresion_complementaria(self):
        """Con una sola celda suprimida en el grupo, el valor es reconstruible por resta."""
        df = pd.DataFrame(
            {"anio": [2022] * 3, "comuna_cut": list("abc"), "casos": [4, 30, 50]}
        )
        out, rep = suprimir_celdas_pequenas(df, "casos", k=10, grupo=["anio"])
        assert rep.filas_suprimidas == 2
        assert rep.filas_suprimidas_complementarias == 1
        assert pd.isna(out.loc[0, "casos"])   # la original
        assert pd.isna(out.loc[1, "casos"])   # la complementaria (la menor de las restantes)
        assert out.loc[2, "casos"] == 50

    def test_sin_complementaria_cuando_ya_hay_dos(self):
        df = pd.DataFrame({"anio": [2022] * 3, "casos": [4, 5, 50]})
        out, rep = suprimir_celdas_pequenas(df, "casos", k=10, grupo=["anio"])
        assert rep.filas_suprimidas == 2
        assert rep.filas_suprimidas_complementarias == 0
        assert out.loc[2, "casos"] == 50


class TestPoliticaPublicacion:
    def test_rechaza_dimension_prohibida(self):
        df = pd.DataFrame({"comuna_cut": ["13101"], "metodo_suicidio": ["x"], "casos": [10]})
        with pytest.raises(SuppressionViolationError):
            verificar_politica_publicacion(df)

    def test_rechaza_desglose_por_codigo_en_suicidio(self):
        df = pd.DataFrame({"causa_cie10": ["X700", "X610"], "casos": [10, 12]})
        with pytest.raises(SuppressionViolationError):
            verificar_politica_publicacion(df, agrupador_id="SUICIDIO")

    def test_acepta_tabla_agregada(self):
        df = pd.DataFrame({"comuna_cut": ["13101"], "casos": [10]})
        verificar_politica_publicacion(df, agrupador_id="SUICIDIO")


class TestReconciliacion:
    def test_pasa_dentro_de_tolerancia(self):
        assert verificar_reconciliacion(1000, 1002, 0.005) < 0.005

    def test_falla_fuera_de_tolerancia(self):
        with pytest.raises(ReconciliationError):
            verificar_reconciliacion(1000, 1100, 0.005, etiqueta="defunciones 2022")

    def test_ancla_en_cero_es_error(self):
        with pytest.raises(ReconciliationError):
            verificar_reconciliacion(10, 0)


class TestValidaciones:
    def test_duplicados(self):
        df = pd.DataFrame({"comuna_cut": ["13101", "13101"], "anio": [2022, 2022]})
        with pytest.raises(ValueError):
            validar_sin_duplicados(df, ["comuna_cut", "anio"])

    def test_cobertura_territorial(self):
        df = pd.DataFrame({"comuna_cut": ["13101", "05101"]})
        rep = validar_cobertura_territorial(df, "comuna_cut", n_esperado=346)
        assert rep["alerta"] is True
        assert rep["comunas_presentes"] == 2
