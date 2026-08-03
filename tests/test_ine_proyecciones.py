"""Tests del ingestor de proyecciones INE, el denominador de toda tasa.

Un defecto acá no produce un número raro en una columna: desplaza todas las tasas del
proyecto a la vez, y en la misma dirección, que es la clase de error que no se nota
mirando el resultado.
"""

from pathlib import Path

import pytest

from obsm.errors import SchemaDriftError
from obsm.ingest.ine_proyecciones import IneProyecciones

FIXTURE = Path(__file__).parent / "fixtures" / "ine_proyecciones" / "muestra_estructura_real.csv"


@pytest.fixture()
def bronze():
    return IneProyecciones().preparar(FIXTURE)


class TestFormatoAncho:
    """El archivo trae una columna por año; la grilla útil tiene una fila por año."""

    def test_el_melt_multiplica_las_filas_por_los_anios(self, bronze):
        assert len(bronze) == 72  # 24 filas de detalle x 3 años

    def test_los_anios_salen_como_numero_y_no_como_nombre_de_columna(self, bronze):
        assert sorted(bronze["anio"].unique()) == [2002, 2003, 2004]
        assert bronze["anio"].dtype == "Int64"

    def test_la_poblacion_no_se_mezcla_entre_anios(self, bronze):
        # Iquique, hombres, 40 años: 2100 / 2110 / 2121 en el fixture.
        fila = bronze[
            (bronze["comuna_cut_fuente"] == "1101")
            & (bronze["sexo"] == "hombre")
            & (bronze["edad_anios"] == 40)
        ].sort_values("anio")
        assert fila["poblacion"].tolist() == [2100, 2110, 2121]


class TestTerritorio:
    """El ingestor NO resuelve territorio: solo garantiza no haber roto el código."""

    def test_conserva_el_cut_tal_como_viene_sin_rellenar(self, bronze):
        # Rellenar es trabajo de silver (docs/02-ARQUITECTURA.md, tabla de capas).
        cuts = set(bronze["comuna_cut_fuente"])
        assert "1101" in cuts, "no debe venir ya rellenado a 01101"
        assert "13120" in cuts

    def test_el_cut_es_string_y_nunca_paso_por_entero(self, bronze):
        assert bronze["comuna_cut_fuente"].map(type).eq(str).all()
        largos = set(bronze["comuna_cut_fuente"].str.len())
        assert largos == {4, 5}, f"largos inesperados: {largos}"

    def test_silver_es_quien_lo_completa(self, bronze):
        from obsm.territorio import formatear_cut_comuna

        assert formatear_cut_comuna(bronze["comuna_cut_fuente"].iloc[0]) in {
            "01101",
            "13120",
            "11101",
        }
        assert formatear_cut_comuna("1101") == "01101"

    def test_lee_los_nombres_con_tilde(self, bronze):
        nombres = set(bronze["comuna_nombre"])
        assert "Ñuñoa" in nombres
        assert "Coyhaique" in nombres


class TestEdadYSexo:
    def test_marca_el_grupo_abierto_de_80(self, bronze):
        # 80 no es la edad 80: es «80 y más». Tratarlo como edad simple infla la tasa
        # del tramo mayor, porque reparte población de muchas edades en una sola.
        abiertos = bronze[bronze["edad_es_grupo_abierto"]]
        assert set(abiertos["edad_anios"]) == {80}
        assert not bronze[bronze["edad_anios"] == 40]["edad_es_grupo_abierto"].any()

    def test_traduce_los_codigos_de_sexo(self, bronze):
        assert set(bronze["sexo"]) == {"hombre", "mujer"}

    def test_un_codigo_de_sexo_nuevo_es_cambio_de_esquema(self, tmp_path):
        # Esta fuente solo publica 1 y 2. Un 9 aparecido de la nada hay que decidirlo,
        # no contarlo en silencio dentro de "desconocido".
        malo = tmp_path / "malo.csv"
        malo.write_bytes(
            b"Region,Nombre Region,Provincia,Nombre Provincia,Comuna,Nombre Comuna,"
            b"Sexo (1=Hombre 2=Mujer),Edad,Poblacion 2002\n"
            b"1,Tarapaca,11,Iquique,1101,Iquique,9,40,100\n"
        )
        with pytest.raises(SchemaDriftError, match="sexo"):
            IneProyecciones().preparar(malo)


class TestContratoDeEsquema:
    def test_falla_si_desaparecen_las_columnas_de_poblacion(self, tmp_path):
        # El cambio más probable de esta fuente y el más silencioso: sin esta
        # comprobación el melt devolvería una tabla vacía y el denominador sería cero.
        malo = tmp_path / "sin_poblacion.csv"
        malo.write_bytes(
            b"Region,Nombre Region,Provincia,Nombre Provincia,Comuna,Nombre Comuna,"
            b"Sexo (1=Hombre 2=Mujer),Edad,Habitantes 2002\n"
            b"1,Tarapaca,11,Iquique,1101,Iquique,1,40,100\n"
        )
        with pytest.raises(SchemaDriftError, match="poblaci"):
            IneProyecciones().preparar(malo)

    def test_falla_si_no_hay_columna_de_sexo(self, tmp_path):
        malo = tmp_path / "sin_sexo.csv"
        malo.write_bytes(b"Comuna,Edad,Poblacion 2002\n1101,40,100\n")
        with pytest.raises(SchemaDriftError, match="sexo"):
            IneProyecciones().preparar(malo)

    def test_tolera_el_acento_y_la_caja_en_el_encabezado(self, tmp_path):
        # `Poblacion`, `Población` y `POBLACION` son la misma columna: el INE cambia
        # acento y caja entre entregas sin cambiar el contenido.
        variante = tmp_path / "acentuado.csv"
        variante.write_bytes(
            "Region,Nombre Region,Provincia,Nombre Provincia,Comuna,Nombre Comuna,"
            "Sexo (1=Hombre 2=Mujer),Edad,Población 2002\n"
            "1,Tarapacá,11,Iquique,1101,Iquique,1,40,100\n".encode("latin-1")
        )
        df = IneProyecciones().preparar(variante)
        assert df["anio"].tolist() == [2002]
        assert df["poblacion"].tolist() == [100]

    def test_declara_las_columnas_que_silver_necesita(self, bronze):
        for col in ("anio", "comuna_cut_fuente", "sexo", "edad_anios", "poblacion"):
            assert col in bronze.columns


class TestCoberturaTemporal:
    """A-008: la cobertura empieza en 2002 y el ingestor no inventa años."""

    def test_no_rellena_anios_ausentes(self, bronze):
        # El fixture solo tiene 2002-2004. Si apareciera un 2001 con población cero,
        # sería una comuna sin habitantes en vez de un año sin dato.
        assert bronze["anio"].min() == 2002
        assert bronze["poblacion"].notna().all()

    def test_la_poblacion_puede_ser_cero_pero_nunca_nula_ni_negativa(self, bronze):
        """Un cero es un dato; un nulo es la ausencia de dato. No son lo mismo.

        La primera versión de este test afirmaba que la población nunca es cero y pasaba,
        porque el fixture no tenía ceros: validaba el supuesto contra sí mismo. El archivo
        real trae 8.060 celdas en cero (0,42 %), todas correctas — en Antártica no vive
        ninguna mujer de 73 años, y eso es un hecho, no un dato faltante. Ver A-009.

        Lo que sí debe cumplirse es que el cero venga de la fuente y no de una coerción
        fallida, que es lo que distingue «nadie» de «no se pudo leer».
        """
        assert bronze["poblacion"].notna().all(), "un nulo acá es lectura fallida"
        assert (bronze["poblacion"] >= 0).all()
        assert (bronze["poblacion"] == 0).any(), (
            "el fixture debe contener celdas en cero: son el 0,42 % del archivo real"
        )


class TestIntegracionConSilver:
    def test_el_total_nacional_se_puede_reconstruir_por_anio(self, bronze):
        # Es la operación que hace gold para obtener el denominador de una tasa nacional.
        totales = bronze.groupby("anio")["poblacion"].sum()
        assert (
            totales[2002]
            == sum([1469, 2100, 615] * 2 + [3200, 5400, 1810] * 2 + [90, 140, 33] * 2) + 2
        )  # +2 = Antártica
        assert totales[2003] > totales[2002]

    def test_la_grilla_no_tiene_duplicados(self, bronze):
        clave = ["comuna_cut_fuente", "sexo", "edad_anios", "anio"]
        assert not bronze.duplicated(subset=clave).any(), (
            "una clave duplicada en el denominador multiplica población al unir"
        )


def test_esta_registrado_en_la_cli():
    from obsm.ingest import INGESTORES

    assert INGESTORES["ine_proyecciones"] is IneProyecciones


class TestNormalizacionASilver:
    """bronze → silver: acá sí se resuelve territorio y se agrupa la edad."""

    @pytest.fixture()
    def silver(self, bronze):
        from obsm.transform.silver import normalizar_poblacion

        return normalizar_poblacion(bronze)

    def test_aqui_si_se_rellena_el_cut(self, silver):
        df, _ = silver
        assert "01101" in set(df["comuna_cut"]), "silver es quien completa el cero"
        assert all(len(c) == 5 for c in df["comuna_cut"])

    def test_la_region_sale_del_cut_completo(self, silver):
        df, _ = silver
        # Sin el zfill previo, Iquique daría region "11" en vez de "01".
        iquique = df[df["comuna_cut"] == "01101"]
        assert set(iquique["region_cut"]) == {"01"}

    def test_usa_el_tope_del_pipeline_y_no_el_general(self, silver):
        from obsm.indicators.tasas import TOPE_EDAD_PIPELINE

        df, rep = silver
        assert rep["tope_edad"] == TOPE_EDAD_PIPELINE == 80
        assert "80+" in set(df["grupo_edad"])
        assert "85+" not in set(df["grupo_edad"])

    def test_no_pierde_ni_inventa_poblacion(self, bronze, silver):
        df, rep = silver
        assert int(df["poblacion"].sum()) == int(bronze["poblacion"].sum())
        assert rep["poblacion_total"] == int(bronze["poblacion"].sum())

    def test_conserva_las_celdas_en_cero(self, silver):
        # A-009: un cero es «no vive nadie», no un faltante. Filtrarlas cambiaría el
        # denominador de las comunas diminutas justo donde más frágil es la tasa.
        df, rep = silver
        assert rep["celdas_poblacion_cero"] > 0
        assert (df["poblacion"] == 0).any()

    def test_la_grilla_es_unica_por_dimension(self, silver):
        df, _ = silver
        clave = ["comuna_cut", "anio", "sexo", "grupo_edad"]
        assert not df.duplicated(subset=clave).any(), (
            "una clave repetida en el denominador multiplica población al unir"
        )

    def test_el_territorio_queda_validado_contra_la_dpa(self, silver):
        _, rep = silver
        assert rep["cut_invalidos"] == 0
        assert rep["cut_fuera_de_dpa"] == 0


class TestGrillaCompartidaConElNumerador:
    """Numerador y denominador tienen que caer en la misma grilla o la tasa miente."""

    def test_defunciones_y_poblacion_usan_los_mismos_grupos_de_edad(self):
        from obsm.ingest.deis_defunciones import DeisDefunciones
        from obsm.transform.silver import normalizar_defunciones, normalizar_poblacion

        muestra = Path(__file__).parent / "fixtures" / "deis_defunciones" / "muestra_latin1.csv"
        defs, rep_d = normalizar_defunciones(DeisDefunciones().preparar(muestra))
        pob, rep_p = normalizar_poblacion(IneProyecciones().preparar(FIXTURE))

        assert rep_d["tope_edad"] == rep_p["tope_edad"], (
            "si los topes divergen, la estandarización descarta grupos en silencio"
        )
        # Ninguno de los dos puede emitir un grupo por encima del tope. Es lo que rompía
        # la estandarización: el numerador llegando a 85+ contra un denominador que
        # termina en 80+.
        for lado, df in (("defunciones", defs), ("poblacion", pob)):
            assert "85+" not in set(df["grupo_edad"]), f"{lado} se pasó del tope"

        # Y para una misma edad, ambos lados tienen que dar exactamente la misma etiqueta.
        from obsm.indicators.tasas import grupo_quinquenal

        for edad in (0, 4, 5, 39, 79, 80, 84, 97):
            etiqueta = grupo_quinquenal(edad, tope=rep_p["tope_edad"])
            assert grupo_quinquenal(edad, tope=rep_d["tope_edad"]) == etiqueta
        assert grupo_quinquenal(97, tope=rep_p["tope_edad"]) == "80+"
