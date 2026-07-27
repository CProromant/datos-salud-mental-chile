"""Tests de territorio. Son de regresión: no se relajan para hacer pasar una ingesta.

Si una fuente trae una grafía nueva, se agrega a ALIAS **y** se agrega su test acá.
"""

import pytest

from obsm.errors import TerritorioError
from obsm.territorio import (
    ANIO_CREACION_NUBLE,
    COMUNA_DESCONOCIDA,
    N_COMUNAS_ESPERADO,
    REGIONES,
    aplicar_alias,
    cargar_dpa,
    formatear_cut_comuna,
    normalizar_comuna,
    normalizar_serie_comunas,
    normalizar_texto,
    region_de_comuna,
    region_vigente,
    validar_dpa,
)


class TestNormalizarTexto:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Santiago", "santiago"),
            ("  VALPARAÍSO  ", "valparaiso"),
            ("Ñuñoa", "nunoa"),
            ("O'Higgins", "ohiggins"),
            ("O’Higgins", "ohiggins"),  # apóstrofo tipográfico
            ("Llay-Llay", "llay llay"),
            ("Til  Til", "til til"),
            ("Concón", "concon"),
            ("Ollagüe", "ollague"),
            ("", ""),
        ],
    )
    def test_casos(self, entrada, esperado):
        assert normalizar_texto(entrada) == esperado

    def test_none_no_explota(self):
        assert normalizar_texto(None) == ""


class TestAlias:
    @pytest.mark.parametrize(
        "alterno,canonico",
        [
            ("Coihaique", "coyhaique"),
            ("Aisén", "aysen"),
            ("Puerto Aysén", "aysen"),
            ("Til Til", "tiltil"),
            ("Llay-Llay", "llaillay"),
            ("Paiguano", "paihuano"),
            ("Marchigüe", "marchihue"),
            ("Trehuaco", "treguaco"),
            ("Alto Bío Bío", "alto biobio"),
            ("Chol Chol", "cholchol"),
            ("Puerto Natales", "natales"),
            ("Rapa Nui", "isla de pascua"),
            ("Puerto Williams", "cabo de hornos"),
        ],
    )
    def test_alias_conocidos(self, alterno, canonico):
        assert aplicar_alias(normalizar_texto(alterno)) == canonico

    def test_nombre_sin_alias_pasa_igual(self):
        assert aplicar_alias(normalizar_texto("Temuco")) == "temuco"


class TestCodigos:
    def test_ceros_a_la_izquierda(self):
        assert formatear_cut_comuna(5101) == "05101"
        assert formatear_cut_comuna("5101") == "05101"
        assert formatear_cut_comuna(" 13101 ") == "13101"

    def test_rechaza_basura(self):
        for malo in ["", "abc", "1234567", None]:
            with pytest.raises(TerritorioError):
                formatear_cut_comuna(malo)

    def test_region_de_comuna(self):
        assert region_de_comuna("05101") == "05"
        assert region_de_comuna(5101) == "05"

    def test_todas_las_regiones_declaradas(self):
        assert len(REGIONES) == 16
        assert all(len(k) == 2 for k in REGIONES)


class TestNuble:
    """El caso que rompe silenciosamente cualquier serie larga por región."""

    def test_antes_de_2018_las_comunas_de_nuble_eran_biobio(self):
        assert region_vigente("16101", ANIO_CREACION_NUBLE - 1) == "08"

    def test_desde_2018_son_nuble(self):
        assert region_vigente("16101", ANIO_CREACION_NUBLE) == "16"
        assert region_vigente("16101", 2024) == "16"

    def test_otras_regiones_no_se_ven_afectadas(self):
        assert region_vigente("08101", 2010) == "08"
        assert region_vigente("13101", 2010) == "13"


class TestResolucion:
    def test_resuelve_capital_regional(self):
        assert normalizar_comuna("Santiago") == "13101"
        assert normalizar_comuna("Punta Arenas") == "12101"

    def test_resuelve_por_alias(self):
        assert normalizar_comuna("Coihaique") == "11101"
        assert normalizar_comuna("COIHAIQUE") == "11101"

    def test_resuelve_sin_tildes(self):
        assert normalizar_comuna("Valparaiso") == "05101"

    def test_falla_ruidosamente_ante_desconocida(self):
        with pytest.raises(TerritorioError):
            normalizar_comuna("Comuna Inexistente")

    def test_modo_no_estricto_marca_desconocida(self):
        assert normalizar_comuna("Comuna Inexistente", estricto=False) == COMUNA_DESCONOCIDA

    def test_serie_reporta_tasa_de_no_resolucion(self):
        cuts, rep = normalizar_serie_comunas(
            ["Santiago", "Coihaique", "Comuna Inexistente", "Otra Rara"]
        )
        assert cuts[:2] == ["13101", "11101"]
        assert cuts[2] == cuts[3] == COMUNA_DESCONOCIDA
        assert rep["no_resueltos"] == 2
        assert rep["tasa_no_resolucion"] == 0.5
        assert "Comuna Inexistente" in rep["detalle"]


class TestDPA:
    def test_semilla_es_consistente_internamente(self):
        dpa = cargar_dpa()
        problemas = validar_dpa(dpa, estricto=False)
        # La única inconsistencia aceptable de la semilla es su incompletitud.
        assert all("incompleta" in p for p in problemas), problemas

    def test_semilla_esta_marcada_como_incompleta(self):
        """Si alguien completa la DPA, este test recuerda actualizar el flujo estricto."""
        dpa = cargar_dpa()
        if len(dpa) < N_COMUNAS_ESPERADO:
            assert not dpa.completa
            with pytest.raises(TerritorioError):
                validar_dpa(dpa, estricto=True)
        else:
            assert dpa.completa
            assert validar_dpa(dpa, estricto=True) == []

    def test_sin_nombres_ambiguos_en_la_semilla(self):
        assert cargar_dpa().nombres_ambiguos() == []


class TestSerieConGeneradores:
    """Regresión: medir el largo de un generador lo consume. La versión anterior
    devolvía cero filas sin lanzar ningún error."""

    def test_acepta_un_generador(self):
        cuts, rep = normalizar_serie_comunas(n for n in ["Santiago", "Coihaique"])
        assert cuts == ["13101", "11101"]
        assert rep["total"] == 2

    def test_largos_incompatibles_fallan(self):
        with pytest.raises(TerritorioError):
            normalizar_serie_comunas(["Santiago", "Temuco"], region_cuts=["13"])
