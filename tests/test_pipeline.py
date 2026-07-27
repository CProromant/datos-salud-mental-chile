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

    def test_el_suicidio_vive_en_la_causa_externa_no_en_la_basica(self, bronze_real):
        """Regresión del error más caro de esta fuente.

        En el archivo real, X60-X84 aparece 0 veces en DIAG1 y 46.805 en DIAG2: la causa
        básica trae la naturaleza de la lesión (`T71X`) y la externa el código `X`. Un
        agrupador aplicado solo a la básica devuelve cero en veintisiete años sin lanzar
        ningún error, con la forma de un hallazgo epidemiológico.
        """
        def es_x60_x84(s):
            return s.str.match(r"^X([6-7]\d|8[0-4])").fillna(False)

        assert not es_x60_x84(bronze_real["causa_basica"]).any()
        assert es_x60_x84(bronze_real["causa_externa"]).any()

    def test_causa_cie10_toma_la_externa_cuando_existe(self, bronze_real):
        con_externa = bronze_real[bronze_real["causa_externa"] != ""]
        assert (con_externa["causa_cie10"] == con_externa["causa_externa"]).all()
        assert (con_externa["origen_causa_cie10"] == "externa").all()

    def test_causa_cie10_cae_a_la_basica_en_muertes_por_enfermedad(self, bronze_real):
        """F32 (depresión) va en la causa básica y DIAG2 viene vacío. Si `causa_cie10`
        fuera siempre la externa, las muertes por enfermedad quedarían sin código."""
        sin_externa = bronze_real[bronze_real["causa_externa"] == ""]
        assert len(sin_externa) > 0
        assert (sin_externa["causa_cie10"] == sin_externa["causa_basica"]).all()
        assert "F32" in set(sin_externa["causa_cie10"])

    def test_el_agrupador_de_suicidio_no_devuelve_cero(self):
        """La prueba que importa: de punta a punta, silver debe contar los suicidios."""
        bronze = DeisDefunciones().preparar(MUESTRA_REAL)
        df, _ = normalizar_defunciones(bronze)
        assert df["es_suicidio"].sum() == 7

    def test_columnas_que_mapean_al_mismo_destino_fallan_ruidosamente(self, tmp_path):
        """`renombrar_columnas` no resuelve colisiones: dos columnas homónimas hacen que
        `df["anio"]` devuelva un DataFrame, y el error aparece mucho después."""
        from obsm.errors import SchemaDriftError

        ruta = tmp_path / "colision.csv"
        ruta.write_text("AÑO;ANO_DEF;SEXO;DIAG1\n2022;2022;1;X700\n", encoding="latin-1")
        with pytest.raises(SchemaDriftError, match="mismo destino"):
            DeisDefunciones().preparar(ruta)

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


class TestCutValidadoContraLaDPA:
    """Un CUT bien formado no es un CUT que exista.

    DEIS usa 99999 como centinela de "comuna ignorada". Cuando silver validaba solo el
    formato, ese centinela pasaba como comuna real, producía `region_cut` 99 y el reporte
    decía `cut_invalidos: 0`. En el archivo real son 64 filas de 3.182.446: pocas para
    mover una tasa, suficientes para inventar una comuna en la salida.
    """

    def _bronze(self, cuts):
        return pd.DataFrame(
            {
                "comuna_cut_fuente": cuts,
                "anio": [2020] * len(cuts),
                "sexo": ["hombre"] * len(cuts),
                "edad_anios": [40] * len(cuts),
                "causa_cie10": ["X700"] * len(cuts),
                "_es_fila_total": [False] * len(cuts),
            }
        )

    def test_el_centinela_99999_no_se_toma_como_comuna(self):
        df, rep = normalizar_defunciones(self._bronze(["05101", "99999"]))
        assert rep["cut_fuera_de_dpa"] == 0  # 99999 ya es el desconocido, no un error nuevo
        assert rep["cut_desconocidos"] == 1
        assert set(df["region_cut"]) == {"05", "99"}

    def test_un_cut_inexistente_pero_bien_formado_se_cuenta(self):
        # 05999 tiene cinco dígitos y una región válida, pero no existe.
        df, rep = normalizar_defunciones(self._bronze(["05101", "05999"]))
        assert rep["cut_fuera_de_dpa"] == 1
        assert rep["cut_invalidos"] == 1
        assert df["comuna_cut"].tolist() == ["05101", "99999"]

    def test_los_cut_vigentes_no_se_tocan(self):
        df, rep = normalizar_defunciones(self._bronze(["05101", "16101", "13101"]))
        assert rep["cut_invalidos"] == 0
        assert rep["cut_desconocidos"] == 0
        assert df["comuna_cut"].tolist() == ["05101", "16101", "13101"]


class TestManifiestoDeBronze:
    """El manifiesto es el único lugar donde bronze dice de dónde vino.

    Escribía `source_version: null` y la URL de la portada del sitio. Con eso, una fila
    de gold es trazable a "el sitio de DEIS", no al archivo que se ingirió.
    """

    def _ingerir(self, tmp_path, monkeypatch):
        from obsm.ingest import base
        from obsm.registry import Fuente

        monkeypatch.setattr(base, "ruta_capa", lambda *a, **k: tmp_path / a[-1])
        fuente = Fuente(
            id="deis_defunciones", nombre="Defunciones",
            url_indice="https://deis.minsal.cl/#datosabiertos",
            url_archivo="https://ejemplo.cl/DEFUNCIONES.zip",
            source_version="CIFRAS_OFICIALES 1990-2023",
        )
        _, manifiesto = DeisDefunciones(fuente).ingerir(MUESTRA)
        return manifiesto

    def test_arrastra_source_version(self, tmp_path, monkeypatch):
        assert self._ingerir(tmp_path, monkeypatch).source_version == "CIFRAS_OFICIALES 1990-2023"

    def test_apunta_al_archivo_y_no_a_la_portada(self, tmp_path, monkeypatch):
        assert self._ingerir(tmp_path, monkeypatch).url == "https://ejemplo.cl/DEFUNCIONES.zip"

    def test_registra_hash_y_encoding_del_archivo_leido(self, tmp_path, monkeypatch):
        m = self._ingerir(tmp_path, monkeypatch)
        assert len(m.sha256) == 64
        assert m.encoding in {"cp1252", "latin-1"}
        assert m.filas == 16


class TestVentanaDeCobertura:
    """El denominador llega a 2035 y el numerador a 2023. La diferencia no es cero.

    Sin recortar, el `fillna(0)` del join publica años futuros con «cero suicidios» y
    tasa 0,0. Un cero dentro de la ventana significa «no hubo muertes»; fuera significa
    «no hay dato». Publicar lo segundo como lo primero es inventar una serie.
    """

    def _tablas(self):
        poblacion = pd.DataFrame({
            "comuna_cut": ["05101"] * 4,
            "anio": [2020, 2021, 2022, 2023],
            "poblacion": [100_000] * 4,
        })
        agregado = pd.DataFrame({
            "comuna_cut": ["05101", "05101"],
            "anio": [2020, 2021],
            "casos": [12, 15],
        })
        return agregado, poblacion

    def test_descarta_los_anios_sin_numerador(self):
        agregado, poblacion = self._tablas()
        gold, meta = tasas_comunales(agregado, poblacion, "SUICIDIO", k=1)
        assert sorted(gold["anio"].unique()) == [2020, 2021]
        assert meta["cobertura"]["anios_cobertura"] == [2020, 2021]
        assert meta["cobertura"]["filas_denominador_descartadas"] == 2

    def test_no_publica_tasa_cero_en_anios_futuros(self):
        agregado, poblacion = self._tablas()
        gold, _ = tasas_comunales(agregado, poblacion, "SUICIDIO", k=1)
        assert not (gold["anio"] > 2021).any(), "2022 y 2023 no tienen numerador"

    def test_dentro_de_la_ventana_el_cero_si_se_conserva(self):
        # Una comuna sin muertes en un año cubierto debe aparecer con 0, no desaparecer.
        poblacion = pd.DataFrame({
            "comuna_cut": ["05101", "05102"],
            "anio": [2020, 2020],
            "poblacion": [100_000, 50_000],
        })
        agregado = pd.DataFrame({"comuna_cut": ["05101"], "anio": [2020], "casos": [12]})
        gold, _ = tasas_comunales(agregado, poblacion, "SUICIDIO", k=1)
        sin_muertes = gold[gold["comuna_cut"] == "05102"]
        assert len(sin_muertes) == 1
        assert int(sin_muertes["casos"].iloc[0]) == 0

    def test_la_ventana_se_puede_forzar(self):
        agregado, poblacion = self._tablas()
        gold, meta = tasas_comunales(
            agregado, poblacion, "SUICIDIO", k=1, anios_cobertura=(2020, 2023)
        )
        assert sorted(gold["anio"].unique()) == [2020, 2021, 2022, 2023]
        assert meta["cobertura"]["anios_cobertura"] == [2020, 2023]


MUESTRA_POBLACION_CADENA = FIXTURES / "ine_proyecciones" / "muestra_cadena.csv"


class TestCadenaCompleta:
    """ingest → silver → gold con AMBAS fuentes reales, sin sustitutos.

    Hasta ahora los tests de gold usaban un CSV de población escrito a mano con tres
    columnas, cuando `normalizar_poblacion` produce seis. Todo el tramo silver-población →
    gold quedaba sin proteger: si el normalizador renombrara una columna o cambiara el
    tipo de `comuna_cut`, estos tests habrían seguido verdes. Es la misma familia de
    A-004 y A-009 — el test confirmando el supuesto del autor en vez de la realidad.

    Los dos fixtures tampoco se podían encadenar: no compartían un solo año. Por eso
    `muestra_cadena.csv` existe y está hecho para calzar con `muestra_latin1.csv`.
    """

    @pytest.fixture()
    def cadena(self):
        from obsm.ingest.ine_proyecciones import IneProyecciones
        from obsm.transform.silver import normalizar_poblacion

        defs, rep_d = normalizar_defunciones(DeisDefunciones().preparar(MUESTRA))
        pob, rep_p = normalizar_poblacion(
            IneProyecciones().preparar(MUESTRA_POBLACION_CADENA)
        )
        agregado = agregar_defunciones(defs, "SUICIDIO", dimensiones=["comuna_cut", "anio"])
        gold, meta = tasas_comunales(agregado, pob, "SUICIDIO", k=1)
        return {"defs": defs, "pob": pob, "agregado": agregado,
                "gold": gold, "meta": meta, "rep_d": rep_d, "rep_p": rep_p}

    def test_numerador_y_denominador_comparten_la_grilla(self, cadena):
        assert cadena["rep_d"]["tope_edad"] == cadena["rep_p"]["tope_edad"]
        assert set(cadena["defs"]["comuna_cut"]) - {"99999"} <= set(cadena["pob"]["comuna_cut"])

    def test_no_se_pierde_ningun_caso_sin_declararlo(self, cadena):
        # La suma tiene que cerrar: lo que entra es lo que sale más lo declarado perdido.
        entran = int(cadena["agregado"]["casos"].sum())
        salen = int(cadena["gold"]["casos"].sum())
        perdidos = cadena["meta"]["cobertura"]["casos_sin_denominador"]
        assert entran == salen + perdidos, "hay casos evaporándose en el join"

    def test_el_centinela_sin_denominador_se_declara(self, cadena):
        cob = cadena["meta"]["cobertura"]
        assert cob["casos_sin_denominador"] == 1
        assert cob["areas_sin_denominador"] == ["99999"]

    def test_la_tasa_sale_del_calculo_a_mano(self, cadena):
        # Santiago 2022: 3 suicidios sobre 84.000 habitantes (3.000 x 2 sexos x 14 edades).
        fila = cadena["gold"].query("comuna_cut == '13101' and anio == 2022").iloc[0]
        assert int(fila["casos"]) == 3
        assert int(fila["poblacion"]) == 84_000
        assert fila["tasa_cruda"] == pytest.approx(3 / 84_000 * 100_000)

    def test_poblacion_cero_da_tasa_indefinida_y_no_cero(self, cadena):
        # A-009 dentro de la cadena: Antártica no tiene habitantes en el fixture.
        # Un 0,0 se leería como «no hubo muertes»; lo correcto es «no se puede dividir».
        ant = cadena["gold"].query("comuna_cut == '12202'")
        assert len(ant) > 0
        assert ant["tasa_cruda"].isna().all()

    def test_una_comuna_sin_muertes_aparece_con_cero_y_no_desaparece(self, cadena):
        # Distinto del caso anterior: acá sí hay gente, y no hubo muertes.
        iquique = cadena["gold"].query("comuna_cut == '01101' and anio == 2022").iloc[0]
        assert int(iquique["casos"]) == 0
        assert iquique["tasa_cruda"] == 0.0

    def test_la_procedencia_llega_hasta_gold(self, cadena):
        for col in ("source_id", "pipeline_version", "fecha_calculo", "agrupador"):
            assert col in cadena["gold"].columns

    def test_el_suavizado_encoge_mas_a_la_comuna_chica(self, cadena):
        # Coyhaique (8.400 hab) tiene 2 casos: tasa cruda enorme y poco peso local.
        # Santiago (84.000 hab) tiene 3: menos ruido, más peso local.
        g = cadena["gold"].query("anio == 2022").set_index("comuna_cut")
        assert g.loc["11101", "peso_local_eb"] < g.loc["13101", "peso_local_eb"]
        assert g.loc["11101", "tasa_suavizada_eb"] < g.loc["11101", "tasa_cruda"]


class TestContratoDelFixtureDePoblacion:
    """El CSV de población escrito a mano no puede divergir del artefacto real."""

    def test_sus_columnas_existen_en_la_salida_real(self):
        from obsm.ingest.ine_proyecciones import IneProyecciones
        from obsm.transform.silver import normalizar_poblacion

        a_mano = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        real, _ = normalizar_poblacion(
            IneProyecciones().preparar(MUESTRA_POBLACION_CADENA)
        )
        faltan = set(a_mano.columns) - set(real.columns)
        assert not faltan, (
            f"el fixture a mano usa columnas que `normalizar_poblacion` ya no produce: "
            f"{faltan}. O se corrige el fixture, o los tests que lo usan están validando "
            f"contra algo que no existe."
        )

    def test_el_cut_es_string_de_cinco_digitos_en_ambos(self):
        from obsm.ingest.ine_proyecciones import IneProyecciones
        from obsm.transform.silver import normalizar_poblacion

        a_mano = pd.read_csv(POBLACION, dtype={"comuna_cut": str})
        real, _ = normalizar_poblacion(
            IneProyecciones().preparar(MUESTRA_POBLACION_CADENA)
        )
        assert a_mano["comuna_cut"].str.len().eq(5).all()
        assert real["comuna_cut"].str.len().eq(5).all()


class TestAvpp:
    """Años de vida potencial perdidos: se calculan en silver porque necesitan la edad."""

    def test_suma_los_aportes_a_mano(self, silver):
        from obsm.transform.silver import agregar_avpp

        df, _ = silver
        av = agregar_avpp(df, "SUICIDIO").set_index(["comuna_cut", "anio"])
        # Santiago 2022: muertes a los 34, 41 y 19 -> (80-34)+(80-41)+(80-19) = 146
        assert av.loc[("13101", 2022), "avpp"] == pytest.approx(146.0)
        # Valparaíso 2021: una muerte a los 51 -> 29
        assert av.loc[("05101", 2021), "avpp"] == pytest.approx(29.0)

    def test_una_muerte_sobre_el_limite_no_resta(self, silver):
        from obsm.indicators.tasas import avpp

        # El aporte se trunca en 0: morir a los 90 no "devuelve" diez años.
        assert avpp([90]) == 0.0
        assert avpp([20, 70, 90]) == pytest.approx(70.0)

    def test_las_muertes_sin_edad_se_cuentan_aparte(self):
        from obsm.transform.silver import agregar_avpp

        df = pd.DataFrame({
            "comuna_cut": ["05101"] * 2, "anio": [2020] * 2,
            "edad_anios": [40.0, float("nan")], "es_suicidio": [True, True],
        })
        av = agregar_avpp(df, "SUICIDIO")
        # Tratar la edad ausente como 0 afirmaría que murió al nacer, y como 80 que
        # murió justo en el límite. Ninguna de las dos es un dato.
        assert av["avpp"].iloc[0] == pytest.approx(40.0)
        assert int(av["casos_sin_edad"].iloc[0]) == 1


class TestEstandarizacionEnGold:
    def _tablas(self):
        # Dos comunas con el MISMO número de muertes y población, pero estructuras
        # etarias opuestas: sin estandarizar se ven iguales, estandarizadas no.
        pob = pd.DataFrame({
            "comuna_cut": ["05101", "05101", "05102", "05102"],
            "anio": [2020] * 4,
            "grupo_edad": ["20-24", "80+", "20-24", "80+"],
            "poblacion": [90_000, 10_000, 10_000, 90_000],
        })
        ag = pd.DataFrame({
            "comuna_cut": ["05101", "05102"],
            "anio": [2020, 2020],
            "grupo_edad": ["80+", "80+"],
            "casos": [20, 20],
        })
        return ag, pob

    def test_la_tasa_cruda_no_distingue_pero_la_estandarizada_si(self):
        ag, pob = self._tablas()
        gold, _ = tasas_comunales(ag, pob, "SUICIDIO", k=1)
        g = gold.set_index("comuna_cut")
        assert g.loc["05101", "tasa_cruda"] == pytest.approx(g.loc["05102", "tasa_cruda"])
        # La comuna joven concentra sus muertes en un grupo pequeño: su tasa específica
        # en 80+ es nueve veces mayor, y estandarizar lo revela.
        assert g.loc["05101", "tasa_estandarizada"] > g.loc["05102", "tasa_estandarizada"]

    def test_no_descarta_el_grupo_abierto(self):
        # Si el estándar no estuviera colapsado a 80+, este grupo se caería y la tasa
        # saldría calculada sin adultos mayores, sin ningún error visible.
        ag, pob = self._tablas()
        gold, _ = tasas_comunales(ag, pob, "SUICIDIO", k=1)
        assert (gold["grupos_edad_descartados"] == 0).all()
        assert (gold["tasa_estandarizada"] > 0).all()

    def test_poblacion_cero_da_estandarizada_indefinida_y_no_cero(self):
        pob = pd.DataFrame({
            "comuna_cut": ["05101"], "anio": [2020],
            "grupo_edad": ["40-44"], "poblacion": [0],
        })
        ag = pd.DataFrame({"comuna_cut": [], "anio": [], "grupo_edad": [], "casos": []})
        gold, _ = tasas_comunales(ag, pob, "SUICIDIO", k=1, anios_cobertura=(2020, 2020))
        assert gold["tasa_estandarizada"].isna().all(), (
            "un 0,0 se lee como «no hubo muertes»; acá significa «no hay a quién dividir»"
        )

    def test_el_intervalo_no_baja_de_cero(self):
        ag, pob = self._tablas()
        gold, _ = tasas_comunales(ag, pob, "SUICIDIO", k=1)
        assert (gold["ic95_inferior"].dropna() >= 0).all(), "una tasa negativa no existe"


class TestSupresionDeDerivadas:
    """Todo lo que permita reconstruir el conteo suprimido se suprime con él."""

    def _gold(self):
        from obsm.transform.silver import agregar_avpp

        defs, _ = normalizar_defunciones(DeisDefunciones().preparar(MUESTRA))
        from obsm.ingest.ine_proyecciones import IneProyecciones
        from obsm.transform.silver import normalizar_poblacion
        pob, _ = normalizar_poblacion(
            IneProyecciones().preparar(MUESTRA_POBLACION_CADENA)
        )
        ag = agregar_defunciones(defs, "SUICIDIO",
                                 dimensiones=["comuna_cut", "anio", "grupo_edad"])
        av = agregar_avpp(defs, "SUICIDIO")
        return tasas_comunales(ag, pob, "SUICIDIO", avpp=av, k=10)

    @pytest.mark.parametrize("col", [
        "tasa_cruda", "tasa_estandarizada", "ic95_inferior", "ic95_superior", "avpp",
    ])
    def test_ninguna_derivada_sobrevive_a_la_supresion(self, col):
        gold, _ = self._gold()
        suprimidas = gold[gold["suprimido"]]
        assert suprimidas[col].isna().all(), (
            f"{col} permite reconstruir el conteo suprimido"
        )

    def test_el_avpp_es_el_caso_mas_sensible(self):
        """Con un solo caso, AVPP revela la edad exacta del fallecido.

        El aporte es 80 − edad, así que un AVPP de 61 en una celda de una muerte dice
        que la persona tenía 19 años. Es el dato más identificable de toda la salida y
        por eso no puede quedar fuera de la supresión.
        """
        gold, _ = self._gold()
        una_muerte = gold[gold["casos"] == 1]
        assert len(una_muerte) == 0 or una_muerte["avpp"].isna().all()
