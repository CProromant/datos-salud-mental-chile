"""Tests del ingestor de listas de espera del MINSAL.

Es la única fuente del proyecto que trae **mediana de días de espera por Servicio de
Salud**, y su trampa central es temporal: la mediana no existe antes de 2022. Una serie
que arranque en 2019 compara contra vacío sin que nada lo advierta, así que los tests que
custodian el nulo son de regresión.
"""

from pathlib import Path

import pandas as pd
import pytest

from obsm.errors import SchemaDriftError
from obsm.ingest.listaespera_minsal import (
    ListaEsperaMinsal,
    periodo_iso,
    slug_servicio,
)

FIXTURES = Path(__file__).parent / "fixtures" / "listaespera_minsal"
NACIONAL = FIXTURES / "data_NACIONAL.json"
VARIOS = FIXTURES / "muestra_varios_servicios.json"


@pytest.fixture()
def bronze():
    return ListaEsperaMinsal().preparar(VARIOS)


class TestSlugDelServicio:
    """El nombre del archivo lo construye el JavaScript del sitio; hay que replicarlo."""

    def test_mayusculas_guion_bajo_y_sin_tildes(self):
        assert slug_servicio("Servicio de Salud Ñuble") == "SERVICIO_DE_SALUD_NUBLE"
        assert slug_servicio("Servicio de Salud Aysén") == "SERVICIO_DE_SALUD_AYSEN"

    def test_conserva_el_apostrofo_tipografico(self):
        # `data_SERVICIO_DE_SALUD_O’HIGGINS.json` responde 200; la misma URL con el
        # apóstrofo recto da 404. Quitarlo es la forma silenciosa de perder un Servicio
        # entero de la serie.
        assert slug_servicio("Servicio de Salud O’Higgins") == (
            "SERVICIO_DE_SALUD_O’HIGGINS"
        )
        assert "'" not in slug_servicio("Servicio de Salud O’Higgins")


class TestPeriodo:
    """El trimestre viene como texto en español y tiene que salir en ISO."""

    @pytest.mark.parametrize(
        ("crudo", "esperado"),
        [
            ("MARZO 2019", "2019-03"),
            ("JUNIO 2025", "2025-06"),
            ("SEPTIEMBRE 2024", "2024-09"),
            ("DICIEMBRE 2023", "2023-12"),
        ],
    )
    def test_traduce_el_mes(self, crudo, esperado):
        assert periodo_iso(crudo) == esperado

    def test_un_mes_desconocido_falla(self):
        # Devolver algo ordenable pero falso uniría la fila con el trimestre equivocado.
        with pytest.raises(SchemaDriftError, match="trimestre no reconocido"):
            periodo_iso("ENERO 2024")

    def test_una_forma_abreviada_falla(self):
        with pytest.raises(SchemaDriftError):
            periodo_iso("ene-24")


class TestLectura:
    def test_lee_las_doce_metricas(self, bronze):
        for lista in ("consulta", "quirurgica", "ges"):
            for m in ("registros", "pacientes", "promedio", "mediana"):
                assert f"{lista}_{m}" in bronze.columns

    def test_el_periodo_ordena_cronologicamente(self, bronze):
        nac = bronze[bronze["servicio"] == "NACIONAL"].sort_values("periodo")
        assert nac["periodo"].tolist() == ["2019-03", "2023-12", "2025-06"]

    def test_los_conteos_son_enteros_y_los_dias_no(self, bronze):
        # La pregunta no es si el número tiene coma, es qué mide. Un conteo fraccionario
        # sería un error (A-010); un promedio de 281,9 días es un promedio.
        assert bronze["consulta_registros"].dtype == "Int64"
        assert bronze["consulta_pacientes"].dtype == "Int64"
        assert bronze["consulta_promedio"].dtype == "Float64"
        assert bronze["consulta_mediana"].dtype == "Float64"

    def test_conserva_los_decimales_de_los_dias(self, bronze):
        # 519 de 692 celdas de `ges_promedio` traen decimales en el archivo real.
        # Tiparlas como entero reventaba la ingesta completa.
        f = bronze[(bronze["servicio"] == "ACONCAGUA") & (bronze["periodo"] == "2019-03")]
        assert float(f["consulta_promedio"].iloc[0]) == pytest.approx(281.9)
        assert float(f["ges_promedio"].iloc[0]) == pytest.approx(97.2)

    def test_una_mediana_par_conserva_el_medio_punto(self, bronze):
        # La mediana de un conjunto de tamaño par es el promedio de los dos centrales.
        f = bronze[(bronze["servicio"] == "O’HIGGINS") & (bronze["periodo"] == "2025-06")]
        assert float(f["ges_mediana"].iloc[0]) == pytest.approx(274.5)

    def test_el_campo_servicio_es_un_slug_no_el_nombre_de_despliegue(self, bronze):
        # El JSON dice `ARICA_Y_PARINACOTA`, no «Servicio de Salud Arica y Parinacota».
        # Resolverlo a nombre legible es trabajo de silver; bronze lo deja como viene.
        assert "O’HIGGINS" in set(bronze["servicio"])
        assert "ACONCAGUA" in set(bronze["servicio"])

    def test_conserva_el_apostrofo_tipografico_del_servicio(self, bronze):
        assert "O'HIGGINS" not in set(bronze["servicio"])


class TestMedianaAusente:
    """La mediana no existe antes de 2022. Es la trampa que hunde una serie de tendencia."""

    def test_el_nulo_de_2019_se_conserva_como_nulo(self, bronze):
        fila = bronze[(bronze["servicio"] == "NACIONAL") & (bronze["periodo"] == "2019-03")]
        assert pd.isna(fila["consulta_mediana"].iloc[0])
        assert pd.isna(fila["quirurgica_mediana"].iloc[0])

    def test_no_se_rellena_con_cero(self, bronze):
        # Un 0 diría que nadie espera. La fuente simplemente no calculaba la mediana.
        assert (bronze["consulta_mediana"].fillna(-1) != 0).all()

    def test_el_dato_de_2019_que_si_existe_sobrevive(self, bronze):
        fila = bronze[(bronze["servicio"] == "NACIONAL") & (bronze["periodo"] == "2019-03")]
        assert int(fila["consulta_registros"].iloc[0]) == 1_860_581

    def test_declara_la_cobertura_de_la_mediana(self, bronze):
        cob = bronze.attrs["cobertura_mediana"]
        assert 0 < cob["consulta_mediana"] < 1, "el fixture mezcla años con y sin mediana"


class TestContrato:
    def test_falla_si_desaparece_una_metrica(self, tmp_path):
        import json
        datos = json.loads(VARIOS.read_text(encoding="utf-8"))
        for fila in datos:
            fila.pop("consulta_mediana")
        destino = tmp_path / "sin_mediana.json"
        destino.write_text(json.dumps(datos), encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="consulta_mediana"):
            ListaEsperaMinsal().preparar(destino)

    def test_falla_si_el_sitio_devuelve_algo_que_no_es_una_lista(self, tmp_path):
        destino = tmp_path / "error.json"
        destino.write_text('{"error": "not found"}', encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="no es una lista"):
            ListaEsperaMinsal().preparar(destino)

    def test_las_columnas_requeridas_existen(self, bronze):
        for col in ListaEsperaMinsal.columnas_requeridas:
            assert col in bronze.columns


class TestClaveServicio:
    """El visualizador y el maestro de DEIS nombran distinto a los mismos 29 servicios."""

    def test_los_nombres_equivalentes_dan_la_misma_clave(self):
        from obsm.transform.silver import clave_servicio
        assert clave_servicio("Servicio de Salud Antofagasta") == clave_servicio("ANTOFAGASTA")
        assert clave_servicio("Servicio de Salud Ñuble") == clave_servicio("NUBLE")

    def test_ohiggins_calza_pese_a_los_dos_apostrofos(self):
        # El maestro dice «Servicio de Salud Del Libertador B.O'Higgins» con apóstrofo
        # recto; el visualizador dice «O’HIGGINS» con el tipográfico. Sin el alias, un
        # Servicio entero queda fuera de la serie sin que nada falle.
        from obsm.transform.silver import clave_servicio
        assert clave_servicio("Servicio de Salud Del Libertador B.O'Higgins") == (
            clave_servicio("O\u2019HIGGINS")
        )

    def test_una_seremi_no_es_un_servicio_de_salud(self):
        from obsm.transform.silver import PREFIJO_SERVICIO_SALUD
        assert not "SEREMI de Salud de Antofagasta".lower().startswith(PREFIJO_SERVICIO_SALUD)


class TestSilverListaEspera:
    @pytest.fixture()
    def silver(self, bronze):
        from obsm.transform.silver import normalizar_listaespera
        return normalizar_listaespera(bronze)

    def test_la_grilla_es_servicio_por_periodo(self, silver):
        s, rep = silver
        assert rep["periodos"] == 3
        assert not s.duplicated(subset=["servicio_clave", "periodo"]).any()

    def test_no_lleva_comuna_cut_y_es_deliberado(self, silver):
        # Excepción declarada al contrato de silver: la unidad territorial de esta fuente
        # es el Servicio de Salud. Bajarla a comuna es una inferencia ecológica y para eso
        # está `mapa_servicio_comuna`, aparte y explícito.
        s, _ = silver
        assert "comuna_cut" not in s.columns

    def test_el_nacional_queda_marcado_y_no_se_confunde_con_un_servicio(self, silver):
        s, rep = silver
        assert s["es_nacional"].sum() == 3
        assert rep["servicios"] == 2, "NACIONAL no cuenta como Servicio de Salud"

    def test_declara_la_cobertura_de_cada_mediana(self, silver):
        _, rep = silver
        assert set(rep["cobertura_mediana"]) == {
            "consulta_mediana", "quirurgica_mediana", "ges_mediana"
        }

    def test_un_servicio_repetido_en_el_mismo_periodo_detiene_todo(self, bronze):
        from obsm.errors import ReconciliationError
        from obsm.transform.silver import normalizar_listaespera
        # Un servicio duplicado se suma solo al agregar y duplica la lista de espera.
        with pytest.raises(ReconciliationError, match="duplicad"):
            normalizar_listaespera(pd.concat([bronze, bronze], ignore_index=True))

    def test_avisa_de_un_servicio_que_no_existe_en_el_maestro(self, bronze):
        from obsm.transform.silver import normalizar_listaespera
        # El maestro solo conoce Aconcagua; O'Higgins queda huérfano y se reporta.
        maestro = pd.DataFrame({"servicio_salud": ["Servicio de Salud Aconcagua"]})
        _, rep = normalizar_listaespera(bronze, establecimientos=maestro)
        assert rep["servicios_sin_maestro"] == ["DEL_LIBERTADOR_BOHIGGINS"]
        assert rep["servicios_verificados"] == 1


class TestGoldListaEspera:
    """La tabla publicable. Su riesgo propio es la supresión: el nacional es la suma
    exacta de los 29 servicios, así que suprimir una celda sin complementaria la deja
    reconstruible por resta."""

    @pytest.fixture()
    def gold(self, bronze):
        from obsm.transform.gold import tabla_listas_espera
        from obsm.transform.silver import normalizar_listaespera
        s, _ = normalizar_listaespera(bronze)
        return tabla_listas_espera(s, k=5)

    def test_pasa_de_doce_columnas_a_una_fila_por_lista(self, gold):
        g, meta = gold
        assert set(g["lista"]) == {"consulta", "quirurgica", "ges"}
        assert set(["registros", "pacientes", "promedio_dias", "mediana_dias"]) <= set(g.columns)
        assert len(g) == len(set(zip(g["servicio_clave"], g["periodo"], g["lista"], strict=True)))

    def test_arrastra_procedencia(self, gold):
        g, _ = gold
        for col in ("source_id", "source_version", "pipeline_version", "fecha_calculo"):
            assert col in g.columns

    def test_marca_donde_la_mediana_no_existe(self, gold):
        # Sin esto, una serie de tendencia arranca en 2019 comparando contra vacío.
        g, _ = gold
        assert not g[g["anio"] == 2019]["mediana_disponible"].any()
        assert g[g["anio"] == 2025]["mediana_disponible"].all()

    def test_el_nacional_no_se_suprime_a_si_mismo(self, gold):
        # Es un total, no un par de los servicios: meterlo en el grupo de supresión lo
        # haría candidato a suprimirse.
        g, _ = gold
        assert not g.loc[g["es_nacional"], "suprimido"].any()

    def test_no_baja_a_comuna(self, gold):
        g, _ = gold
        assert "comuna_cut" not in g.columns

    def test_declara_que_no_hay_desglose_por_especialidad(self, gold):
        # Es la limitación que hace que esta serie no responda por psiquiatría, y tiene
        # que viajar con el dato y no solo en la documentación.
        _, meta = gold
        assert any("especialidad" in a for a in meta["advertencias"])


class TestSupresionListaEspera:
    def test_suprime_bajo_k(self):
        from obsm.transform.gold import tabla_listas_espera
        # Un servicio con 3 garantías retrasadas y otro con 900. El 3 está bajo k=5.
        s = pd.DataFrame({
            "servicio_clave": ["A", "B", "C"],
            "periodo": ["2025-06"] * 3,
            "anio": [2025] * 3,
            "es_nacional": [False] * 3,
            "ges_registros": pd.array([3, 40, 900], dtype="Int64"),
            "ges_pacientes": pd.array([3, 35, 800], dtype="Int64"),
            "ges_promedio": pd.array([10.0, 30.0, 55.5], dtype="Float64"),
            "ges_mediana": pd.array([9.0, 28.0, 50.0], dtype="Float64"),
        })
        g, meta = tabla_listas_espera(s, k=5)
        por_serv = g.set_index("servicio_clave")
        assert pd.isna(por_serv.loc["A", "registros"]), "3 está bajo k=5"
        assert por_serv.loc["C", "registros"] == 900, "900 no corre riesgo"
        assert meta["supresion"]["filas_suprimidas"] >= 1

    def test_un_cero_puede_caer_como_complementaria_y_esta_documentado(self):
        from obsm.transform.gold import tabla_listas_espera
        # `docs/06` dice a la vez «el cero sí se publica» y que la complementaria es «la
        # menor de las celdas restantes». Cuando la menor ES un cero, las dos reglas
        # chocan y gana la segunda, que es la implementada. Este test fija la conducta
        # real para que un cambio de política sea deliberado y no un efecto lateral.
        # Ver A-017 en docs/05-CALIDAD.md.
        s = pd.DataFrame({
            "servicio_clave": ["A", "B", "C"],
            "periodo": ["2025-06"] * 3,
            "anio": [2025] * 3,
            "es_nacional": [False] * 3,
            "ges_registros": pd.array([3, 0, 900], dtype="Int64"),
            "ges_pacientes": pd.array([3, 0, 800], dtype="Int64"),
            "ges_promedio": pd.array([10.0, 0.0, 55.5], dtype="Float64"),
            "ges_mediana": pd.array([9.0, 0.0, 50.0], dtype="Float64"),
        })
        g, _ = tabla_listas_espera(s, k=5)
        por_serv = g.set_index("servicio_clave")
        assert pd.isna(por_serv.loc["B", "registros"]), (
            "hoy el cero se suprime como complementaria; si esto cambia, es una decisión "
            "de política y exige versión nueva del dataset (docs/07)"
        )

    def test_la_supresion_complementaria_impide_la_resta(self):
        from obsm.transform.gold import tabla_listas_espera
        # Con una sola celda suprimida y el resto visible, quien conozca el total del
        # grupo la reconstruye restando. Por eso se suprime una segunda.
        s = pd.DataFrame({
            "servicio_clave": ["A", "B", "C"],
            "periodo": ["2025-06"] * 3,
            "anio": [2025] * 3,
            "es_nacional": [False] * 3,
            "ges_registros": pd.array([2, 40, 900], dtype="Int64"),
            "ges_pacientes": pd.array([2, 35, 800], dtype="Int64"),
            "ges_promedio": pd.array([10.0, 30.0, 55.0], dtype="Float64"),
            "ges_mediana": pd.array([9.0, 28.0, 50.0], dtype="Float64"),
        })
        g, meta = tabla_listas_espera(s, k=5)
        assert int(g["suprimido"].sum()) == 2, "la de riesgo más la complementaria"
        assert meta["supresion"]["complementarias"] == 1
