"""Tests del portero de la publicación.

La mitad de estos tests comprueban que la reconciliación **falla** cuando debe. Es
deliberado: `verificar_reconciliacion` existía desde el principio y pasaba sus tests, pero
nadie la llamaba, así que el pipeline podía publicar cualquier cosa. Un guard que nunca se
dispara no protege nada, solo tranquiliza.
"""

import pandas as pd
import pytest
import yaml

from obsm.errors import ObsmError, ReconciliationError
from obsm.reconciliacion import Ancla, cargar_anclas, reconciliar, resumen


def _escribir(tmp_path, anclas):
    ruta = tmp_path / "anclas.yml"
    ruta.write_text(yaml.safe_dump({"anclas": anclas}, allow_unicode=True), encoding="utf-8")
    return ruta


def _ancla(**kwargs):
    base = {
        "id": "x",
        "descripcion": "prueba",
        "source_id": "fuente",
        "metrica": {"tipo": "conteo_filas"},
        "valor": 100,
        "referencia": "documento oficial, p.1",
        "fecha_verificacion": "2026-01-01",
    }
    base.update(kwargs)
    return base


class TestCatalogoReal:
    """El archivo que se usa en producción tiene que estar bien formado."""

    def test_carga(self):
        anclas = cargar_anclas()
        assert len(anclas) >= 4

    def test_toda_ancla_declara_su_procedencia(self):
        # Un número sin origen comprobable no valida nada: traslada la fe de lugar.
        for a in cargar_anclas():
            assert a.referencia, f"{a.id} sin referencia"
            assert a.fecha_verificacion, f"{a.id} sin fecha de verificación"

    def test_cubre_numerador_y_denominador(self):
        fuentes = {a.source_id for a in cargar_anclas()}
        assert "deis_defunciones" in fuentes, "sin ancla del numerador"
        assert "ine_proyecciones" in fuentes, (
            "sin ancla del denominador: un error ahí desplaza todas las tasas a la vez"
        )

    def test_el_denominador_tiene_tolerancia_mas_estricta(self):
        anclas = {a.id: a for a in cargar_anclas()}
        assert (anclas["poblacion_nacional_2020"].tolerancia_relativa
                < anclas["defunciones_totales_2020"].tolerancia_relativa), (
            "sumar el mismo archivo no admite la misma holgura que comparar organismos"
        )


class TestEvaluacion:
    def test_conteo_filas_con_filtro(self):
        a = Ancla(**_ancla(filtro={"anio": 2020}, valor=2))
        df = pd.DataFrame({"anio": [2020, 2020, 2021]})
        assert a.evaluar(df) == 2

    def test_suma_columna(self):
        a = Ancla(**_ancla(
            metrica={"tipo": "suma_columna", "columna": "poblacion"},
            filtro={"anio": 2020}, valor=30,
        ))
        df = pd.DataFrame({"anio": [2020, 2020, 2021], "poblacion": [10, 20, 99]})
        assert a.evaluar(df) == 30

    def test_sin_filtro_toma_todo(self):
        a = Ancla(**_ancla(valor=3))
        assert a.evaluar(pd.DataFrame({"anio": [1, 2, 3]})) == 3

    def test_falla_si_falta_la_columna_de_filtro(self):
        a = Ancla(**_ancla(filtro={"anio": 2020}))
        with pytest.raises(ReconciliationError, match="filtro"):
            a.evaluar(pd.DataFrame({"otra": [1]}))

    def test_falla_si_falta_la_columna_de_la_metrica(self):
        a = Ancla(**_ancla(metrica={"tipo": "suma_columna", "columna": "poblacion"}))
        with pytest.raises(ReconciliationError, match="poblacion"):
            a.evaluar(pd.DataFrame({"otra": [1]}))


class TestElGuardBloquea:
    """La parte que importa: que una serie rota NO pase."""

    def _tabla(self, n):
        return pd.DataFrame({"anio": [2020] * n})

    def test_pasa_cuando_cuadra_exacto(self):
        anclas = [Ancla(**_ancla(valor=100, filtro={"anio": 2020}))]
        res = reconciliar({"fuente": self._tabla(100)}, anclas)
        assert res[0]["estado"] == "ok"
        assert res[0]["diferencia_relativa"] == 0

    def test_pasa_dentro_de_tolerancia(self):
        # 100 contra 100,4 son 0,4 %: bajo el 0,5 % declarado.
        anclas = [Ancla(**_ancla(valor=100.4, filtro={"anio": 2020}))]
        assert reconciliar({"fuente": self._tabla(100)}, anclas)[0]["estado"] == "ok"

    def test_lanza_cuando_se_pasa_de_tolerancia(self):
        anclas = [Ancla(**_ancla(valor=110, filtro={"anio": 2020}))]
        with pytest.raises(ReconciliationError, match="Reconciliación fallida"):
            reconciliar({"fuente": self._tabla(100)}, anclas, estricto=True)

    def test_en_modo_no_estricto_reporta_pero_no_lanza(self):
        # Es el modo de diagnóstico: se quieren ver TODAS las fallas, no la primera.
        anclas = [
            Ancla(**_ancla(id="a", valor=110, filtro={"anio": 2020})),
            Ancla(**_ancla(id="b", valor=200, filtro={"anio": 2020})),
        ]
        res = reconciliar({"fuente": self._tabla(100)}, anclas, estricto=False)
        assert [r["estado"] for r in res] == ["FALLA", "FALLA"]
        assert resumen(res)["FALLA"] == 2

    def test_una_diferencia_de_una_unidad_en_un_millon_no_alarma(self):
        anclas = [Ancla(**_ancla(valor=1_000_001, filtro={"anio": 2020},
                                 tolerancia_relativa=0.005))]
        res = reconciliar({"fuente": self._tabla(1_000_000)}, anclas)
        assert res[0]["estado"] == "ok"

    def test_la_fuente_ausente_se_declara_y_no_se_finge_ok(self):
        # No se puede reconciliar lo que no se cargó. Contarlo como ok sería mentir.
        anclas = [Ancla(**_ancla(source_id="otra_fuente"))]
        res = reconciliar({"fuente": self._tabla(100)}, anclas)
        assert res[0]["estado"] == "omitida"
        assert resumen(res)["ok"] == 0


class TestValidacionDelCatalogo:
    """Un ancla mal declarada debe romper al cargar, no al usarse."""

    def test_rechaza_ancla_sin_referencia(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(referencia="")])
        with pytest.raises(ObsmError, match="procedencia"):
            cargar_anclas(ruta)

    def test_rechaza_ancla_sin_fecha_de_verificacion(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(fecha_verificacion="")])
        with pytest.raises(ObsmError, match="procedencia"):
            cargar_anclas(ruta)

    def test_rechaza_metrica_desconocida(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(metrica={"tipo": "promedio_magico"})])
        with pytest.raises(ObsmError, match="métrica"):
            cargar_anclas(ruta)

    def test_rechaza_suma_columna_sin_columna(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(metrica={"tipo": "suma_columna"})])
        with pytest.raises(ObsmError, match="columna"):
            cargar_anclas(ruta)

    @pytest.mark.parametrize("tol", [0, 1, 1.5, -0.1])
    def test_rechaza_tolerancia_fuera_de_rango(self, tmp_path, tol):
        # Una tolerancia de 0 nunca pasa; una de 1 acepta cualquier cosa. Ambas
        # convierten el guard en decoración.
        ruta = _escribir(tmp_path, [_ancla(tolerancia_relativa=tol)])
        with pytest.raises(ObsmError, match="olerancia"):
            cargar_anclas(ruta)

    def test_rechaza_campos_desconocidos(self, tmp_path):
        # Un `tolerancia: 0.5` mal escrito quedaría ignorado y el ancla usaría el default
        # sin que nadie lo note.
        ruta = _escribir(tmp_path, [_ancla(tolerancia=0.5)])
        with pytest.raises(ObsmError, match="desconocidos"):
            cargar_anclas(ruta)

    def test_rechaza_ids_duplicados(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(id="x"), _ancla(id="x")])
        with pytest.raises(ObsmError, match="duplicados"):
            cargar_anclas(ruta)

    def test_rechaza_valor_no_positivo(self, tmp_path):
        ruta = _escribir(tmp_path, [_ancla(valor=0)])
        with pytest.raises(ObsmError, match="no positivo"):
            cargar_anclas(ruta)
