"""Tests de la tabla de cobertura: personas en control por mil inscritos en la APS.

Es la primera tabla del proyecto que **divide dos fuentes distintas**, y ahí está todo el
riesgo: numerador y denominador pueden describir poblaciones diferentes sin que nada lo
advierta. Una cobertura de 397 por mil no se ve rota, se ve alarmante, e invita a
interpretarla. Estos tests custodian las tres razones por las que una celda no se publica.
"""

import pandas as pd
import pytest

from obsm.quality import refutar_denominador_con_numerador
from obsm.transform.gold import (
    DENOMINADOR_AUSENTE,
    DENOMINADOR_COMPLETO,
    DENOMINADOR_PARCIAL,
    tabla_cobertura,
)


def _rem(filas):
    """silver del REM: (comuna, periodo, etiqueta, personas)."""
    return pd.DataFrame(
        [
            {
                "comuna_cut": c,
                "periodo": p,
                "etiqueta": e,
                "etiqueta_norm": e,
                "valor": v,
                "es_total_etario": True,
                "sexo": "ambos",
            }
            for c, p, e, v in filas
        ]
    )


def _ins(filas, **cols):
    df = pd.DataFrame([{"comuna_cut": c, "anio": a, "poblacion_inscrita": v} for c, a, v in filas])
    df["poblacion_inscrita"] = df["poblacion_inscrita"].astype("Int64")
    for k, v in cols.items():
        df[k] = v
    return df


def _aps(filas):
    return pd.DataFrame([{"comuna_cut": c, "fraccion_municipal": f} for c, f in filas])


def _pob(filas):
    return pd.DataFrame([{"comuna_cut": c, "anio": a, "poblacion": v} for c, a, v in filas])


class TestCoberturaSeCalcula:
    def test_divide_bien_cuando_todo_esta_en_orden(self):
        # 500 en control sobre 10.000 inscritos = 50 por mil, que es la mediana real
        # del país en diciembre de 2025.
        t, meta = tabla_cobertura(
            _rem([("01101", "2025-12", "DEPRESION MODERADA", 500)]),
            _ins([("01101", 2025, 10_000)]),
            _aps([("01101", 1.0)]),
            poblacion=_pob([("01101", 2025, 12_000)]),
            k=0,
        )
        fila = t.iloc[0]
        assert fila["denominador"] == DENOMINADOR_COMPLETO
        assert float(fila["cobertura_por_mil"]) == 50.0
        assert meta["comunas_con_cobertura"] == 1

    def test_la_columna_es_numerica_y_no_object(self):
        # Inicializar con pd.NA y asignar por máscara deja la columna en `object`, que
        # sobrevive a to_parquet y hace fallar cualquier promedio o ranking aguas abajo.
        t, _ = tabla_cobertura(
            _rem([("01101", "2025-12", "X", 500)]),
            _ins([("01101", 2025, 10_000)]),
            _aps([("01101", 1.0)]),
            poblacion=_pob([("01101", 2025, 12_000)]),
            k=0,
        )
        assert t["cobertura_por_mil"].dtype == "Float64"

    def test_el_anio_sale_del_periodo_del_rem(self):
        # `periodo` es YYYY-MM y el denominador es anual. Si el año se tomara de otra
        # columna habría dos verdades sobre a qué año pertenece la fila.
        t, _ = tabla_cobertura(
            _rem([("01101", "2021-06", "X", 100)]),
            _ins([("01101", 2021, 1_000), ("01101", 2025, 9_999)]),
            _aps([("01101", 1.0)]),
            poblacion=_pob([("01101", 2021, 1_200)]),
            k=0,
        )
        assert int(t.iloc[0]["poblacion_inscrita"]) == 1_000
        assert float(t.iloc[0]["cobertura_por_mil"]) == 100.0


class TestNoSePublica:
    """Tres razones distintas para no dividir. Ninguna publica un número con advertencia."""

    def test_comuna_mixta_queda_parcial_y_sin_valor(self):
        # La comuna tiene APS municipal y del Servicio de Salud: el denominador cuenta
        # solo a los municipales y el REM cuenta a todos. La cobertura sobreestimaría.
        t, _ = tabla_cobertura(
            _rem([("16201", "2025-12", "X", 100)]),
            _ins([("16201", 2025, 5_000)]),
            _aps([("16201", 0.5)]),
            poblacion=_pob([("16201", 2025, 12_000)]),
            k=0,
        )
        assert t.iloc[0]["denominador"] == DENOMINADOR_PARCIAL
        assert pd.isna(t.iloc[0]["cobertura_por_mil"])

    def test_comuna_sin_aps_municipal_queda_ausente(self):
        t, _ = tabla_cobertura(
            _rem([("02301", "2025-12", "X", 100)]),
            _ins([("02301", 2025, pd.NA)]),
            _aps([("02301", 0.0)]),
            poblacion=_pob([("02301", 2025, 28_000)]),
            k=0,
        )
        assert t.iloc[0]["denominador"] == DENOMINADOR_AUSENTE
        assert pd.isna(t.iloc[0]["cobertura_por_mil"])

    def test_padron_minoritario_no_se_publica_aunque_sea_100_por_ciento_municipal(self):
        # Tiltil: un solo CESFAM municipal —así que es «100 % municipal»— con un padrón de
        # 2.425 sobre 19.700 habitantes. Contar establecimientos no basta; sin este guard
        # la comuna publicaba 397 personas en control por mil «inscritos».
        t, _ = tabla_cobertura(
            _rem([("13203", "2025-12", "X", 964)]),
            _ins([("13203", 2025, 2_425)]),
            _aps([("13203", 1.0)]),
            poblacion=_pob([("13203", 2025, 19_700)]),
            k=0,
        )
        assert t.iloc[0]["denominador"] == DENOMINADOR_PARCIAL
        assert pd.isna(t.iloc[0]["cobertura_por_mil"])
        assert float(t.iloc[0]["padron_sobre_poblacion"]) == pytest.approx(0.1231, abs=1e-4)

    def test_un_denominador_ya_marcado_por_a015_no_se_usa(self):
        t, _ = tabla_cobertura(
            _rem([("16201", "2025-12", "X", 100)]),
            _ins([("16201", 2025, 33)], total_menor_que_tramos=True),
            _aps([("16201", 1.0)]),
            poblacion=_pob([("16201", 2025, 12_244)]),
            k=0,
        )
        assert t.iloc[0]["denominador"] == DENOMINADOR_AUSENTE

    def test_sin_poblacion_de_referencia_no_puede_medir_el_padron(self):
        # `poblacion` es opcional, pero omitirla desactiva el guard poblacional. El test
        # existe para que eso sea una decisión visible y no una sorpresa.
        t, _ = tabla_cobertura(
            _rem([("13203", "2025-12", "X", 964)]),
            _ins([("13203", 2025, 2_425)]),
            _aps([("13203", 1.0)]),
            k=0,
        )
        assert pd.isna(t.iloc[0]["padron_sobre_poblacion"])
        assert t.iloc[0]["denominador"] == DENOMINADOR_COMPLETO


class TestRefutacionPorNumerador:
    """La regla dura: quien está en control está inscrito. Más control que inscritos es
    imposible, no improbable, y no necesita umbral."""

    def test_mas_personas_en_control_que_inscritos_refuta_el_denominador(self):
        # Sierra Gorda, dic-2025: 275 en control sobre 24 «inscritos».
        df = pd.DataFrame(
            {
                "comuna_cut": ["02103"],
                "anio": [2025],
                "personas": [275],
                "poblacion_inscrita": [24],
            }
        )
        out, rep = refutar_denominador_con_numerador(df)
        assert bool(out.iloc[0]["denominador_refutado"])
        assert rep["celdas_refutadas"] == 1

    def test_no_refuta_un_denominador_mayor_que_el_numerador(self):
        df = pd.DataFrame(
            {
                "comuna_cut": ["01101"],
                "anio": [2025],
                "personas": [500],
                "poblacion_inscrita": [10_000],
            }
        )
        out, rep = refutar_denominador_con_numerador(df)
        assert not bool(out.iloc[0]["denominador_refutado"])
        assert rep["celdas_refutadas"] == 0

    def test_el_defecto_se_propaga_hacia_adelante_pero_nunca_hacia_atras(self):
        # Probado en 2020. Los años anteriores están verificados y sanos: marcarlos sería
        # descartar dato bueno. Los posteriores comparten el régimen de reporte roto y en
        # 2025 el derrumbe conjunto borra la evidencia individual.
        df = pd.DataFrame(
            {
                "comuna_cut": ["02103"] * 4,
                "anio": [2015, 2020, 2022, 2025],
                "personas": [100, 275, 200, 275],
                "poblacion_inscrita": [8_000, 24, 300, 24],
            }
        )
        out, rep = refutar_denominador_con_numerador(df)
        por_anio = out.set_index("anio")["comuna_refutada"]
        assert not por_anio[2015], "2015 está sano y no se toca"
        assert por_anio[2020] and por_anio[2022] and por_anio[2025]
        assert rep["primer_anio_por_comuna"] == {"02103": 2020}

    def test_una_comuna_sana_no_se_contagia_de_otra(self):
        df = pd.DataFrame(
            {
                "comuna_cut": ["02103", "01101"],
                "anio": [2025, 2025],
                "personas": [275, 500],
                "poblacion_inscrita": [24, 10_000],
            }
        )
        out, _ = refutar_denominador_con_numerador(df)
        assert bool(out[out["comuna_cut"] == "02103"].iloc[0]["comuna_refutada"])
        assert not bool(out[out["comuna_cut"] == "01101"].iloc[0]["comuna_refutada"])


class TestComandoCobertura:
    """El comando tiene que negarse a producir una tabla parcial.

    Una cobertura calculada sin saber quién administra la APS de cada comuna se ve
    perfectamente creíble, así que fallar es la única salida segura cuando falta un insumo.
    """

    def test_falla_nombrando_la_capa_que_falta(self, tmp_path, monkeypatch, capsys):
        from types import SimpleNamespace

        from obsm import cli, io

        # Un almacén vacío: no hay ninguna capa silver. `ruta_capa` resuelve contra
        # `io.DIR_DATOS`, así que apuntarlo a un tmp_path deja al comando sin insumos.
        monkeypatch.setattr(io, "DIR_DATOS", tmp_path)

        codigo = cli.cmd_rem_cobertura(SimpleNamespace(config=None, k=5))
        assert codigo == 1
        err = capsys.readouterr().err
        assert "no hay silver del REM" in err
        assert "obsm rem ingerir" in err, "el error nombra el comando que falta"
