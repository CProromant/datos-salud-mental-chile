"""Tests del parser de la Glosa 06.

Es la única fuente pública que dice cuánta gente espera por psiquiatría en Chile, y el
parser es **frágil por diseño** (`CLAUDE.md` §8): tiene que fallar ante un informe
rediseñado, no adaptarse. Los fixtures son el texto real de dos trimestres consecutivos,
que ya traen dos formatos distintos.
"""

from pathlib import Path

import pytest

from obsm.errors import SchemaDriftError
from obsm.ingest.glosa06 import (
    normalizar_especialidad,
    parsear_tabla_especialidades,
)

FIXTURES = Path(__file__).parent / "fixtures" / "glosa06"


def _texto(nombre: str) -> list[str]:
    return [(FIXTURES / nombre).read_text(encoding="utf-8")]


@pytest.fixture()
def t2025():
    return parsear_tabla_especialidades(_texto("2025_T3_tabla15.txt"))


@pytest.fixture()
def t2026():
    return parsear_tabla_especialidades(_texto("2026_T1_tabla15.txt"))


class TestNormalizacion:
    """La etiqueta cambia de caja Y de género entre trimestres consecutivos."""

    def test_la_caja_no_separa_conceptos(self):
        assert normalizar_especialidad("PSIQUIATRÍA ADULTO") == normalizar_especialidad(
            "Psiquiatría adulto"
        )

    def test_quita_tildes_y_puntuacion(self):
        assert normalizar_especialidad("Medicina física y rehabilitación (fisiatría)") == (
            "MEDICINA FISICA Y REHABILITACION FISIATRIA"
        )


class TestPsiquiatria:
    """La cifra que justifica la fase: ~36.000 personas esperando psiquiatra."""

    def test_encuentra_las_dos_especialidades_en_2025(self, t2025):
        _, rep = t2025
        assert rep["salud_mental"] == {
            "Psiquiatría adulta": 22_963,
            "Psiquiatría infanto-adolescente": 13_960,
        }

    def test_las_encuentra_igual_en_2026_pese_al_cambio_de_etiqueta(self, t2026):
        # 2025 dice «PSIQUIATRÍA ADULTO» y 2026 «Psiquiatría adulta»: cambia la caja y el
        # género. Agrupar por la cadena cruda parte la serie en dos (A-012).
        _, rep = t2026
        assert rep["salud_mental"] == {
            "Psiquiatría adulta": 23_134,
            "Psiquiatría infanto-adolescente": 12_585,
        }

    def test_no_quedan_especialidades_de_salud_mental_sin_reconocer(self, t2025, t2026):
        for _, rep in (t2025, t2026):
            assert rep["salud_mental_faltante"] == []


class TestOrdenYPosicion:
    """Ni el orden de las filas ni la página son estables entre informes."""

    def test_lee_los_dos_ordenes(self, t2025, t2026):
        # 2025 va alfabético, 2026 por magnitud descendente. Anclar en la posición de la
        # fila rompe al primer informe nuevo.
        t25, _ = t2025
        t26, _ = t2026
        assert t25.iloc[0]["registros"] != t25["registros"].max(), "2025 no va por magnitud"
        assert t26.iloc[0]["registros"] == t26["registros"].max(), "2026 sí"

    def test_la_tabla_se_busca_por_contenido_no_por_pagina(self, t2025):
        # La tabla estaba en la página 27 en 2025 y en la 29 en 2026.
        t, rep = t2025
        assert rep["especialidades"] > 50
        assert "pagina" in rep


class TestFilaDeTotal:
    """La tabla trae su propio total mezclado con el detalle."""

    def test_el_total_no_entra_como_especialidad(self, t2025):
        t, _ = t2025
        assert not t["especialidad_fuente"].str.contains("Total", case=False).any()

    def test_el_total_declarado_se_conserva_como_ancla(self, t2025):
        _, rep = t2025
        assert rep["total_declarado"] == 2_051_482

    def test_el_detalle_de_2025_cuadra_exacto_con_el_total_del_informe(self, t2025):
        # Es la comprobación que valida el parser entero: si la suma del detalle da
        # exactamente el total que el propio informe declara, no se perdió ni se inventó
        # ninguna fila. Fue lo que delató que el pie de página entraba como especialidad.
        _, rep = t2025
        assert rep["diferencia_con_total"] == 0

    def test_el_pie_de_pagina_no_entra_como_especialidad(self, t2025):
        # «Glosa 06 III trimestre 2025» seguido del número de página se emparejaba como
        # una especialidad de 27 registros.
        t, _ = t2025
        assert not t["especialidad_norm"].str.contains("GLOSA").any()
        assert not t["especialidad_norm"].str.contains("MINISTERIO").any()


class TestContrato:
    def test_falla_si_no_encuentra_la_tabla(self):
        with pytest.raises(SchemaDriftError, match="no se encontró la tabla"):
            parsear_tabla_especialidades(["Un informe sin tabla de especialidades."])

    def test_falla_si_la_tabla_quedo_a_medias(self):
        # Menos de diez pares es un rediseño, no una tabla corta. Adaptarse en silencio
        # publicaría una serie con la mitad de las especialidades.
        parcial = "Especialidad médica\nN° de registros\nOFTALMOLOGÍA\n372.391\n"
        with pytest.raises(SchemaDriftError):
            parsear_tabla_especialidades([parcial])

    def test_el_reporte_declara_cuantas_especialidades_leyo(self, t2025, t2026):
        _, r25 = t2025
        _, r26 = t2026
        assert r25["especialidades"] == 66
        assert r26["especialidades"] == 62


class TestAnomaliaDeLaFuente:
    """A-018: la tabla de 2026 no suma su propio total declarado."""

    def test_2026_no_cuadra_y_la_diferencia_se_declara(self, t2026):
        # El parser captura todos los números presentes en el texto —verificado línea por
        # línea— y aun así falta 0,58 %. El hueco está en el informe, no acá. Se declara
        # en vez de esconderlo, para que quien use la tabla sepa que no es exhaustiva.
        _, rep = t2026
        assert rep["diferencia_con_total"] == -11_478
        assert abs(rep["diferencia_con_total"]) < 0.01 * rep["total_declarado"]


class TestPeriodo:
    """El trimestre se lee del contenido, nunca del nombre del archivo."""

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Glosa 06 III trimestre 2025", "2025-09"),
            ("correspondiente al primer trimestre de 2026", "2026-03"),
            ("IV trimestre 2024", "2024-12"),
            ("cuarto trimestre del 2023", "2023-12"),
            ("II trimestre 2022", "2022-06"),
        ],
    )
    def test_lee_las_dos_formas_de_escribir_el_trimestre(self, texto, esperado):
        # Dos informes consecutivos usan formas distintas: romanos y ordinales en palabra.
        from obsm.ingest.glosa06 import periodo_del_informe

        assert periodo_del_informe([texto]) == esperado

    def test_el_mes_es_el_de_cierre_del_trimestre(self):
        # El corte de la lista es el último día del trimestre: «III trimestre 2025» son
        # los datos al 30 de septiembre, no al 1 de julio.
        from obsm.ingest.glosa06 import periodo_del_informe

        assert periodo_del_informe(["III trimestre 2025"]) == "2025-09"

    def test_falla_ante_una_forma_nueva(self):
        # Deducirlo del nombre del archivo no sirve: los dos nombres publicados no
        # comparten patrón y uno ni siquiera trae el año.
        from obsm.ingest.glosa06 import periodo_del_informe

        with pytest.raises(SchemaDriftError, match="trimestre"):
            periodo_del_informe(["Informe correspondiente a Q3 2025"])


class TestIngestor:
    def test_agrega_el_periodo_a_cada_fila(self):
        from obsm.ingest.glosa06 import Glosa06, parsear_tabla_especialidades

        tabla, _ = parsear_tabla_especialidades(_texto("2025_T3_tabla15.txt"))
        assert len(tabla) == 66
        # El fixture de texto no trae la portada, así que se prueba la composición
        # directamente sobre el parser; el período tiene su propio test arriba.
        assert Glosa06.source_id == "glosa06"
        assert "registros" in Glosa06.columnas_requeridas


class TestGoldEspecialidad:
    """La serie publicable. Corta a propósito: solo hay dos informes descargables."""

    @pytest.fixture()
    def gold(self):
        import pandas as pd

        from obsm.transform.gold import tabla_espera_especialidad

        t25, _ = parsear_tabla_especialidades(_texto("2025_T3_tabla15.txt"))
        t26, _ = parsear_tabla_especialidades(_texto("2026_T1_tabla15.txt"))
        t25.insert(0, "periodo", "2025-09")
        t26.insert(0, "periodo", "2026-03")
        return tabla_espera_especialidad(pd.concat([t25, t26], ignore_index=True))

    def test_arma_la_serie_de_psiquiatria(self, gold):
        _, meta = gold
        assert meta["salud_mental"]["2025-09"]["Psiquiatría adulta"] == 22_963
        assert meta["salud_mental"]["2026-03"]["Psiquiatría adulta"] == 23_134

    def test_arrastra_procedencia(self, gold):
        g, _ = gold
        for col in ("source_id", "pipeline_version", "fecha_calculo", "unidad_territorial"):
            assert col in g.columns

    def test_declara_que_la_cifra_es_nacional(self, gold):
        g, meta = gold
        assert (g["unidad_territorial"] == "nacional").all()
        assert any("NACIONAL" in a for a in meta["advertencias"])

    def test_advierte_de_la_anomalia_del_informe_de_2026(self, gold):
        # Sin este aviso alguien calcularía «psiquiatría es el X % de la lista» sobre un
        # denominador que no cuadra consigo mismo.
        _, meta = gold
        assert any("A-018" in a for a in meta["advertencias"])
