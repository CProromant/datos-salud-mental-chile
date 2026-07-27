"""Test de extremo a extremo sobre el fixture: ingesta -> silver -> gold.

Es el test que detecta las roturas entre módulos, que son las que ningún test
unitario ve.
"""

from pathlib import Path

import pandas as pd
import pytest

from obsm.ingest.deis_defunciones import DeisDefunciones
from obsm.transform.gold import tasas_comunales
from obsm.transform.silver import agregar_defunciones, normalizar_defunciones

FIXTURES = Path(__file__).parent / "fixtures"
MUESTRA = FIXTURES / "deis_defunciones" / "muestra_latin1.csv"
MUESTRA_REAL = FIXTURES / "deis_defunciones" / "muestra_estructura_real.csv"
POBLACION = FIXTURES / "poblacion" / "poblacion_muestra.csv"


@pytest.fixture()
def bronze():
    return DeisDefunciones().preparar(MUESTRA)


@pytest.fixture()
def silver(bronze):
    df, reporte = normalizar_defunciones(bronze)
    return df, reporte


class TestIngesta:
    def test_lee_separador_y_encoding_correctos(self, bronze):
        assert len(bronze) == 16  # 15 registros + la fila TOTAL PAIS
        assert "causa_cie10" in bronze.columns

    def test_sexo_normalizado(self, bronze):
        assert set(bronze["sexo"].unique()) <= {"hombre", "mujer", "desconocido"}

    def test_edad_en_meses_no_se_lee_como_anios(self, bronze):
        fila = bronze[bronze["causa_cie10"] == "P219"].iloc[0]
        assert fila["edad_anios"] == 0
        assert fila["edad_unidad_original"] == "meses"

    def test_contrato_de_esquema_falla_si_faltan_columnas(self):
        ing = DeisDefunciones()
        from obsm.errors import SchemaDriftError
        with pytest.raises(SchemaDriftError):
            ing.validar_esquema(pd.DataFrame({"otra_cosa": [1]}))


class TestEstructuraRealDeis:
    """Regresión contra la estructura publicada por DEIS, verificada el 2026-07-27.

    El mapa de columnas anterior era una hipótesis y fallaba: la columna de año es `AÑO`
    y no `ANO_DEF`, y no existe `SEXO`, solo `SEXO_NOMBRE`. Estos tests fijan la
    estructura real para que un cambio de la fuente se note acá y no en un indicador.
    """

    @pytest.fixture()
    def bronze_real(self):
        return DeisDefunciones().preparar(MUESTRA_REAL)

    def test_el_encabezado_real_satisface_el_contrato(self, bronze_real):
        for col in ("anio", "sexo", "causa_cie10"):
            assert col in bronze_real.columns

    def test_la_columna_de_anio_se_llama_ano_a_secas(self, bronze_real):
        # La fila "TOTAL PAÍS" del fixture no trae año, y debe quedar nula en vez de
        # colarse como un año cualquiera. Se excluye con la marca del propio ingestor.
        datos = bronze_real[~bronze_real[DeisDefunciones.COL_FILA_TOTAL]]
        assert datos["anio"].notna().all()
        assert datos["anio"].min() == 1994

    def test_sexo_se_deriva_de_sexo_nombre(self, bronze_real):
        """La fuente no publica `SEXO`. Si `sexo` quedara vacío, el contrato pasaría
        igual y el indicador saldría todo 'desconocido'."""
        assert "sexo_nombre" in bronze_real.columns
        assert not (bronze_real["sexo"] == "desconocido").all()
        assert {"hombre", "mujer"} <= set(bronze_real["sexo"])

    def test_indeterminado_no_se_confunde_con_faltante(self, bronze_real):
        assert "indeterminado" in set(bronze_real["sexo"])

    def test_los_codigos_anteriores_a_1997_se_marcan_como_cie9(self, bronze_real):
        """Trampa central: los agrupadores de cie10.py sobre CIE-9 no fallan, dan cero."""
        viejos = bronze_real[bronze_real["anio"] < 1997]
        assert len(viejos) > 0
        assert (viejos["clasificacion_causa"] == "cie9").all()

        nuevos = bronze_real[bronze_real["anio"] >= 1997]
        assert (nuevos["clasificacion_causa"] == "cie10").all()

    def test_edad_sin_unidad_no_se_lee_como_anios(self, bronze_real):
        """EDAD_TIPO vacío con EDAD_CANT=3 no es «3 años»: es una edad desconocida."""
        sin_unidad = bronze_real[bronze_real["edad_unidad_original"] == "desconocido"]
        assert len(sin_unidad) > 0
        assert sin_unidad["edad_anios"].isna().all()

    def test_cod_comuna_llega_sin_cero_a_la_izquierda(self, bronze_real):
        """El ingestor no normaliza territorio: solo se verifica que el problema exista,
        para que `silver` esté obligado a resolverlo con formatear_cut_comuna."""
        largos = set(bronze_real["comuna_cut_fuente"].dropna().astype(str).str.len())
        assert 4 in largos and 5 in largos


class TestSilver:
    def test_descarta_la_fila_de_total(self, silver):
        df, rep = silver
        assert rep["filas_total_descartadas"] == 1
        assert len(df) == 15

    def test_resuelve_alias_de_comuna(self, silver):
        df, _ = silver
        coyhaique = df[df["comuna_cut"] == "11101"]
        assert len(coyhaique) == 2  # "Coihaique" y "COYHAIQUE"

    def test_reporta_comuna_no_resuelta_en_vez_de_perderla(self, silver):
        df, rep = silver
        assert rep["territorio"]["no_resueltos"] == 1
        assert "Comuna Inexistente" in rep["territorio"]["detalle"]
        assert (df["comuna_cut"] == "99999").sum() == 1

    def test_clasificacion_de_suicidio(self, silver):
        df, _ = silver
        # 2022: X700 Santiago, X70 Santiago, X610 Santiago, X700 Valparaíso,
        # X700 Coihaique, X840 Coyhaique, Y870 Punta Arenas, X700 comuna no resuelta = 8
        # 2021: X700 Santiago, X780 Valparaíso = 2
        assert df["es_suicidio"].sum() == 10

    def test_intencion_indeterminada_no_entra_a_suicidio(self, silver):
        df, _ = silver
        fila = df[df["causa_cie10"] == "Y210"].iloc[0]
        assert fila["es_intencion_indeterminada"]
        assert not fila["es_suicidio"]

    def test_causa_no_mental_no_clasifica(self, silver):
        df, _ = silver
        fila = df[df["causa_cie10"] == "I219"].iloc[0]
        assert not fila["es_suicidio"]
        assert not fila["es_trastornos_mentales"]


class TestGold:
    def test_comunas_sin_casos_aparecen_con_cero(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, meta = tasas_comunales(agregado, poblacion, "SUICIDIO", k=1)
        # Concepción (08101) no tiene suicidios en el fixture pero sí población.
        fila = gold[(gold["comuna_cut"] == "08101") & (gold["anio"] == 2022)]
        assert len(fila) == 1
        assert fila.iloc[0]["casos"] == 0

    def test_no_inventa_comunas_sin_poblacion(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, _ = tasas_comunales(agregado, poblacion, "SUICIDIO", k=1)
        assert "99999" not in set(gold["comuna_cut"])  # sin denominador, no hay tasa

    def test_supresion_borra_conteo_y_tasa(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, meta = tasas_comunales(agregado, poblacion, "SUICIDIO", k=10)
        suprimidas = gold[gold["suprimido"]]
        assert len(suprimidas) > 0
        assert suprimidas["casos"].isna().all()
        assert suprimidas["tasa_cruda"].isna().all()  # si no, se reconstruye por resta

    def test_arrastra_procedencia(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, _ = tasas_comunales(
            agregado, poblacion, "SUICIDIO", source_version="2026-07", poblacion_version="INE-2017"
        )
        for col in ["source_id", "source_version", "poblacion_version", "pipeline_version",
                    "fecha_calculo"]:
            assert col in gold.columns
            assert gold[col].notna().all()

    def test_marca_anios_preliminares(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, meta = tasas_comunales(agregado, poblacion, "SUICIDIO", anios_preliminares=(2022,))
        assert gold[gold["anio"] == 2022]["preliminar"].all()
        assert any("preliminar" in a for a in meta["advertencias"])

    def test_advierte_cuando_el_ruido_domina(self, silver):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        gold, meta = tasas_comunales(agregado, poblacion, "SUICIDIO")
        assert isinstance(meta["advertencias"], list)
        assert meta["supresion"]["k"] == 10


class TestMarcaFilaTotal:
    """Regresión del bug real: la fila de total sobrevive a la lectura pero pierde
    su pista textual en la coerción de tipos. Si alguien mueve la detección después
    del posproceso, estos tests fallan."""

    def test_el_ingestor_marca_la_fila_total(self, bronze):
        assert bronze["_es_fila_total"].sum() == 1

    def test_la_marca_sobrevive_al_posproceso(self, bronze):
        fila = bronze[bronze["_es_fila_total"]].iloc[0]
        assert pd.isna(fila["anio"])  # el texto ya se perdió...
        assert fila["_es_fila_total"]  # ...pero la marca no


class TestSuavizadoPorAnio:
    """El suavizado debe calcularse dentro de cada año. Si se calcula sobre el panel
    completo, la media hacia la que se encoge una comuna incluye sus propios años
    vecinos y las tendencias reales se aplanan."""

    def _gold(self, silver, **kw):
        df, _ = silver
        agregado = agregar_defunciones(df, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        poblacion = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        return tasas_comunales(agregado, poblacion, "SUICIDIO", **kw)

    def test_agrupa_por_anio_por_defecto(self, silver):
        _, meta = self._gold(silver)
        assert meta["suavizado_eb"]["agrupado_por"] == ["anio"]
        assert len(meta["suavizado_eb"]["por_grupo"]) == 2  # 2021 y 2022

    def test_tasas_globales_distintas_entre_anios(self, silver):
        _, meta = self._gold(silver)
        globales = [g["tasa_global"] for g in meta["suavizado_eb"]["por_grupo"].values()]
        assert globales[0] != globales[1]

    def test_se_puede_forzar_panel_completo(self, silver):
        _, meta = self._gold(silver, grupo_suavizado=[])
        assert meta["suavizado_eb"]["por_grupo"].keys() == {"global"}

    def test_casos_es_entero_nullable(self, silver):
        gold, _ = self._gold(silver)
        assert str(gold["casos"].dtype) == "Int64"
