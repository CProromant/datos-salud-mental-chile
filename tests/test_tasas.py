"""Tests de indicadores. Los valores esperados están calculados a mano, no con el código."""

import numpy as np
import pandas as pd
import pytest

from obsm.indicators.tasas import (
    POBLACION_ESTANDAR_OMS,
    avpp,
    grupo_quinquenal,
    razon_estandarizada,
    suavizado_eb_poisson_gamma,
    tasa_cruda,
    tasa_estandarizada_directa,
)


class TestGrupoQuinquenal:
    @pytest.mark.parametrize(
        "edad,esperado",
        [(0, "00-04"), (4, "00-04"), (5, "05-09"), (17, "15-19"), (84, "80-84"),
         (85, "85+"), (97, "85+")],
    )
    def test_casos(self, edad, esperado):
        assert grupo_quinquenal(edad) == esperado

    def test_negativa_y_nula(self):
        assert grupo_quinquenal(-1) == "desconocido"
        assert grupo_quinquenal(float("nan")) == "desconocido"
        assert grupo_quinquenal(None) == "desconocido"


class TestTasaCruda:
    def test_valor_a_mano(self):
        # 10 casos en 100.000 habitantes = 10 por 100.000
        assert tasa_cruda([10], [100_000])[0] == pytest.approx(10.0)
        # 5 casos en 50.000 = 10 por 100.000
        assert tasa_cruda([5], [50_000])[0] == pytest.approx(10.0)

    def test_poblacion_cero_da_nan_no_infinito(self):
        assert np.isnan(tasa_cruda([3], [0])[0])


class TestEstandarizacion:
    def test_tasa_constante_por_edad_devuelve_la_misma_tasa(self):
        """Si la tasa específica es 1% en todos los grupos, la estandarizada es 1%."""
        grupos = ["00-04", "05-09", "10-14"]
        casos = pd.Series([10, 20, 30], index=grupos)
        pob = pd.Series([1000, 2000, 3000], index=grupos)
        r = tasa_estandarizada_directa(casos, pob)
        assert r["tasa_estandarizada"] == pytest.approx(1000.0)  # 0,01 * 100.000

    def test_pondera_por_el_estandar_no_por_la_poblacion_local(self):
        """Dos poblaciones con distinta estructura etaria y misma tasa específica
        deben dar la misma tasa estandarizada."""
        grupos = ["00-04", "80-84"]
        casos_a = pd.Series([10, 100], index=grupos)
        pob_a = pd.Series([1000, 1000], index=grupos)
        casos_b = pd.Series([100, 10], index=grupos)
        pob_b = pd.Series([10_000, 100], index=grupos)
        ra = tasa_estandarizada_directa(casos_a, pob_a)
        rb = tasa_estandarizada_directa(casos_b, pob_b)
        # tasas específicas: A = (0,01; 0,10); B = (0,01; 0,10) -> misma estandarizada
        assert ra["tasa_estandarizada"] == pytest.approx(rb["tasa_estandarizada"])

    def test_calculo_manual(self):
        grupos = ["00-04", "80-84"]
        w = np.array([POBLACION_ESTANDAR_OMS[g] for g in grupos])
        w = w / w.sum()
        casos = pd.Series([10, 20], index=grupos)
        pob = pd.Series([1000, 500], index=grupos)
        esperado = (w[0] * 0.01 + w[1] * 0.04) * 100_000
        r = tasa_estandarizada_directa(casos, pob)
        assert r["tasa_estandarizada"] == pytest.approx(esperado)

    def test_reporta_grupos_descartados(self):
        casos = pd.Series([10, 5], index=["00-04", "desconocido"])
        pob = pd.Series([1000, 100], index=["00-04", "desconocido"])
        r = tasa_estandarizada_directa(casos, pob)
        assert r["grupos_descartados"] == ["desconocido"]
        assert r["grupos_usados"] == 1

    def test_intervalo_contiene_a_la_estimacion(self):
        casos = pd.Series([10, 20], index=["00-04", "80-84"])
        pob = pd.Series([1000, 500], index=["00-04", "80-84"])
        r = tasa_estandarizada_directa(casos, pob)
        assert r["ic95_inferior"] < r["tasa_estandarizada"] < r["ic95_superior"]


class TestSuavizadoEB:
    def test_encoge_hacia_la_media_global(self):
        # Un área diminuta con una tasa cruda absurda y varias áreas grandes estables.
        casos = [1, 50, 55, 45, 60]
        pob = [200, 100_000, 110_000, 90_000, 120_000]
        r = suavizado_eb_poisson_gamma(casos, pob)
        cruda_chica = 1 / 200 * 100_000  # 500 por 100.000
        assert r["tasa_suavizada"][0] < cruda_chica / 2
        assert r["peso_local"][0] < r["peso_local"][1]

    def test_area_grande_casi_no_se_mueve(self):
        casos = [5000, 40, 60, 55]
        pob = [10_000_000, 90_000, 110_000, 100_000]
        r = suavizado_eb_poisson_gamma(casos, pob)
        cruda = 5000 / 10_000_000 * 100_000
        assert r["tasa_suavizada"][0] == pytest.approx(cruda, rel=0.05)

    def test_suavizada_entre_local_y_global(self):
        casos = [2, 40, 60, 55]
        pob = [5_000, 90_000, 110_000, 100_000]
        r = suavizado_eb_poisson_gamma(casos, pob)
        local = np.array(casos) / np.array(pob) * 100_000
        glob = r["tasa_global"]
        for i in range(len(casos)):
            lo, hi = sorted([local[i], glob])
            assert lo - 1e-9 <= r["tasa_suavizada"][i] <= hi + 1e-9

    def test_sin_variacion_real_encoge_todo_a_la_media(self):
        """Si toda la dispersión observada es compatible con ruido de Poisson,
        s² = 0 y todas las áreas quedan en la tasa global. Comportamiento correcto."""
        rng = np.random.default_rng(42)
        pob = np.full(60, 50_000)
        casos = rng.poisson(5, size=60)  # misma tasa subyacente en todas
        r = suavizado_eb_poisson_gamma(casos, pob)
        assert r["varianza_entre_areas"] == pytest.approx(0.0, abs=1e-12)
        assert np.allclose(r["tasa_suavizada"], r["tasa_global"])

    def test_poblacion_cero_no_rompe(self):
        r = suavizado_eb_poisson_gamma([0, 10], [0, 100_000])
        assert np.isnan(r["tasa_suavizada"][0])
        assert not np.isnan(r["tasa_suavizada"][1])

    def test_formas_distintas_es_error(self):
        with pytest.raises(ValueError):
            suavizado_eb_poisson_gamma([1, 2], [100])


class TestAVPP:
    def test_calculo_manual(self):
        # (80-20) + (80-70) + 0 = 70
        assert avpp([20, 70, 90]) == 70.0

    def test_limite_configurable(self):
        assert avpp([20], limite=75) == 55.0

    def test_ignora_nan(self):
        assert avpp([20, float("nan")]) == 60.0


class TestSMR:
    def test_valores(self):
        r = razon_estandarizada([10, 20], [10, 10])
        assert r[0] == pytest.approx(1.0)
        assert r[1] == pytest.approx(2.0)

    def test_esperados_cero(self):
        assert np.isnan(razon_estandarizada([5], [0])[0])
