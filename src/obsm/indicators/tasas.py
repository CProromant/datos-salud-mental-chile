"""Cálculo de tasas: cruda, estandarizada por edad, suavizada y AVPP.

Funciones puras: entran y salen estructuras de datos, sin I/O. Todo el módulo es
testeable contra valores calculados a mano, y así están escritos sus tests.

Por qué importa el suavizado: la mitad de las comunas de Chile tiene poblaciones
en las que una o dos muertes mueven la tasa cruda por 100.000 en varias decenas.
Publicar tasas crudas comunales de un evento raro produce rankings que reflejan
ruido y que después alguien usa para asignar recursos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Población estándar mundial de la OMS (Ahmad et al., 2001), en porcentaje por
#: grupo quinquenal. Los valores publicados suman ~100,035 por redondeo; el código
#: los normaliza a 1. VERIFICAR contra la publicación original antes de la v1.0.
POBLACION_ESTANDAR_OMS: dict[str, float] = {
    "00-04": 8.860,
    "05-09": 8.690,
    "10-14": 8.600,
    "15-19": 8.470,
    "20-24": 8.220,
    "25-29": 7.930,
    "30-34": 7.610,
    "35-39": 7.150,
    "40-44": 6.590,
    "45-49": 6.040,
    "50-54": 5.370,
    "55-59": 4.550,
    "60-64": 3.720,
    "65-69": 2.960,
    "70-74": 2.210,
    "75-79": 1.520,
    "80-84": 0.910,
    "85+": 0.635,
}

POR_DEFECTO = 100_000


def grupo_quinquenal(edad: float | int, tope: int = 85) -> str:
    """Asigna una edad en años a su grupo quinquenal canónico.

    >>> grupo_quinquenal(0)
    '00-04'
    >>> grupo_quinquenal(17)
    '15-19'
    >>> grupo_quinquenal(97)
    '85+'
    """
    if edad is None or (isinstance(edad, float) and np.isnan(edad)):
        return "desconocido"
    e = int(edad)
    if e < 0:
        return "desconocido"
    if e >= tope:
        return f"{tope}+"
    inicio = (e // 5) * 5
    return f"{inicio:02d}-{inicio + 4:02d}"


def tasa_cruda(casos, poblacion, por: int = POR_DEFECTO):
    """Tasa cruda por `por` habitantes. Devuelve NaN si la población es 0 o nula."""
    casos = np.asarray(casos, dtype="float64")
    poblacion = np.asarray(poblacion, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(poblacion > 0, casos / poblacion * por, np.nan)
    return t


def tasa_estandarizada_directa(
    casos_por_edad: pd.Series,
    poblacion_por_edad: pd.Series,
    poblacion_estandar: dict[str, float] | None = None,
    por: int = POR_DEFECTO,
) -> dict:
    """Estandarización directa por edad.

    `casos_por_edad` y `poblacion_por_edad` deben estar indexadas por el mismo
    conjunto de grupos etarios. Los grupos presentes en los datos pero ausentes del
    estándar se descartan (y se reportan), no se reparten.

    Devuelve tasa estandarizada, error estándar y IC 95% por aproximación normal
    sobre la varianza de Poisson. Para conteos muy pequeños la aproximación normal
    es mala: por eso el resultado incluye `casos_totales`, y la capa de publicación
    usa el suavizado EB cuando ese total es bajo.
    """
    estandar = poblacion_estandar or POBLACION_ESTANDAR_OMS
    grupos = [g for g in casos_por_edad.index if g in estandar]
    descartados = [g for g in casos_por_edad.index if g not in estandar]

    pesos = np.array([estandar[g] for g in grupos], dtype="float64")
    pesos = pesos / pesos.sum()
    casos = casos_por_edad.reindex(grupos).astype("float64").to_numpy()
    pob = poblacion_por_edad.reindex(grupos).astype("float64").to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        tasas_esp = np.where(pob > 0, casos / pob, np.nan)
        var_terms = np.where(pob > 0, (pesos**2) * casos / (pob**2), np.nan)

    validos = ~np.isnan(tasas_esp)
    tasa = float(np.nansum(pesos[validos] * tasas_esp[validos]) * por)
    ee = float(np.sqrt(np.nansum(var_terms[validos])) * por)

    return {
        "tasa_estandarizada": tasa,
        "error_estandar": ee,
        "ic95_inferior": tasa - 1.96 * ee,
        "ic95_superior": tasa + 1.96 * ee,
        "casos_totales": float(np.nansum(casos)),
        "poblacion_total": float(np.nansum(pob)),
        "grupos_usados": len(grupos),
        "grupos_descartados": descartados,
    }


def suavizado_eb_poisson_gamma(
    casos, poblacion, por: int = POR_DEFECTO
) -> dict[str, np.ndarray | float]:
    """Suavizado bayesiano empírico global (estimador de Marshall, Poisson-Gamma).

    Encoge la tasa de cada área hacia la media global en proporción inversa a la
    información local disponible. Un área con 200 habitantes y una muerte queda
    cerca de la media nacional; una comuna grande casi no se mueve.

    Fórmulas:
        m   = sum(casos) / sum(poblacion)                     (tasa global)
        s²  = sum(n_i (r_i - m)²) / sum(n_i) - m / n_barra    (varianza entre áreas)
        w_i = s² / (s² + m / n_i)                             (peso del dato local)
        r*_i = w_i r_i + (1 - w_i) m

    Si s² resulta negativa (ruido domina toda la variación observada) se fija en 0,
    lo que equivale a encoger todo a la media global. Es el comportamiento correcto
    y conservador para un evento raro.
    """
    casos = np.asarray(casos, dtype="float64")
    poblacion = np.asarray(poblacion, dtype="float64")
    if casos.shape != poblacion.shape:
        raise ValueError("casos y poblacion deben tener la misma forma")

    validos = poblacion > 0
    n = poblacion[validos]
    y = casos[validos]
    if n.size == 0:
        return {
            "tasa_suavizada": np.full_like(casos, np.nan),
            "peso_local": np.full_like(casos, np.nan),
            "tasa_global": np.nan,
            "varianza_entre_areas": np.nan,
        }

    m = y.sum() / n.sum()
    r = y / n
    n_barra = n.mean()
    s2 = float((n * (r - m) ** 2).sum() / n.sum() - m / n_barra)
    s2 = max(s2, 0.0)

    # s2 == 0 significa que toda la dispersión observada es compatible con ruido:
    # el peso local es cero y todas las áreas quedan en la media global.
    w = np.zeros_like(n) if s2 == 0.0 else s2 / (s2 + m / n)

    r_eb = w * r + (1 - w) * m

    tasa_out = np.full(casos.shape, np.nan, dtype="float64")
    peso_out = np.full(casos.shape, np.nan, dtype="float64")
    tasa_out[validos] = r_eb * por
    peso_out[validos] = w

    return {
        "tasa_suavizada": tasa_out,
        "peso_local": peso_out,
        "tasa_global": float(m * por),
        "varianza_entre_areas": s2,
    }


def avpp(edades, limite: int = 80) -> float:
    """Años de vida potencial perdidos, con límite fijo (por defecto 80 años).

    Cada defunción aporta max(0, limite - edad). El límite fijo se prefiere a la
    esperanza de vida por año porque hace la serie comparable en el tiempo; la
    elección queda declarada en la ficha del indicador.

    >>> avpp([20, 70, 90])
    70.0
    """
    e = np.asarray(list(edades), dtype="float64")
    e = e[~np.isnan(e)]
    return float(np.maximum(limite - e, 0).sum())


def razon_estandarizada(casos_observados, casos_esperados) -> np.ndarray:
    """Razón observados/esperados (SMR). Útil cuando no hay tasas específicas fiables."""
    obs = np.asarray(casos_observados, dtype="float64")
    esp = np.asarray(casos_esperados, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(esp > 0, obs / esp, np.nan)
