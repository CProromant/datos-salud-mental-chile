"""Tests del ingestor de población inscrita validada en APS municipal.

Es un denominador, así que sus defectos no producen una celda rara: mueven todas las
coberturas a la vez. Y trae la trampa más silenciosa que se ha encontrado en el proyecto
—un `0` que significa «esta comuna no tiene APS municipal»— así que los tests que la
custodian son de regresión y no se relajan.
"""

from pathlib import Path

import pandas as pd
import pytest

from obsm.errors import SchemaDriftError
from obsm.ingest.fonasa_inscritos import FonasaInscritos

FIXTURE = Path(__file__).parent / "fixtures" / "fonasa_inscritos" / "sinim_hpism_muestra.xls"


@pytest.fixture()
def bronze():
    return FonasaInscritos().preparar(FIXTURE)


def _celda(df, cut, anio):
    fila = df[(df["comuna_cut_fuente"] == cut) & (df["anio"] == anio)]
    assert len(fila) == 1, f"se esperaba una celda para {cut}/{anio}, hay {len(fila)}"
    return fila.iloc[0]


class TestFormato:
    """El archivo se llama .xls pero es XML; leerlo mal falla de formas creativas."""

    def test_lee_pese_al_salto_de_linea_antes_del_prologo_xml(self, bronze):
        # El cuerpo que sirve SINIM empieza con \n. Sin lstrip() esto es un ParseError.
        assert len(bronze) == 6 * 7  # 6 comunas x 7 años

    def test_el_melt_produce_una_fila_por_comuna_y_anio(self, bronze):
        assert sorted(bronze["anio"].unique()) == [2015, 2020, 2021, 2022, 2023, 2024, 2025]
        assert bronze["anio"].dtype == "Int64"

    def test_la_cabecera_se_busca_por_contenido_no_por_numero_de_fila(self, bronze):
        # Sobre la cabecera hay dos filas de glosa. Si se asumiera la fila 3 fija,
        # bastaría que SINIM agregue una línea para leer los años como comunas.
        assert "CODIGO" not in set(bronze["comuna_cut_fuente"])
        assert "Valores en miles de peso" not in set(bronze["comuna_nombre"])


class TestTerritorio:
    """El ingestor no resuelve territorio; solo garantiza no haber roto el código."""

    def test_conserva_el_cero_a_la_izquierda_pese_al_ss_type_number(self, bronze):
        # El nodo dice ss:Type="Number" pero el texto es "01402". Creerle al tipo
        # declarado es exactamente cómo 01402 se convierte en 1402.
        cuts = set(bronze["comuna_cut_fuente"])
        assert "01402" in cuts
        assert "1402" not in cuts

    def test_el_cut_es_texto_no_entero(self, bronze):
        assert bronze["comuna_cut_fuente"].map(type).eq(str).all()

    def test_conserva_los_nombres_con_tilde_y_enie(self, bronze):
        nombres = set(bronze["comuna_nombre"])
        assert "CAMIÑA" in nombres
        assert "SAN NICOLÁS" in nombres


class TestCentinelas:
    """Cuatro marcas no numéricas, cuatro significados distintos. Ninguna es cero."""

    @pytest.mark.parametrize(
        ("cut", "anio", "motivo"),
        [
            ("01101", 2023, "no_recepcionado"),
            ("01402", 2015, "costo_fijo"),
            ("02301", 2015, "sin_servicio_municipal"),
            ("01107", 2015, "no_aplica"),
        ],
    )
    def test_cada_marca_se_conserva_con_su_motivo(self, bronze, cut, anio, motivo):
        fila = _celda(bronze, cut, anio)
        assert fila["motivo_sin_dato"] == motivo
        assert pd.isna(fila["poblacion_inscrita"]), "un centinela no es un número"

    def test_una_marca_nueva_detiene_la_ingesta(self, tmp_path):
        # Si SINIM inventa una marca, significa algo. Adaptarse en silencio la contaría
        # como faltante y borraría comunas del denominador sin dejar rastro.
        crudo = FIXTURE.read_bytes().decode("utf-8")
        adulterado = crudo.replace(
            '<Data ss:Type="String">Costo Fijo</Data>',
            '<Data ss:Type="String">En Convenio</Data>',
            1,
        )
        destino = tmp_path / "marca_nueva.xls"
        destino.write_text(adulterado, encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="En Convenio"):
            FonasaInscritos().preparar(destino)

    def test_el_valor_crudo_sobrevive_para_poder_auditar(self, bronze):
        assert _celda(bronze, "01402", 2015)["valor_crudo"] == "Costo Fijo"


class TestCeroQueNoEsCero:
    """A-013: desde ~2019 SINIM escribe 0 donde antes escribía «Sin Servicio».

    El ingestor **no** resuelve esto —no infiere entre filas— pero sí tiene que dejar la
    evidencia intacta para que silver pueda. Si bronze perdiera el 0 o el centinela
    histórico, la corrección sería imposible aguas abajo.
    """

    def test_el_cero_llega_a_bronze_como_cero_y_no_como_faltante(self, bronze):
        fila = _celda(bronze, "02301", 2025)
        assert fila["poblacion_inscrita"] == 0
        assert fila["motivo_sin_dato"] == ""

    def test_el_centinela_historico_de_la_misma_comuna_sigue_disponible(self, bronze):
        # Tocopilla: «Sin Servicio» en 2015, 0 desde 2020. Es el par que permite
        # deducir que el 0 no es cero.
        assert _celda(bronze, "02301", 2015)["motivo_sin_dato"] == "sin_servicio_municipal"
        assert _celda(bronze, "02301", 2020)["poblacion_inscrita"] == 0


class TestCeldasDispersas:
    """SpreadsheetML omite las celdas vacías y numera la siguiente con ss:Index."""

    def test_honra_ss_index_y_no_corre_los_anios(self, bronze):
        # Isla de Pascua no trae celda para 2024: la siguiente declara ss:Index="5".
        # Leyendo las celdas en orden, el «No Recepcionado» de 2023 caería en 2024 y
        # todos los años posteriores quedarían desplazados un lugar.
        assert pd.isna(_celda(bronze, "05201", 2024)["poblacion_inscrita"])
        assert _celda(bronze, "05201", 2024)["motivo_sin_dato"] == ""
        assert _celda(bronze, "05201", 2023)["motivo_sin_dato"] == "no_recepcionado"
        assert _celda(bronze, "05201", 2022)["poblacion_inscrita"] == 8500
        assert _celda(bronze, "05201", 2015)["motivo_sin_dato"] == "sin_servicio_municipal"


class TestContrato:
    def test_falla_si_desaparece_la_cabecera(self, tmp_path):
        crudo = FIXTURE.read_bytes().decode("utf-8")
        destino = tmp_path / "sin_cabecera.xls"
        destino.write_text(crudo.replace(">CODIGO<", ">COD<"), encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="cabecera"):
            FonasaInscritos().preparar(destino)

    def test_falla_si_la_cabecera_no_declara_anios(self, tmp_path):
        crudo = FIXTURE.read_bytes().decode("utf-8")
        for a in ("2025", "2024", "2023", "2022", "2021", "2020", "2015"):
            crudo = crudo.replace(
                f'<Data ss:Type="String">{a}</Data>', '<Data ss:Type="String">x</Data>'
            )
        destino = tmp_path / "sin_anios.xls"
        destino.write_text(crudo, encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="año"):
            FonasaInscritos().preparar(destino)

    def test_las_columnas_requeridas_existen_antes_de_validar(self, bronze):
        for col in FonasaInscritos.columnas_requeridas:
            assert col in bronze.columns


class TestSilverResuelveElCero:
    """A-013: el `0` que en realidad es «esta comuna no tiene APS municipal».

    La reinterpretación necesita la serie completa de la comuna, así que vive en silver.
    Estos tests son de regresión: si alguna vez vuelven a pasar con el cero intacto, hay
    comunas publicando cobertura infinita.
    """

    @pytest.fixture()
    def silver(self, bronze):
        from obsm.transform.silver import normalizar_inscritos

        return normalizar_inscritos(bronze)

    def test_el_cero_de_una_comuna_sin_servicio_se_vuelve_nulo(self, silver):
        plata, _ = silver
        toco = plata[(plata["comuna_cut"] == "02301") & (plata["anio"] == 2025)].iloc[0]
        assert pd.isna(toco["poblacion_inscrita"]), (
            "Tocopilla declaró «Sin Servicio» en 2015; su 0 de 2025 es el mismo hecho"
        )
        assert toco["motivo_sin_dato"] == "sin_servicio_municipal_inferido"

    def test_el_motivo_inferido_se_distingue_del_declarado(self, silver):
        # Poder auditar cuál cero reinterpretamos nosotros y cuál marcó la fuente es la
        # diferencia entre una decisión documentada y un dato tocado a mano.
        plata, _ = silver
        motivos = set(plata["motivo_sin_dato"])
        assert "sin_servicio_municipal" in motivos  # lo declaró SINIM, en 2015
        assert "sin_servicio_municipal_inferido" in motivos  # lo dedujimos, desde 2020

    def test_no_toca_los_ceros_de_comunas_que_nunca_declararon_sin_servicio(self, bronze):
        from obsm.transform.silver import normalizar_inscritos

        # Camiña nunca dijo «Sin Servicio». Si su valor fuera 0, sería un 0 de verdad.
        alterado = bronze.copy()
        objetivo = (alterado["comuna_cut_fuente"] == "01402") & (alterado["anio"] == 2020)
        alterado.loc[objetivo, "poblacion_inscrita"] = 0
        plata, rep = normalizar_inscritos(alterado)
        fila = plata[(plata["comuna_cut"] == "01402") & (plata["anio"] == 2020)].iloc[0]
        assert fila["poblacion_inscrita"] == 0
        assert fila["motivo_sin_dato"] == ""
        assert rep["ceros_conservados"] >= 1

    def test_no_imputa_ningun_valor(self, silver):
        plata, rep = silver
        # 6 comunas x 7 años; lo que no es número queda nulo, nunca estimado.
        assert len(plata) == 42
        assert rep["celdas_con_dato"] + int(plata["poblacion_inscrita"].isna().sum()) == 42

    def test_el_reporte_deja_contabilidad_de_lo_que_se_toco(self, silver):
        _, rep = silver
        assert rep["comunas_sin_servicio_municipal"] == 2  # Tocopilla e Isla de Pascua
        assert rep["ceros_reinterpretados"] == 5  # los 0 de Tocopilla 2020-2025
        assert rep["cut_invalidos"] == 0

    def test_una_comuna_repetida_detiene_la_normalizacion(self, bronze):
        from obsm.errors import ReconciliationError
        from obsm.transform.silver import normalizar_inscritos

        # Un denominador con la comuna duplicada se suma solo al unir y hunde la cobertura.
        with pytest.raises(ReconciliationError, match="duplicad"):
            normalizar_inscritos(pd.concat([bronze, bronze], ignore_index=True))


class TestDenominadorImplausible:
    """A-015: comunas cuyo padrón municipal no describe a la comuna.

    Quirihue tiene once inscritos municipales sobre 12.244 habitantes, y los once son
    correctos: su único establecimiento municipal es una posta rural. Lo que se marca no
    es un valor malo sino un denominador que no corresponde al numerador del REM, que sí
    cuenta la actividad del establecimiento del Servicio de Salud.
    """

    @pytest.fixture()
    def caso(self):
        inscritos = pd.DataFrame(
            {
                "comuna_cut": ["16201", "16201", "01101", "02301"],
                "anio": [2014, 2025, 2025, 2025],
                "poblacion_inscrita": pd.array([9204, 33, 205125, None], dtype="Int64"),
            }
        )
        poblacion = pd.DataFrame(
            {
                "comuna_cut": ["16201", "16201", "01101", "02301"],
                "anio": [2014, 2025, 2025, 2025],
                "poblacion": [11800, 12244, 280000, 28369],
            }
        )
        return inscritos, poblacion

    def test_marca_la_celda_absurda_y_deja_en_paz_la_creible(self, caso):
        from obsm.quality import marcar_denominador_implausible

        marcado, _ = marcar_denominador_implausible(*caso)
        por_llave = marcado.set_index(["comuna_cut", "anio"])["denominador_implausible"]
        assert por_llave[("16201", 2025)]  # 33 sobre 12.244 habitantes
        assert not por_llave[("16201", 2014)]  # 9.204 sobre 11.800: creíble
        assert not por_llave[("01101", 2025)]

    def test_no_borra_ni_imputa_el_valor_marcado(self, caso):
        from obsm.quality import marcar_denominador_implausible

        marcado, _ = marcar_denominador_implausible(*caso)
        fila = marcado[(marcado["comuna_cut"] == "16201") & (marcado["anio"] == 2025)]
        assert fila["poblacion_inscrita"].iloc[0] == 33, "el dato original sobrevive"

    def test_una_celda_sin_dato_no_se_marca_como_implausible(self, caso):
        # Nulo y absurdo son cosas distintas: Tocopilla no tiene dato, no tiene un dato malo.
        from obsm.quality import marcar_denominador_implausible

        marcado, rep = marcar_denominador_implausible(*caso)
        fila = marcado[marcado["comuna_cut"] == "02301"]
        assert not fila["denominador_implausible"].iloc[0]
        assert rep["celdas_sin_poblacion_de_referencia"] == 1

    def test_el_reporte_cuenta_lo_marcado(self, caso):
        from obsm.quality import marcar_denominador_implausible

        _, rep = marcar_denominador_implausible(*caso)
        assert rep["celdas_implausibles"] == 1
        assert rep["comunas_implausibles"] == 1


MULTI = Path(__file__).parent / "fixtures" / "fonasa_inscritos" / "sinim_multivariable_muestra.xls"


class TestFormatoMultivariable:
    """Pedir varias variables devuelve bloques de años consecutivos, uno por variable.

    El año deja de identificar la columna: 2025 aparece cuatro veces. Sin el código de
    variable los cuatro valores caen sobre la misma llave y sobrevive el último.
    """

    @pytest.fixture()
    def bronze_multi(self):
        return FonasaInscritos().preparar(MULTI)

    def test_separa_las_cuatro_variables(self, bronze_multi):
        assert sorted(set(bronze_multi["variable_codigo"])) == [
            "HPISM",
            "HPV2064",
            "HPVM6",
            "HPVM64",
        ]
        assert len(bronze_multi) == 3 * 4 * 7  # 3 comunas x 4 variables x 7 años

    def test_no_colapsa_los_valores_del_mismo_anio(self, bronze_multi):
        # Quirihue 2025: total 33, tramos 4 / 24 / 3. Cuatro números distintos que sin
        # `variable_codigo` serían uno solo.
        q = bronze_multi[
            (bronze_multi["comuna_cut_fuente"] == "16201") & (bronze_multi["anio"] == 2025)
        ].set_index("variable_codigo")["poblacion_inscrita"]
        assert q["HPISM"] == 33
        assert q["HPVM6"] == 4
        assert q["HPV2064"] == 24
        assert q["HPVM64"] == 3

    def test_silver_se_queda_con_el_total_y_lo_declara(self, bronze_multi):
        from obsm.transform.silver import normalizar_inscritos

        plata, rep = normalizar_inscritos(bronze_multi)
        assert len(plata) == 3 * 7
        assert rep["variable"] == "HPISM"
        assert sorted(rep["variables_descartadas"]) == ["HPV2064", "HPVM6", "HPVM64"]

    def test_pedir_una_variable_ausente_falla_en_vez_de_devolver_vacio(self, bronze_multi):
        from obsm.errors import ReconciliationError
        from obsm.transform.silver import normalizar_inscritos

        with pytest.raises(ReconciliationError, match="HPXXX"):
            normalizar_inscritos(bronze_multi, variable="HPXXX")

    def test_la_variable_unica_sigue_leyendose(self, bronze):
        # El fixture de una sola variable escribe el nombre una vez y deja el resto de la
        # fila vacío. El arrastre hacia la derecha tiene que cubrir los dos casos.
        assert set(bronze["variable_codigo"]) == {"HPISM"}


class TestCoherenciaConTramos:
    """A-015: el padrón municipal no cubre a los beneficiarios FONASA de la comuna.

    **Ojo con lo que esto significa.** Los tramos NO son el desglose etario del total: el
    total son inscritos en APS *municipal* y los tramos son *beneficiarios* del seguro. Que
    el total quede por debajo no delata un error del dato —Quirihue tiene once inscritos
    municipales y los once son correctos— sino que la APS de esa comuna la presta un
    establecimiento del Servicio de Salud. Ver A-015 en docs/05-CALIDAD.md.
    """

    @pytest.fixture()
    def marcado(self):
        from obsm.quality import marcar_total_incoherente_con_tramos
        from obsm.transform.silver import normalizar_inscritos, resolver_cut

        b = FonasaInscritos().preparar(MULTI)
        total, _ = normalizar_inscritos(b)
        b["comuna_cut"], _ = resolver_cut(b["comuna_cut_fuente"])
        return marcar_total_incoherente_con_tramos(total, b)

    def test_detecta_la_comuna_sin_aps_municipal(self, marcado):
        df, _ = marcado
        # Quirihue 2024: 31 inscritos municipales y 499 + 4.045 + 1.589 = 6.133
        # beneficiarios. La comuna se atiende en un establecimiento del Servicio de Salud.
        fila = df[(df["comuna_cut"] == "16201") & (df["anio"] == 2024)].iloc[0]
        assert fila["total_menor_que_tramos"]
        assert fila["razon_tramos"] < 0.01

    def test_no_marca_la_comuna_sana(self, marcado):
        df, _ = marcado
        iqq = df[(df["comuna_cut"] == "01101") & (df["anio"] == 2024)].iloc[0]
        assert not iqq["total_menor_que_tramos"]
        # Donde la APS sí es municipal, el padrón cubre 1,15 a 1,36 veces los tramos.
        assert 1.1 < iqq["razon_tramos"] < 1.4

    def test_no_basta_por_si_solo_y_por_eso_hacen_falta_dos_chequeos(self, marcado):
        df, _ = marcado
        # Cuando los beneficiarios de la comuna también son pocos, la comparación entre
        # las dos variables no delata nada y solo la razón contra el INE lo hace.
        fila = df[(df["comuna_cut"] == "16201") & (df["anio"] == 2025)].iloc[0]
        assert not fila["total_menor_que_tramos"]
        assert fila["razon_tramos"] > 1

    def test_no_corrige_ningun_valor(self, marcado):
        df, _ = marcado
        fila = df[(df["comuna_cut"] == "16201") & (df["anio"] == 2024)].iloc[0]
        assert fila["poblacion_inscrita"] == 31, (
            "el 31 es correcto: son los inscritos del único establecimiento municipal"
        )

    def test_una_celda_sin_los_tres_tramos_no_se_compara(self, marcado):
        df, _ = marcado
        # Tocopilla: silver la anuló por A-013, así que no hay total que comparar.
        toco = df[(df["comuna_cut"] == "02301") & (df["anio"] == 2025)].iloc[0]
        assert not toco["total_menor_que_tramos"]

    def test_el_reporte_dice_donde_esta_el_problema(self, marcado):
        _, rep = marcado
        assert rep["tramos_faltantes"] == []
        assert rep["celdas_incoherentes"] >= 1
        assert 2024 in rep["anios_incoherentes"]
