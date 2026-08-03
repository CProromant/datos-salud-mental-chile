"""Tests del maestro de establecimientos y de la composición comunal de la APS.

Esta fuente existe para responder una sola pregunta: **quién administra la atención primaria
de cada comuna**. De eso depende que un denominador de cobertura signifique algo, así que un
filtro mal puesto acá no produce una tabla rara sino una cobertura creíble y falsa.
"""

from pathlib import Path

import pytest

from obsm.errors import ReconciliationError, SchemaDriftError
from obsm.ingest.deis_establecimientos import DeisEstablecimientos
from obsm.transform.silver import componer_aps_comunal

FIXTURE = (
    Path(__file__).parent / "fixtures" / "deis_establecimientos" / "muestra_estructura_real.csv"
)


@pytest.fixture()
def bronze():
    return DeisEstablecimientos().preparar(FIXTURE)


@pytest.fixture()
def aps(bronze):
    return componer_aps_comunal(bronze)


class TestGlosasDuplicadas:
    """El archivo usa dos grafías simultáneas para lo mismo. Filtrar por una pierde datos."""

    def test_las_dos_grafias_de_primer_nivel_son_el_mismo_nivel(self, bronze):
        # «Primer Nivel» (2.478 en el archivo real) y «Primario» (534) conviven.
        # Filtrar por una sola descarta el 18 % de la atención primaria.
        iqq = bronze[bronze["comuna_cut_fuente"] == "1101"]
        assert set(iqq["nivel_atencion_fuente"]) == {"Primer Nivel", "Primario"}
        assert set(iqq["nivel_atencion"]) == {"primario"}

    def test_las_dos_cajas_de_vigente_son_el_mismo_estado(self, bronze):
        # «Vigente en Operación Habitual» y «Vigente en operación habitual» son iguales;
        # comparar por igualdad exacta descarta 209 establecimientos vigentes.
        iqq = bronze[bronze["comuna_cut_fuente"] == "1101"]
        assert iqq["estado_funcionamiento"].nunique() == 2
        assert iqq["vigente"].all()

    def test_un_cerrado_no_queda_como_vigente(self, bronze):
        cerrado = bronze[bronze["establecimiento_deis"] == "113999"].iloc[0]
        assert not cerrado["vigente"]

    def test_un_nivel_nuevo_detiene_la_ingesta(self, tmp_path):
        crudo = FIXTURE.read_text(encoding="utf-8")
        destino = tmp_path / "nivel_raro.csv"
        destino.write_text(crudo.replace(";Primer Nivel;", ";Cuarto Nivel;", 1), encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="cuarto nivel"):
            DeisEstablecimientos().preparar(destino)


class TestCodigoCorrecto:
    """Hay dos columnas de código y solo una calza con el padrón de FONASA."""

    def test_usa_el_codigo_vigente_y_no_el_antiguo(self, bronze):
        cods = set(bronze["establecimiento_deis"])
        assert "116201" in cods, "el código vigente (116201) es el que calza con FONASA"
        assert "16-201" not in cods, "el código antiguo tiene otro formato y da 0 coincidencias"

    def test_falla_si_desaparece_la_columna_de_codigo_vigente(self, tmp_path):
        crudo = FIXTURE.read_text(encoding="utf-8")
        destino = tmp_path / "sin_codigo.csv"
        destino.write_text(
            crudo.replace("EstablecimientoCodigo;", "OtroNombre;", 1), encoding="utf-8"
        )
        with pytest.raises(SchemaDriftError, match="EstablecimientoCodigo"):
            DeisEstablecimientos().preparar(destino)


class TestComposicionAps:
    """La pregunta que hace usable —o no— al denominador de `fonasa_inscritos`."""

    def test_cuenta_solo_aps_publica_vigente(self, aps):
        _, rep = aps
        # De 12 filas: se excluyen la clínica privada, el consultorio cerrado y el
        # hospital de segundo nivel de Lautaro.
        assert rep["aps_publica_vigente"] == 9

    def test_la_clinica_privada_no_cuenta_como_aps_publica(self, aps):
        tabla, _ = aps
        toco = tabla[tabla["comuna_cut"] == "02301"].iloc[0]
        # Tocopilla tiene una clínica privada y un hospital del Servicio de Salud.
        assert toco["aps_total"] == 1
        assert toco["aps_municipal"] == 0

    def test_identifica_la_comuna_sin_aps_municipal(self, aps):
        tabla, _ = aps
        for cut in ("02301", "05201", "11101"):  # Tocopilla, Isla de Pascua, Coyhaique
            fila = tabla[tabla["comuna_cut"] == cut].iloc[0]
            assert fila["fraccion_municipal"] == 0, f"{cut} no tiene APS municipal"

    def test_identifica_la_comuna_mixta(self, aps):
        tabla, _ = aps
        # Quirihue: una posta municipal y el hospital del Servicio de Salud. Es el caso
        # que explica los 11 inscritos de A-015.
        q = tabla[tabla["comuna_cut"] == "16201"].iloc[0]
        assert q["aps_total"] == 2
        assert q["aps_municipal"] == 1
        assert q["aps_servicio_salud"] == 1
        assert q["fraccion_municipal"] == 0.5

    def test_identifica_la_comuna_enteramente_municipal(self, aps):
        tabla, _ = aps
        iqq = tabla[tabla["comuna_cut"] == "01101"].iloc[0]
        assert iqq["fraccion_municipal"] == 1

    def test_el_hospital_de_segundo_nivel_no_entra(self, aps):
        tabla, _ = aps
        # Lautaro tiene un hospital de segundo nivel y un CECOSF municipal. Solo el
        # segundo es APS; contar el hospital diría que Lautaro es mixta y no lo es.
        lau = tabla[tabla["comuna_cut"] == "09118"].iloc[0]
        assert lau["aps_total"] == 1
        assert lau["fraccion_municipal"] == 1

    def test_el_reporte_clasifica_las_comunas(self, aps):
        _, rep = aps
        assert rep["comunas_solo_municipal"] == 3  # Iquique, Santiago, Lautaro
        assert rep["comunas_mixtas"] == 1  # Quirihue
        assert rep["comunas_sin_aps_municipal"] == 3  # Tocopilla, Isla de Pascua, Coyhaique
        assert rep["cut_invalidos"] == 0

    def test_falla_si_no_queda_ninguna_aps(self, bronze):
        vacio = bronze.copy()
        vacio["sistema_salud"] = "privado"
        with pytest.raises(ReconciliationError, match="APS pública vigente"):
            componer_aps_comunal(vacio)
