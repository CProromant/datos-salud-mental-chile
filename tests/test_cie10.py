"""Tests de los agrupadores CIE-10 y de la política de publicación."""

import pytest

from obsm.cie10 import (
    AGRUPADORES,
    DEMENCIAS,
    INTENCION_INDETERMINADA,
    SUICIDIO,
    TRASTORNOS_ANIMO,
    TRASTORNOS_MENTALES,
    clasificar,
    en_rango,
    es_publicable,
    normalizar_codigo,
)


class TestNormalizacion:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [("x60.1", "X601"), (" F32 ", "F32"), ("f32.9", "F329"), ("Y87.0", "Y870")],
    )
    def test_codigos(self, entrada, esperado):
        assert normalizar_codigo(entrada) == esperado

    def test_none(self):
        assert normalizar_codigo(None) == ""


class TestRangos:
    def test_dentro(self):
        assert en_rango("F32.1", "F30", "F39")
        assert en_rango("F30", "F30", "F39")
        assert en_rango("F39", "F30", "F39")

    def test_fuera(self):
        assert not en_rango("F40", "F30", "F39")
        assert not en_rango("F29", "F30", "F39")

    def test_letra_distinta(self):
        assert not en_rango("X60", "F30", "F39")

    def test_basura(self):
        assert not en_rango("", "F30", "F39")
        assert not en_rango("ZZZ", "F30", "F39")


class TestSuicidio:
    @pytest.mark.parametrize("codigo", ["X60", "X700", "X84", "X84.9", "Y87.0"])
    def test_incluye(self, codigo):
        assert SUICIDIO.contiene(codigo)

    @pytest.mark.parametrize("codigo", ["X85", "X59", "Y10", "Y21.0", "F32", "I21"])
    def test_excluye(self, codigo):
        assert not SUICIDIO.contiene(codigo)

    def test_indeterminada_es_agrupador_aparte(self):
        assert INTENCION_INDETERMINADA.contiene("Y210")
        assert not SUICIDIO.contiene("Y210")


class TestOtrosAgrupadores:
    def test_animo(self):
        assert TRASTORNOS_ANIMO.contiene("F32.9")
        assert not TRASTORNOS_ANIMO.contiene("F41")

    def test_capitulo_completo(self):
        assert TRASTORNOS_MENTALES.contiene("F99")
        assert not TRASTORNOS_MENTALES.contiene("G30")

    def test_demencias_incluye_alzheimer_fuera_del_capitulo_f(self):
        assert DEMENCIAS.contiene("G30.0")
        assert DEMENCIAS.contiene("F03")

    def test_solapamiento_declarado(self):
        """F03 cae en dos agrupadores: la clasificación es multi-etiqueta a propósito."""
        etiquetas = clasificar("F03")
        assert "DEMENCIAS" in etiquetas
        assert "TRASTORNOS_MENTALES" in etiquetas

    def test_causa_no_mental_no_clasifica(self):
        assert clasificar("I21.9") == []


class TestPoliticaPublicacion:
    def test_agrupador_de_suicidio_es_publicable(self):
        assert es_publicable("SUICIDIO", nivel_detalle="agrupador")

    def test_detalle_por_codigo_esta_prohibido(self):
        assert not es_publicable("SUICIDIO", nivel_detalle="codigo")
        assert not es_publicable("LESION_AUTOINFLIGIDA_MORBILIDAD", nivel_detalle="codigo")

    def test_detalle_por_codigo_permitido_en_agrupadores_no_sensibles(self):
        assert es_publicable("TRASTORNOS_ANIMO", nivel_detalle="codigo")

    def test_todos_los_agrupadores_tienen_id_consistente(self):
        for k, v in AGRUPADORES.items():
            assert k == v.id


class TestElGuardDePublicacionNoFallaAbierto:
    """`es_publicable` hace cumplir una regla no negociable de docs/06.

    Antes devolvía True para cualquier `nivel_detalle` que no reconociera: un typo
    como "subcodigo" no coincidía con la condición, se saltaba la prohibición y
    autorizaba la publicación. Se descubrió escribiendo el archivo de práctica, que
    usó justamente ese literal equivocado.
    """

    @pytest.mark.parametrize("nivel", ["subcodigo", "sub_codigo", "CODIGO", "", "detalle"])
    def test_un_nivel_desconocido_se_detiene_en_vez_de_autorizar(self, nivel):
        with pytest.raises(ValueError, match="nivel_detalle"):
            es_publicable("SUICIDIO", nivel_detalle=nivel)

    def test_los_niveles_validos_siguen_funcionando(self):
        assert es_publicable("SUICIDIO", nivel_detalle="agrupador")
        assert not es_publicable("SUICIDIO", nivel_detalle="codigo")

    def test_el_error_nombra_los_niveles_validos(self):
        # Quien se equivoca tiene que poder arreglarlo sin leer el código fuente.
        with pytest.raises(ValueError) as exc:
            es_publicable("SUICIDIO", nivel_detalle="subcodigo")
        assert "agrupador" in str(exc.value) and "codigo" in str(exc.value)
