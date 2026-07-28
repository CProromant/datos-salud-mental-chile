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

    def test_los_valores_no_se_fuerzan_a_entero(self, bronze):
        """El archivo trae algunos conteos con decimales y no se redondean (A-010).

        Forzar a entero haría una de dos cosas malas: reventar la ingesta del año
        —le pasó a 2014— o alterar el dato en silencio. Redondear es decisión de la
        capa que publica, que además puede declararlo.
        """
        fraccion = bronze[bronze["valor"] % 1 != 0]
        assert len(fraccion), "el fixture debe traer el caso feo de 2014"
        assert 123.55 in set(fraccion["valor"]), "el valor se redondeó o se perdió"
        assert (bronze["valor"].dropna() >= 0).all()

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


class TestSilverDelRem:
    """bronze → silver: territorio, período semestral y grilla etaria."""

    @pytest.fixture()
    def silver(self, bronze):
        from obsm.transform.silver import normalizar_rem

        return normalizar_rem(bronze)

    def test_aqui_si_se_rellena_el_cut(self, silver):
        df, rep = silver
        assert "09108" in set(df["comuna_cut"])
        assert all(len(c) == 5 for c in df["comuna_cut"])
        assert rep["cut_invalidos"] == 0

    def test_el_periodo_es_semestral_y_va_en_iso(self, silver):
        df, rep = silver
        assert rep["periodos"] == ["2023-06", "2023-12"]
        assert set(df["periodo"]) == {"2023-06", "2023-12"}

    def test_los_grupos_del_rem_calzan_con_la_grilla_del_proyecto(self, silver):
        """Coincidencia afortunada: el REM ya usa quinquenios con abierto en 80.

        Es la misma grilla que impone el denominador del INE, así que no hay que
        armonizar nada. Si algún año cambiara, `grupos_edad_no_reconocidos` lo delata.
        """
        df, rep = silver
        assert rep["grupos_edad_no_reconocidos"] == []
        assert {"00-04", "05-09"} <= set(df["grupo_edad"])

    def test_las_filas_de_total_se_marcan_y_no_se_llaman_desconocido(self, silver):
        """`total` y `desconocido` dicen cosas opuestas y confundirlas duplica gente.

        Una fila de total son todos los tramos juntos; una `desconocido` sería gente de
        la que no se sabe la edad. Sumar el total con el detalle cuenta a cada persona
        dos veces, y con el mismo nombre nadie lo notaría.
        """
        df, _ = silver
        totales = df[df["es_total_etario"]]
        assert set(totales["grupo_edad"]) == {"total"}
        assert "desconocido" not in set(df["grupo_edad"])

    def test_el_total_no_se_puede_sumar_con_el_detalle(self, silver):
        # Santiago, diciembre: el total de «ambos sexos» es 50 y el detalle etario suma
        # 30. Son la misma gente contada de dos formas, no 80 personas.
        df, _ = silver
        stgo = df[(df["comuna_cut"] == "13101") & (df["etiqueta"] == "DEPRESIÓN LEVE")]
        total = stgo[stgo["es_total_etario"] & (stgo["sexo"] == "ambos")]["valor"].sum()
        detalle = stgo[~stgo["es_total_etario"]]["valor"].sum()
        assert total == 50
        assert detalle == 30
        assert total != detalle, "el detalle no cubre todos los tramos; no son sumables"

    def test_agrega_establecimientos_dentro_de_la_comuna(self, silver):
        # El establecimiento no es unidad publicable: identificar el CESFAM con dos casos
        # de un diagnóstico es identificar a las personas.
        df, _ = silver
        assert "establecimiento_deis" not in df.columns


class TestGrupoEdadRem:
    @pytest.mark.parametrize("texto,esperado", [
        ("0 a 4 años", "00-04"),
        ("5 a 9 años", "05-09"),
        ("75 a 79 años", "75-79"),
        ("80 y más años", "80+"),
        ("80 y mas años", "80+"),
        ("10 - 14 años", "10-14"),
    ])
    def test_traduce_las_formas_conocidas(self, texto, esperado):
        from obsm.transform.silver import grupo_edad_rem

        assert grupo_edad_rem(texto) == esperado

    @pytest.mark.parametrize("texto", ["", "adultos", "de 20 a 30", None, "0-4"])
    def test_lo_que_no_reconoce_queda_desconocido_y_no_adivinado(self, texto):
        from obsm.transform.silver import grupo_edad_rem

        # Adivinar movería personas de un tramo a otro sin dejar rastro.
        assert grupo_edad_rem(texto) == "desconocido"


class TestGoldDelRem:
    """La tabla publicable: conteos, no tasas."""

    @pytest.fixture()
    def gold(self, bronze):
        from obsm.transform.gold import tabla_rem
        from obsm.transform.silver import normalizar_rem

        silver, _ = normalizar_rem(bronze)
        return tabla_rem(silver, k=1)

    def test_no_devuelve_tasas(self, gold):
        """Deliberado. El denominador correcto es la población INSCRITA en APS.

        Dividir por la proyección comunal del INE incluiría a quien se atiende en el
        sistema privado y daría un número que parece cobertura y no lo es. Mientras
        `fonasa_inscritos` no exista, publicar conteos es lo honesto.
        """
        df, meta = gold
        assert "personas" in df.columns
        assert not any(c.startswith("tasa") for c in df.columns)
        assert any("no tasas" in a for a in meta["advertencias"])

    def test_usa_el_total_etario_y_no_lo_mezcla_con_el_detalle(self, gold):
        # Santiago tiene 50 en el total y 30 en el detalle: son la misma gente.
        # Si se mezclaran, saldrían 80 personas que no existen.
        df, meta = gold
        stgo = df[(df["comuna_cut"] == "13101") & (df["etiqueta"] == "DEPRESIÓN LEVE")]
        assert int(stgo["personas"].iloc[0]) == 50
        assert meta["origen_de_la_cifra"] == "total etario"

    def test_no_suma_ambos_sexos_con_hombres_y_mujeres(self, gold):
        # Las tres columnas describen la misma población. Sumarlas duplica a cada persona.
        df, _ = gold
        junio = df[(df["comuna_cut"] == "09108") & (df["periodo"] == "2023-06")
                   & (df["etiqueta"] == "DEPRESIÓN LEVE")]
        assert int(junio["personas"].iloc[0]) == 4

    def test_advierte_que_los_periodos_no_se_suman(self, gold):
        # Población bajo control es un stock: sumar junio y diciembre cuenta dos veces
        # a quien siguió en tratamiento todo el año.
        _, meta = gold
        assert any("stock" in a for a in meta["advertencias"])

    def test_la_procedencia_llega_a_cada_fila(self, gold):
        df, _ = gold
        for col in ("source_id", "pipeline_version", "fecha_calculo"):
            assert col in df.columns

    def test_suprime_con_el_umbral_de_actividad(self, bronze):
        from obsm.quality import K_SUPRESION_ACTIVIDAD
        from obsm.transform.gold import tabla_rem
        from obsm.transform.silver import normalizar_rem

        silver, _ = normalizar_rem(bronze)
        df, meta = tabla_rem(silver)
        assert meta["supresion"]["k"] == K_SUPRESION_ACTIVIDAD == 5
        visibles = df[~df["suprimido"]]
        assert not visibles["personas"].between(1, 4).any()
