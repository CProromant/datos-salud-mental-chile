"""Tests del camino bronze → silver → gold de egresos hospitalarios.

Esta fuente es la que cierra el tramo entre el control ambulatorio (REM) y la muerte
(DEIS). Tres cosas de acá pueden salir mal sin que nada falle, y cada una tiene su test:
que las filas sin territorio se cuelen como una comuna, que se ofrezca una estandarización
por edad que la fuente no permite, y que la serie de conducta suicida salga sin las
salvaguardas de `docs/06`.
"""

from pathlib import Path

import pytest

from obsm.errors import SuppressionViolationError
from obsm.ingest.deis_egresos import DeisEgresos
from obsm.transform.gold import (
    tabla_egresos_autoinfligida,
    tabla_egresos_salud_mental,
)
from obsm.transform.silver import normalizar_egresos

FIXTURE = Path(__file__).parent / "fixtures" / "deis_egresos" / "muestra_estructura_real_2023.csv"
RECURSOS = ["Salud Responde 600 360 7777", "*4141 Línea de prevención del suicidio"]


@pytest.fixture()
def bronze():
    return DeisEgresos().preparar(FIXTURE)


@pytest.fixture()
def silver(bronze):
    df, _ = normalizar_egresos(bronze)
    return df


@pytest.fixture()
def reporte(bronze):
    _, rep = normalizar_egresos(bronze)
    return rep


class TestSilver:
    def test_el_territorio_se_resuelve_por_codigo(self, silver):
        # El fixture trae Iquique (01101), Valparaíso ×2 (05101), Ñuñoa, Chillán,
        # Coyhaique, Concepción, más la suprimida y la de residencia ignorada.
        assert "01101" in set(silver["comuna_cut"])
        assert (silver["comuna_cut"] == "05101").sum() == 2

    def test_las_filas_sin_territorio_no_inventan_una_comuna(self, silver, reporte):
        """La suprimida y la ignorada van a COMUNA_DESCONOCIDA, no a una comuna real."""
        assert (silver["comuna_cut"] == "99999").sum() == 3
        assert reporte["sin_territorio_por_supresion"] == 1
        assert reporte["sin_territorio_por_residencia_ignorada"] == 1
        assert reporte["sin_territorio_total"] == 3

    def test_las_tres_causas_de_falta_de_territorio_se_cuentan_aparte(self, reporte):
        """Mezclarlas borra por qué el total comunal no suma el nacional.

        Y son **tres**, no dos: supresión de DEIS, residencia ignorada y residencia en el
        extranjero. La tercera apareció al correr el pipeline sobre el archivo real —661
        filas de 2023 que no encajaban en ninguna de las otras dos— y significa algo
        distinto: el egreso **sí** tiene residencia conocida, solo que fuera de Chile.
        """
        assert reporte["sin_territorio_por_supresion"] == 1
        assert reporte["sin_territorio_por_residencia_ignorada"] == 1
        assert reporte["sin_territorio_por_residencia_extranjero"] == 1
        assert (
            reporte["sin_territorio_por_supresion"]
            + reporte["sin_territorio_por_residencia_ignorada"]
            + reporte["sin_territorio_por_residencia_extranjero"]
            == reporte["sin_territorio_total"]
        )

    def test_no_queda_ninguna_fila_sin_territorio_sin_explicar(self, reporte):
        """Lo que no se explica es lo que hay que mirar: un centinela nuevo de la fuente.

        Con los tres conocidos declarados, el resto debe ser cero. Si deja de serlo, DEIS
        agregó un código que la DPA no reconoce y que se lo tragaría el balde de
        «comuna desconocida» sin que nadie lo note.
        """
        assert reporte["sin_territorio_sin_explicar"] == 0

    def test_el_extranjero_no_se_confunde_con_residencia_ignorada(self, silver):
        ext = silver[silver["residencia_extranjero"]]
        assert len(ext) == 1
        assert not ext["residencia_ignorada"].any()
        assert not ext["suprimido_en_origen"].any()
        assert ext["comuna_cut"].iloc[0] == "99999"  # sin territorio chileno al que ir

    def test_no_se_fabrica_un_grupo_etario_quinquenal(self, silver, reporte):
        """La fuente trae tramos, no edad exacta: inventar la grilla del INE haría creer
        que la tasa estandarizada es calculable.

        Y el tramo de la fuente **no se llama `grupo_edad`**: ese nombre, en el silver de
        defunciones, es la grilla quinquenal compatible con el denominador del INE.
        Compartirlo entre dos silvers con significados distintos es cómo alguien
        estandariza contra la grilla equivocada sin que nada falle.
        """
        assert reporte["edad_exacta_disponible"] is False
        assert "grupo_edad" not in silver.columns
        assert "grupo_edad_fuente" in silver.columns
        assert "grupo_edad_norm" in silver.columns
        assert "20 a 29" in set(silver["grupo_edad_fuente"])

    def test_el_reporte_declara_que_son_eventos_y_no_personas(self, reporte):
        assert "NO personas" in reporte["unidad"]

    def test_los_agrupadores_leen_la_causa_derivada(self, silver):
        """Un solo pase encuentra los F del diagnóstico y los X de la causa externa."""
        assert silver["es_trastornos_mentales"].sum() == 4
        assert silver["es_lesion_autoinfligida_morbilidad"].sum() == 2

    def test_las_marcas_del_ingestor_llegan_a_silver(self, reporte):
        assert reporte["filas_suprimidas_en_origen"] == 1
        assert reporte["filas_con_anio_imputado"] == 1


class TestGoldTrastornosMentales:
    def test_cuenta_egresos_por_comuna_y_anio(self, silver):
        # k=1 para que el fixture chico no quede íntegramente suprimido: lo que se prueba
        # acá es la agregación, y la supresión tiene sus propios tests en test_quality.
        tabla, meta = tabla_egresos_salud_mental(silver, k=1)
        assert set(tabla["anio"]) == {2023}
        # F200 en Iquique, F102 en Chillán, F332 en Valparaíso: uno por comuna.
        por_comuna = dict(zip(tabla["comuna_cut"], tabla["egresos"], strict=True))
        assert por_comuna["01101"] == 1
        assert por_comuna["16101"] == 1
        assert por_comuna["05101"] == 1
        assert meta["agrupador"] == "TRASTORNOS_MENTALES"

    def test_arrastra_procedencia_completa(self, silver):
        tabla, _ = tabla_egresos_salud_mental(silver, k=1)
        for col in ("source_id", "source_version", "pipeline_version", "fecha_calculo"):
            assert col in tabla.columns
        assert (tabla["source_id"] == "deis_egresos").all()

    def test_calcula_dias_de_estada(self, silver):
        tabla, _ = tabla_egresos_salud_mental(silver, k=1)
        iquique = tabla[tabla["comuna_cut"] == "01101"].iloc[0]
        assert iquique["dias_estada_total"] == 45  # el F200 del fixture
        assert iquique["dias_estada_mediana"] == 45

    def test_el_meta_advierte_que_no_se_cuadra_con_el_total_nacional(self, silver):
        _, meta = tabla_egresos_salud_mental(silver, k=1)
        junto = " ".join(meta["advertencias"])
        assert "NO SUMA EL NACIONAL" in junto
        assert "NO ES UNA PERSONA" in junto
        assert "ESTANDARIZACIÓN POR EDAD" in junto

    def test_el_meta_declara_los_egresos_sin_territorio(self, silver):
        _, meta = tabla_egresos_salud_mental(silver, k=1)
        assert meta["egresos_sin_territorio"] == 3


class TestGoldLesionAutoinfligida:
    """La serie más sensible del proyecto: mismas salvaguardas que I-05."""

    def test_sin_recursos_de_ayuda_no_produce_nada(self, silver):
        with pytest.raises(SuppressionViolationError, match="recursos_ayuda"):
            tabla_egresos_autoinfligida(silver, recursos_ayuda=[])

    def test_con_recursos_produce_la_tabla(self, silver):
        tabla, meta = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
        assert meta["recursos_ayuda"] == RECURSOS
        assert len(tabla) == 2  # Valparaíso y Ñuñoa

    def test_usa_el_umbral_de_mortalidad_por_defecto(self, silver):
        """Eventos poco frecuentes y de la dimensión más sensible: k=10, no k=5."""
        _, meta = tabla_egresos_autoinfligida(silver, RECURSOS)
        assert meta["supresion"]["k"] == 10

    def test_declara_la_revision_clinica_como_pendiente(self, silver):
        _, meta = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
        assert "PENDIENTE" in meta["revision_clinica"]
        assert any("REVISIÓN CLÍNICA PENDIENTE" in a for a in meta["advertencias"])

    def test_advierte_que_no_se_resta_contra_las_otras_series(self, silver):
        _, meta = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
        assert any("NO SE RESTA" in a for a in meta["advertencias"])

    def test_advierte_la_prohibicion_de_desagregar_por_metodo(self, silver):
        _, meta = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
        assert any("MÉTODO" in a for a in meta["advertencias"])

    def test_la_tabla_no_expone_el_codigo_individual(self, silver):
        """CLAUDE.md §2.4: el agrupador es la única salida pública."""
        tabla, _ = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
        assert "causa_cie10" not in tabla.columns
        assert "causa_externa" not in tabla.columns
        assert set(tabla["agrupador"]) == {"LESION_AUTOINFLIGIDA_MORBILIDAD"}


def test_las_dos_tablas_cuentan_universos_disjuntos(silver):
    """Ningún egreso aparece en las dos series: verificado disjunto en el archivo real."""
    mentales, _ = tabla_egresos_salud_mental(silver, k=1)
    auto, _ = tabla_egresos_autoinfligida(silver, RECURSOS, k=1)
    assert mentales["egresos"].sum() == 4
    assert auto["egresos"].sum() == 2
    assert mentales["egresos"].sum() + auto["egresos"].sum() <= len(silver)


def test_el_silver_no_pierde_filas_sin_avisar(bronze):
    """Toda fila descartada tiene que quedar contada en el reporte."""
    silver, rep = normalizar_egresos(bronze)
    assert rep["filas_entrada"] == len(bronze)
    assert rep["filas_salida"] + rep["filas_total_descartadas"] == rep["filas_entrada"]
