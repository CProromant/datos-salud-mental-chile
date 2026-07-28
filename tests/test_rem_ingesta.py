"""Tests del ingestor del REM Serie P, sección P6.

Es la fuente que da lo que la mortalidad no puede: en el archivo de defunciones la
depresión son once muertes al año en todo Chile; acá son más de cien mil personas en
tratamiento. Por eso vale la pena que se lea bien.
"""

from pathlib import Path

import pytest

from obsm.errors import SchemaDriftError
from obsm.ingest.rem_poblacion_control import RemPoblacionControl

MUESTRA = Path(__file__).parent / "fixtures" / "rem_salud_mental" / "muestra_serie_p.txt"

#: Mapeo mínimo, con la forma del que genera `obsm rem mapear`.
MAPEO = {
    "seccion": "P6",
    "anios": {
        2023: {
            "diccionario": "demo.xlsm",
            "conceptos": {
                "P6221600": {"grupo": "TRASTORNOS DEL HUMOR", "concepto": "DEPRESIÓN LEVE"},
                "P6227500": {"grupo": "TRASTORNOS DEL HUMOR", "concepto": "DEPRESIÓN MODERADA"},
                "P6230800": {"grupo": "SUICIDIO", "concepto": "IDEACIÓN"},
            },
            "columnas": {
                "COL01": {"grupo_edad": "", "sexo": "ambos"},
                "COL02": {"grupo_edad": "", "sexo": "hombres"},
                "COL03": {"grupo_edad": "", "sexo": "mujeres"},
                "COL04": {"grupo_edad": "0 a 4 años", "sexo": "hombres"},
                "COL05": {"grupo_edad": "0 a 4 años", "sexo": "mujeres"},
                "COL06": {"grupo_edad": "5 a 9 años", "sexo": "hombres"},
                "COL07": {"grupo_edad": "5 a 9 años", "sexo": "mujeres"},
            },
        }
    },
    "no_legibles": ["2009: diccionario ilegible"],
}


@pytest.fixture()
def bronze():
    return RemPoblacionControl(mapeo=MAPEO).preparar(MUESTRA)


class TestFiltradoPorSeccion:
    """Solo el 7,8 % del archivo real es P6. Filtrar al leer no es optimización."""

    def test_descarta_las_filas_de_otras_secciones(self, bronze):
        # El fixture trae una fila P4190600 y otra P1220100 con valores 99 y 88.
        assert bronze["codigo_prestacion"].str.startswith("P6").all()
        assert not bronze["valor"].isin([99, 88]).any(), (
            "se colaron filas de otra sección del REM-P"
        )

    def test_conserva_todas_las_filas_de_p6(self, bronze):
        assert set(bronze["codigo_prestacion"]) == {"P6221600", "P6227500", "P6230800"}

    def test_falla_si_ninguna_fila_es_de_la_seccion(self, tmp_path):
        # Si DEIS recodificara las prestaciones, el ingestor debe detenerse y no
        # entregar una tabla vacía que parezca «ese mes no hubo atenciones».
        malo = tmp_path / "otra_seccion.txt"
        malo.write_text(
            "Mes;IdServicio;Ano;IdEstablecimiento;CodigoPrestacion;IdRegion;IdComuna;Col01\n"
            "12;21;2023;121355;P9990000;9;09108;5\n", encoding="utf-8")
        with pytest.raises(SchemaDriftError, match="ninguna fila"):
            RemPoblacionControl(mapeo=MAPEO).preparar(malo)


class TestFormatoLargo:
    def test_las_columnas_genericas_se_vuelven_filas(self, bronze):
        # Cada fila del archivo con 7 columnas llenas produce hasta 7 filas largas.
        una = bronze[(bronze["codigo_prestacion"] == "P6221600") & (bronze["mes"] == 6)]
        assert set(una["columna"]) == {f"COL0{i}" for i in range(1, 8)}

    def test_las_celdas_vacias_no_se_vuelven_ceros(self, bronze):
        """Una celda en blanco es «no se reportó», no «cero personas».

        En el fixture, P6227500 de junio tiene COL04 y COL05 vacías. Si se leyeran
        como cero, se estaría afirmando que no hay niños de 0 a 4 en control, cuando
        lo que hay es ausencia de dato.
        """
        junio = bronze[(bronze["codigo_prestacion"] == "P6227500") & (bronze["mes"] == 6)]
        assert set(junio["columna"]) == {"COL01", "COL02", "COL03", "COL06", "COL07"}

    def test_pega_el_concepto_desde_el_mapeo(self, bronze):
        fila = bronze[bronze["codigo_prestacion"] == "P6230800"].iloc[0]
        assert fila["grupo"] == "SUICIDIO"
        assert fila["concepto"] == "IDEACIÓN"

    def test_pega_la_dimension_de_cada_columna(self, bronze):
        cols = bronze.drop_duplicates("columna").set_index("columna")
        assert cols.loc["COL01", "sexo"] == "ambos"
        assert cols.loc["COL01", "grupo_edad_fuente"] == ""
        assert cols.loc["COL05", "grupo_edad_fuente"] == "0 a 4 años"
        assert cols.loc["COL05", "sexo"] == "mujeres"


class TestTerritorioYTipos:
    def test_el_cut_llega_sin_rellenar(self, bronze):
        # Rellenar el cero a la izquierda es resolver territorio: le toca a silver.
        assert "09108" in set(bronze["comuna_cut_fuente"])
        assert bronze["comuna_cut_fuente"].map(type).eq(str).all()

    def test_los_valores_son_enteros(self, bronze):
        assert bronze["valor"].dtype == "Int64"
        assert (bronze["valor"] >= 0).all()

    def test_conserva_los_dos_cortes_semestrales(self, bronze):
        """La Serie P NO es mensual: se reporta en junio y diciembre.

        El plan asumía «serie mensual comunal». Sobre el archivo real de 2023 los
        únicos meses presentes son 6 y 12, porque población bajo control es un stock
        con corte semestral, no un flujo mensual.
        """
        assert set(bronze["mes"].dropna()) == {6, 12}


class TestMapeoFaltante:
    def test_un_anio_sin_mapeo_falla_diciendo_cuales_hay(self, tmp_path):
        archivo = tmp_path / "2013.txt"
        archivo.write_text(
            "Mes;IdServicio;Ano;IdEstablecimiento;CodigoPrestacion;IdRegion;IdComuna;Col01\n"
            "12;21;2013;121355;P6221600;9;09108;5\n", encoding="utf-8")
        with pytest.raises(SchemaDriftError) as exc:
            RemPoblacionControl(mapeo=MAPEO).preparar(archivo)
        # El mensaje tiene que servir para actuar: qué años hay y por qué faltan los otros.
        assert "2023" in str(exc.value)
        assert "no_legibles" in str(exc.value) or "ilegible" in str(exc.value)

    def test_esta_registrado_en_la_cli(self):
        from obsm.ingest import INGESTORES

        assert INGESTORES["rem_salud_mental"] is RemPoblacionControl
