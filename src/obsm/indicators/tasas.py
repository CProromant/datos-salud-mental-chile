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

#: Tope etario del pipeline. **Lo fija el denominador, no una preferencia.** Las
#: proyecciones comunales del INE publican `80` como grupo abierto («80 y más») y no hay
#: forma de partirlo en 80-84 y 85+ sin inventar población, que es justo lo que la tabla de
#: capas de `docs/02-ARQUITECTURA.md` le prohíbe a `gold`.
#:
#: Las defunciones sí traen edad exacta y podrían separarse hasta 85+, pero estandarizar
#: exige numerador y denominador en la misma grilla. Se colapsa al grano común más grueso.
#: Existe como constante única para que ambos lados no puedan divergir: si un día el INE
#: publica hasta 85+, se cambia acá y se recalcula todo, en un solo lugar.
TOPE_EDAD_PIPELINE = 80

#: Límite de los años de vida potencial perdidos. Es una convención elegida por
#: comparabilidad, no una afirmación sobre el valor de una vida (ver ficha I-02).
#: Se prefiere un límite fijo a la esperanza de vida del año porque esta última hace
#: que la serie cambie por moverse el patrón de referencia y no por moverse la muerte.
LIMITE_AVPP = 80


def colapsar_estandar(
    estandar: dict[str, float], tope: int = TOPE_EDAD_PIPELINE
) -> dict[str, float]:
    """Colapsa los grupos por encima de `tope` en un único grupo abierto `{tope}+`.

    Sumar los pesos es la operación correcta: el peso de un grupo abierto es la suma de
    los pesos de los grupos que agrupa. No colapsar sería peor que perder resolución —
    `tasa_estandarizada_directa` descarta los grupos que no encuentra en el estándar, así
    que un denominador en `80+` contra un estándar en `80-84`/`85+` produciría una tasa
    calculada **sin adultos mayores**, sin que nada falle.

    >>> pesos = colapsar_estandar({"75-79": 1.5, "80-84": 0.9, "85+": 0.6}, tope=80)
    >>> pesos == {"75-79": 1.5, "80+": 1.5}
    True
    """
    abierto = f"{tope}+"
    salida: dict[str, float] = {}
    acumulado = 0.0
    for grupo, peso in estandar.items():
        inicio = grupo.rstrip("+").split("-")[0]
        if inicio.isdigit() and int(inicio) >= tope:
            acumulado += peso
        else:
            salida[grupo] = peso
    if acumulado:
        salida[abierto] = acumulado
    return salida


#: La estándar OMS llevada al tope del pipeline. `80-84` (0,910) y `85+` (0,635) se suman
#: en `80+` (1,545).
POBLACION_ESTANDAR_OMS_80: dict[str, float] = colapsar_estandar(POBLACION_ESTANDAR_OMS)


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
    if not validos.any():
        # Ningún grupo con población: la tasa es indefinida, no cero. `nansum` de un
        # conjunto vacío devuelve 0.0, y ese 0.0 se leería como «no hubo muertes» cuando
        # significa «no hay a quién dividir». Es el mismo error que `tasa_cruda` ya evita.
        return {
            "tasa_estandarizada": float("nan"),
            "error_estandar": float("nan"),
            "ic95_inferior": float("nan"),
            "ic95_superior": float("nan"),
            "casos_totales": float(np.nansum(casos)),
            "poblacion_total": 0.0,
            "grupos_usados": len(grupos),
            "grupos_descartados": descartados,
        }

    tasa = float(np.nansum(pesos[validos] * tasas_esp[validos]) * por)
    ee = float(np.sqrt(np.nansum(var_terms[validos])) * por)

    return {
        "tasa_estandarizada": tasa,
        "error_estandar": ee,
        # El límite inferior se trunca en 0: una tasa negativa no existe. La aproximación
        # normal sobre la varianza de Poisson lo produce con conteos pequeños, y publicar
        # «−11,9 por 100.000» es peor que perder la simetría del intervalo. Que el
        # truncamiento haya sido necesario es señal de que el conteo es demasiado bajo
        # para este método: por eso se devuelve `casos_totales` junto a la tasa.
        "ic95_inferior": max(0.0, tasa - 1.96 * ee),
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


def avpp(edades, limite: int = LIMITE_AVPP) -> float:
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
