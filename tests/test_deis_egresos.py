"""Tests de egresos hospitalarios DEIS.

Esta fuente aporta el eslabón que faltaba entre el control ambulatorio (REM) y la muerte
(defunciones): la hospitalización. Dos cosas de acá se publican como serie —egresos por
trastorno mental y egresos por lesión autoinfligida—, y las dos dependen de leer la
columna correcta. La primera clase de este archivo es de regresión pura: si alguien
«simplifica» el ingestor para leer solo `DIAG1`, la serie de intento suicida se vuelve
cero sin que falle nada.
"""

from pathlib import Path

import pandas as pd
import pytest

from obsm.cie10 import LESION_AUTOINFLIGIDA_MORBILIDAD, TRASTORNOS_MENTALES
from obsm.errors import SchemaDriftError
from obsm.ingest.deis_egresos import (
    TRAMOS_DECENALES,
    TRAMOS_QUINQUENALES,
    DeisEgresos,
    clasificar_esquema_edad,
    normalizar_grupo_edad,
)

DIR = Path(__file__).parent / "fixtures" / "deis_egresos"
F2023 = DIR / "muestra_estructura_real_2023.csv"
F2021 = DIR / "muestra_2021_quinquenal.csv"
F2024 = DIR / "muestra_2024_utf8_corrupto.csv"
F2015 = DIR / "muestra_2015_supresion_sin_comuna.csv"


@pytest.fixture()
def bronze():
    return DeisEgresos().preparar(F2023)


class TestLaLesionAutoinfligidaVivEnDiag2:
    """Regresión de A-004, que se repite idéntica en egresos.

    En el archivo real de 2023, sobre 1.612.267 egresos: X60-X84 aparece 0 veces en
    `DIAG1` y 7.683 en `DIAG2`. Leer solo el diagnóstico principal devuelve cero
    intentos suicidas **sin lanzar ningún error**.
    """

    def test_diag1_solo_no_encuentra_ninguna_lesion_autoinfligida(self, bronze):
        principal = bronze["diagnostico_principal"]
        assert principal.map(LESION_AUTOINFLIGIDA_MORBILIDAD.contiene).sum() == 0

    def test_diag2_si_las_encuentra(self, bronze):
        externa = bronze["causa_externa"]
        assert externa.map(LESION_AUTOINFLIGIDA_MORBILIDAD.contiene).sum() == 2

    def test_la_causa_derivada_las_encuentra(self, bronze):
        """`causa_cie10` es la columna que debe usar `transform/`: sirve para ambos grupos."""
        causa = bronze["causa_cie10"]
        assert causa.map(LESION_AUTOINFLIGIDA_MORBILIDAD.contiene).sum() == 2
        assert causa.map(TRASTORNOS_MENTALES.contiene).sum() == 3

    def test_los_trastornos_mentales_viven_en_diag1_y_no_en_diag2(self, bronze):
        assert bronze["diagnostico_principal"].map(TRASTORNOS_MENTALES.contiene).sum() == 3
        assert bronze["causa_externa"].map(TRASTORNOS_MENTALES.contiene).sum() == 0

    def test_la_derivacion_no_esconde_egresos_psiquiatricos(self, bronze):
        """Verificado disjunto en el archivo real: ninguna fila con F en DIAG1 trae DIAG2.

        Si dejara de serlo, la causa derivada taparía egresos psiquiátricos con su causa
        externa y el conteo de F caería sin aviso.
        """
        con_f = bronze[bronze["diagnostico_principal"].map(TRASTORNOS_MENTALES.contiene)]
        assert (con_f["causa_externa"] == "").all()
        assert (con_f["origen_causa_cie10"] == "principal").all()

    def test_el_intento_suicida_conserva_su_diagnostico_principal(self, bronze):
        """La derivación no borra el T: queda en su propia columna, que es la lesión real."""
        auto = bronze[bronze["causa_externa"].map(LESION_AUTOINFLIGIDA_MORBILIDAD.contiene)]
        assert set(auto["diagnostico_principal"]) == {"T424", "T509"}
        assert (auto["origen_causa_cie10"] == "externa").all()


class TestSupresionDeOrigen:
    """El `*` de DEIS es supresión, no dato faltante. Ver A-022."""

    def test_la_fila_suprimida_queda_marcada(self, bronze):
        assert bronze["suprimido_en_origen"].sum() == 1

    def test_ninguna_comuna_llega_como_asterisco(self, bronze):
        """Un `"*"` en la llave territorial revienta el join o, peor, crea una comuna."""
        assert "*" not in set(bronze["comuna_cut_fuente"].dropna())
        assert bronze.loc[bronze["suprimido_en_origen"], "comuna_cut_fuente"].isna().all()

    def test_la_fila_suprimida_conserva_diagnostico_y_condicion(self, bronze):
        """DEIS enmascara la demografía, no el diagnóstico: la fila sirve para el total país."""
        fila = bronze[bronze["suprimido_en_origen"]].iloc[0]
        assert fila["diagnostico_principal"] == "O820"
        assert fila["condicion_egreso"] == "vivo"
        assert fila["dias_estada"] == 2

    def test_el_nucleo_clinico_sobrevive_a_la_supresion(self, bronze):
        """Diagnóstico, causa externa y días de estada nunca se enmascaran.

        Es lo que mantiene utilizable a la fila suprimida: sin territorio ni demografía,
        todavía suma al total nacional por diagnóstico.
        """
        sup = bronze[bronze["suprimido_en_origen"]]
        assert (sup["diagnostico_principal"] != "").all()
        assert sup["dias_estada"].notna().all()
        assert sup["condicion_egreso"].notna().all()

    def test_si_la_supresion_alcanza_al_diagnostico_falla(self, tmp_path):
        crudo = F2023.read_bytes().decode("latin-1")
        crudo = crudo.replace(";O820;;2;1", ";*;;2;1")
        ruta = tmp_path / "diag_suprimido.csv"
        ruta.write_bytes(crudo.encode("latin-1"))
        with pytest.raises(SchemaDriftError, match="núcleo clínico"):
            DeisEgresos().preparar(ruta)

    def test_los_totales_comunales_no_suman_el_total_nacional(self, bronze):
        """Consecuencia obligada de la supresión, y no es un error del pipeline."""
        assert bronze["comuna_cut_fuente"].notna().sum() < len(bronze)

    def test_dos_patrones_de_enmascaramiento_en_un_archivo_es_deriva(self, tmp_path):
        """Un solo patrón por archivo está bien; dos conviviendo hay que mirarlos.

        No se exige un conjunto **fijo** de columnas —cambió entre 2019 y 2023 y exigirlo
        dejaría fuera media serie—, sino que el archivo sea coherente consigo mismo.
        """
        crudo = F2023.read_bytes().decode("latin-1").splitlines()
        # Fila enmascarada solo en sexo y edad, conservando comuna: otro patrón.
        crudo.append(
            "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS;*;"
            "*;No se identifica con alguna etnia;Chileno;13101;Santiago;13;"
            "Metropolitana de Santiago;1;FONASA;2023;J189;;3;1"
        )
        ruta = tmp_path / "dos_patrones.csv"
        ruta.write_bytes(("\n".join(crudo) + "\n").encode("latin-1"))
        with pytest.raises(SchemaDriftError, match="combinaciones distintas"):
            DeisEgresos().preparar(ruta)

    def test_el_patron_antiguo_que_deja_la_comuna_se_acepta(self):
        """Hasta 2019 el `*` enmascara la región y deja la comuna. Debe ingerirse igual."""
        df = DeisEgresos().preparar(F2015)
        assert df["suprimido_en_origen"].sum() == 3
        # La comuna sobrevive a la supresión antigua (salvo la de residencia ignorada).
        supr = df[df["suprimido_en_origen"]]
        assert set(supr["comuna_cut_fuente"].dropna()) == {"15101", "12101"}
        assert supr["region_cut_fuente"].isna().all()

    def test_la_supresion_antigua_es_inefectiva_y_queda_registrado(self):
        """Los dos primeros dígitos del CUT comunal *son* la región enmascarada.

        El proyecto no lo explota; el test existe para que el hecho no se pierda.
        """
        df = DeisEgresos().preparar(F2015)
        fila = df[df["comuna_cut_fuente"] == "15101"].iloc[0]
        assert fila["suprimido_en_origen"]
        assert pd.isna(fila["region_cut_fuente"])
        assert fila["comuna_cut_fuente"][:2] == "15"  # la región oculta, a la vista


class TestElAnioTambienVieneSuprimido:
    """La supresión se lleva `ANO_EGRESO`, en los seis años que la tienen.

    Es el peor de los efectos de A-022: sin año, un `groupby("anio")` descarta el 8 % de
    los egresos de 2023 **en silencio**. El ingestor lo imputa porque cada archivo es de
    un solo año, pero lo declara: un dato imputado que se lee como leído es peor que uno
    ausente.
    """

    def test_el_anio_se_imputa_y_queda_marcado(self, bronze):
        assert bronze["anio"].notna().all()
        assert bronze["anio_imputado"].sum() == 1
        imputada = bronze[bronze["anio_imputado"]].iloc[0]
        assert imputada["anio"] == 2023
        assert imputada["suprimido_en_origen"]

    def test_ninguna_fila_con_datos_queda_marcada_como_imputada(self, bronze):
        assert not bronze.loc[~bronze["suprimido_en_origen"], "anio_imputado"].any()

    def test_sin_supresion_no_hay_imputacion(self):
        """2021 no tiene supresión: nada que imputar."""
        df = DeisEgresos().preparar(F2021)
        assert not df["anio_imputado"].any()
        assert (df["anio"] == 2021).all()

    def test_con_varios_anios_en_el_archivo_no_se_imputa(self, tmp_path):
        """Imputar sobre un archivo multianual sería inventar el período.

        Hoy DEIS publica un archivo por año, pero el ingestor no puede depender de eso:
        si algún día entrega una serie junta, tiene que dejar el año nulo, no repartirlo.
        """
        crudo = F2023.read_bytes().decode("latin-1").splitlines()
        crudo.append(crudo[1].replace(";2023;", ";2022;"))
        ruta = tmp_path / "multianual.csv"
        ruta.write_bytes(("\n".join(crudo) + "\n").encode("latin-1"))
        df = DeisEgresos().preparar(ruta)
        assert df["anio"].isna().sum() == 1
        assert not df["anio_imputado"].any()

    def test_en_2015_tambien_se_pierde_el_anio(self):
        df = DeisEgresos().preparar(F2015)
        assert df["anio_imputado"].sum() == 3
        assert (df["anio"] == 2015).all()


class TestResidenciaIgnorada:
    """`99999`/`Ignorada` no es supresión: es que no se sabe dónde vive la persona."""

    def test_la_comuna_ignorada_no_llega_como_comuna(self, bronze):
        """Sin esto aparece una comuna «99999» que no existe en ninguna agregación."""
        assert "99999" not in set(bronze["comuna_cut_fuente"].dropna())
        assert bronze["residencia_ignorada"].sum() == 1

    def test_la_region_ignorada_tampoco(self, bronze):
        assert "99" not in set(bronze["region_cut_fuente"].dropna())

    def test_ignorada_y_suprimida_son_marcas_distintas(self, bronze):
        """La fila ignorada conserva sexo y edad; la suprimida no."""
        ign = bronze[bronze["residencia_ignorada"]].iloc[0]
        assert not ign["suprimido_en_origen"]
        assert ign["sexo"] == "hombre"
        assert ign["grupo_edad_norm"] == "60_a_69"

    def test_en_2015_una_fila_puede_ser_ignorada_y_suprimida_a_la_vez(self):
        df = DeisEgresos().preparar(F2015)
        fila = df[df["residencia_ignorada"]].iloc[0]
        assert fila["suprimido_en_origen"]
        assert pd.isna(fila["comuna_cut_fuente"])


class TestDerivaEntreAnios:
    """15, 16 o 18 columnas según el año, y un codebook distinto en 2021."""

    def test_el_archivo_de_2021_se_ingiere_pese_a_no_traer_etnia(self):
        df = DeisEgresos().preparar(F2021)
        assert len(df) == 6
        assert "etnia" not in df.columns

    def test_el_sexo_numerico_de_2021_se_traduce(self):
        df = DeisEgresos().preparar(F2021)
        assert list(df["sexo"][:3]) == ["hombre", "mujer", "hombre"]

    def test_el_sexo_sin_codebook_no_se_inventa(self):
        """`3` y `9` no tienen codebook publicado: van a `no_especificado`, no a una
        categoría inventada, y el valor crudo sobrevive."""
        df = DeisEgresos().preparar(F2021)
        fila = df[df["sexo_fuente"] == "3"].iloc[0]
        assert fila["sexo"] == "no_especificado"

    def test_un_sexo_desconocido_falla_ruidosamente(self, tmp_path):
        crudo = F2023.read_bytes().decode("latin-1").replace(";HOMBRE;20 a 29;", ";VARON;20 a 29;")
        ruta = tmp_path / "sexo_raro.csv"
        ruta.write_bytes(crudo.encode("latin-1"))
        with pytest.raises(SchemaDriftError, match="SEXO"):
            DeisEgresos().preparar(ruta)

    def test_el_nombre_truncado_de_la_primera_columna_se_reconoce(self, bronze):
        """Desde 2019 llega `..._SALU` sin la D; antes llegaba completo."""
        assert "pertenencia_snss" in bronze.columns
        df21 = DeisEgresos().preparar(F2021)
        assert "pertenencia_snss" in df21.columns

    def test_los_dos_esquemas_etarios_se_distinguen(self, bronze):
        assert set(bronze["esquema_grupo_edad"]) == {"decenal"}
        assert set(DeisEgresos().preparar(F2021)["esquema_grupo_edad"]) == {"quinquenal"}

    def test_un_tramo_etario_nuevo_falla_ruidosamente(self, tmp_path):
        crudo = F2023.read_bytes().decode("latin-1").replace(";20 a 29;", ";adulto joven;")
        ruta = tmp_path / "tramo_raro.csv"
        ruta.write_bytes(crudo.encode("latin-1"))
        with pytest.raises(SchemaDriftError, match="GRUPO_EDAD"):
            DeisEgresos().preparar(ruta)


class TestArchivoDe2024ConAcentosDestruidos:
    """Regresión de A-021: DEIS publicó 2024 con 1.199.605 caracteres irrecuperables."""

    def test_se_ingiere_pese_a_los_caracteres_de_reemplazo(self):
        df = DeisEgresos().preparar(F2024)
        assert len(df) == 4

    def test_los_codigos_territoriales_estan_intactos(self):
        """Los acentos se perdieron en las glosas; el CUT no los tiene y sobrevive.

        Es la razón por la que la llave del proyecto es `comuna_cut` y nunca el nombre.
        """
        df = DeisEgresos().preparar(F2024)
        assert list(df["comuna_cut_fuente"]) == ["05101", "13120", "08101", "16101"]

    def test_los_tramos_etarios_se_normalizan_pese_al_dano(self):
        """`90 y m�s` y `menor de un a�o` deben clasificar igual que si vinieran sanos."""
        df = DeisEgresos().preparar(F2024)
        assert set(df["grupo_edad_norm"]) == {"10_a_19", "20_a_29", "90_y_mas", "menor_de_1_anio"}
        assert set(df["esquema_grupo_edad"]) == {"decenal"}

    def test_las_glosas_danadas_no_se_reparan_a_ciegas(self):
        """No hay forma de saber qué letra había. Adivinarla sería inventar un dato."""
        df = DeisEgresos().preparar(F2024)
        assert "�" in df["comuna_nombre"].iloc[0]


class TestNormalizacionDeTramos:
    """Casos calculados a mano, no con el output del propio código."""

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("1 a 9", "1_a_9"),
            ("10 a 19", "10_a_19"),
            ("90 y más", "90_y_mas"),
            ("menor de un año", "menor_de_1_anio"),
            ("90 y m�s", "90_y_mas"),
            ("menor de un a�o", "menor_de_1_anio"),
            ("1 A 4 AÑOS", "1_a_4"),
            ("85 A MAS", "85_y_mas"),
            ("menor a 7 días", "menor_a_7_dias"),
            ("7 A 27 DIAS", "7_a_27_dias"),
            ("28 DIAS A 2 MES", "28_dias_a_2_meses"),
            ("2 MESES A MENOS DE 1 AÑO", "2_meses_a_1_anio"),
            ("*", ""),
        ],
    )
    def test_normalizar_grupo_edad(self, texto, esperado):
        assert normalizar_grupo_edad(texto) == esperado

    def test_los_doce_tramos_decenales_reales_estan_cubiertos(self):
        """Los 12 valores distintos que trae el archivo de 2023, contados en el original."""
        reales = [
            "menor de un año",
            "1 a 9",
            "10 a 19",
            "20 a 29",
            "30 a 39",
            "40 a 49",
            "50 a 59",
            "60 a 69",
            "70 a 79",
            "80 a 89",
            "90 y más",
        ]
        assert {normalizar_grupo_edad(t) for t in reales} <= TRAMOS_DECENALES
        assert len(reales) == 11  # los 12 del archivo incluyen el centinela '*'

    def test_los_veintidos_tramos_quinquenales_reales_estan_cubiertos(self):
        reales = [
            "menor a 7 días",
            "7 A 27 DIAS",
            "28 DIAS A 2 MES",
            "2 MESES A MENOS DE 1 AÑO",
            "1 A 4 AÑOS",
            "5 A 9 AÑOS",
            "10 A 14 AÑOS",
            "15 A 19 AÑOS",
            "20 A 24 AÑOS",
            "25 A 29 AÑOS",
            "30 A 34 AÑOS",
            "35 A 39 AÑOS",
            "40 A 44 AÑOS",
            "45 A 49 AÑOS",
            "50 A 54 AÑOS",
            "55 A 59 AÑOS",
            "60 A 64 AÑOS",
            "65 A 69 AÑOS",
            "70 A 74 AÑOS",
            "75 A 79 AÑOS",
            "80 A 84 AÑOS",
            "85 A MAS",
        ]
        assert len(reales) == 22
        assert {normalizar_grupo_edad(t) for t in reales} <= TRAMOS_QUINQUENALES

    def test_los_dos_esquemas_no_son_colapsables_arriba_de_79(self):
        """Quinquenal cierra en `85 y más` y decenal en `90 y más`.

        No es un detalle: significa que ninguna serie por edad puede cruzar 2021 en los
        tramos superiores, ni siquiera agregando. El test existe para que nadie escriba
        ese colapso creyendo que es posible.
        """
        assert "85_y_mas" in TRAMOS_QUINQUENALES
        assert "85_y_mas" not in TRAMOS_DECENALES
        assert "90_y_mas" in TRAMOS_DECENALES
        assert "90_y_mas" not in TRAMOS_QUINQUENALES

    def test_clasificar_esquema_mixto(self):
        assert clasificar_esquema_edad({"1_a_9", "80_a_84"}) == "mixto"
        assert clasificar_esquema_edad(set()) == "desconocido"


class TestContratoBasico:
    def test_el_cut_conserva_el_cero_a_la_izquierda(self, bronze):
        """A diferencia de defunciones, esta fuente sí lo trae. Leerlo como int lo destruye."""
        assert "01101" in set(bronze["comuna_cut_fuente"])

    def test_condicion_egreso_segun_el_diccionario_del_zip(self, bronze):
        assert bronze["condicion_egreso"].value_counts()["fallecido"] == 1
        assert bronze["condicion_egreso"].value_counts()["vivo"] == 8

    def test_dias_estada_es_entero_nullable(self, bronze):
        assert bronze["dias_estada"].dtype == "Int64"
        assert bronze["anio"].dtype == "Int64"

    def test_falta_una_columna_requerida(self, tmp_path):
        crudo = F2023.read_bytes().decode("latin-1").replace("DIAG1;", "DIAGNOSTICO_X;", 1)
        ruta = tmp_path / "sin_diag1.csv"
        ruta.write_bytes(crudo.encode("latin-1"))
        with pytest.raises(SchemaDriftError, match="diagnostico_principal"):
            DeisEgresos().preparar(ruta)

    def test_la_region_de_nuble_llega_como_16(self, bronze):
        """Ñuble existe desde 2018; sus comunas aparecen bajo 08 en series anteriores."""
        chillan = bronze[bronze["comuna_cut_fuente"] == "16101"].iloc[0]
        assert chillan["region_cut_fuente"] == "16"

    def test_no_hay_columnas_duplicadas(self, bronze):
        assert not bronze.columns.duplicated().any()

    def test_el_ingestor_esta_registrado(self):
        from obsm.ingest import INGESTORES

        assert INGESTORES["deis_egresos"] is DeisEgresos


class TestUnEgresoNoEsUnaPersona:
    """La advertencia central de esta fuente, fijada como test para que no se olvide."""

    def test_las_filas_son_egresos_y_pueden_repetir_a_la_misma_persona(self, bronze):
        """No hay identificador de paciente: es imposible deduplicar, y por eso esta
        fuente no puede usarse como prevalencia."""
        assert not any(
            c in bronze.columns for c in ("rut", "id_paciente", "folio", "identificador")
        )
        assert len(bronze) == 9
        # Dos egresos de Valparaíso que podrían ser la misma persona reingresando.
        assert (bronze["comuna_cut_fuente"] == "05101").sum() == 2


def test_no_se_publica_desglose_por_metodo(bronze):
    """CLAUDE.md §2.4: X60-X84 individuales no salen nunca, tampoco en morbilidad."""
    from obsm.cie10 import es_publicable

    assert es_publicable("LESION_AUTOINFLIGIDA_MORBILIDAD", "agrupador")
    assert not es_publicable("LESION_AUTOINFLIGIDA_MORBILIDAD", "codigo")
    # El bronze conserva el código individual (es materia prima); el veto es de publicación.
    assert set(bronze.loc[bronze["causa_externa"] != "", "causa_externa"]) == {"X610", "X619"}


def test_los_tres_fixtures_tienen_encodings_distintos_a_proposito():
    """2023 y 2021 son latin-1; 2024 es UTF-8 válido con el daño ya dentro."""
    assert F2023.read_bytes().decode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        F2023.read_bytes().decode("utf-8")
    assert F2024.read_bytes().decode("utf-8")
    assert pd.notna(pd.NA) is False  # centinela de sanidad de pandas
