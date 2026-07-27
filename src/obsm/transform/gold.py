"""silver → gold: indicadores publicables.

Toda salida de este módulo cumple, por construcción:
  - lleva procedencia (`source_id`, `source_version`, `fecha_extraccion`, `pipeline_version`);
  - pasó por la política de publicación (`quality.verificar_politica_publicacion`);
  - tiene supresión de celdas pequeñas aplicada;
  - marca los años preliminares.
"""

from __future__ import annotations

import pandas as pd

from .. import PIPELINE_VERSION
from ..indicators.tasas import POR_DEFECTO, suavizado_eb_poisson_gamma, tasa_cruda
from ..io import ahora_iso
from ..quality import (
    K_SUPRESION_MORTALIDAD,
    suprimir_celdas_pequenas,
    verificar_politica_publicacion,
)

DIMENSIONES_BASE = ["comuna_cut", "anio"]


def tasas_comunales(
    agregado: pd.DataFrame,
    poblacion: pd.DataFrame,
    agrupador_id: str,
    dimensiones: list[str] | None = None,
    grupo_suavizado: list[str] | None = None,
    anios_preliminares: tuple[int, ...] = (),
    k: int = K_SUPRESION_MORTALIDAD,
    por: int = POR_DEFECTO,
    source_id: str = "deis_defunciones",
    source_version: str | None = None,
    poblacion_version: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Une conteos con población, calcula tasa cruda y suavizada, y suprime.

    `poblacion` debe tener las mismas dimensiones que `agregado` más `poblacion`.
    El join es `left` sobre el agregado y luego se reindexa contra la población
    completa: las comunas con cero casos deben aparecer con cero, no desaparecer.
    Una comuna ausente se lee como "sin datos" y una comuna con cero se lee como
    "sin muertes"; confundirlas sesga cualquier comparación territorial.
    """
    dimensiones = dimensiones or DIMENSIONES_BASE
    faltan = [d for d in dimensiones if d not in poblacion.columns]
    if faltan:
        raise KeyError(f"La tabla de población no tiene las dimensiones {faltan}")

    base = poblacion.groupby(dimensiones, dropna=False)["poblacion"].sum().reset_index()
    conteos = agregado.groupby(dimensiones, dropna=False)["casos"].sum().reset_index()
    df = base.merge(conteos, on=dimensiones, how="left")
    df["casos"] = df["casos"].fillna(0).astype("Int64")

    df["tasa_cruda"] = tasa_cruda(df["casos"].astype("float64"), df["poblacion"], por=por)

    # El suavizado se calcula DENTRO de cada grupo temporal, no sobre el panel completo.
    # Mezclar años haría que la media hacia la que se encoge una comuna incluya sus
    # propios años vecinos, lo que aplana tendencias reales.
    grupo_suav = grupo_suavizado if grupo_suavizado is not None else (
        ["anio"] if "anio" in dimensiones else []
    )
    df["tasa_suavizada_eb"] = pd.NA
    df["peso_local_eb"] = pd.NA
    resumen_eb: dict = {}
    if grupo_suav:
        for clave, sub in df.groupby(grupo_suav, sort=False):
            eb = suavizado_eb_poisson_gamma(
                sub["casos"].astype("float64"), sub["poblacion"], por=por
            )
            df.loc[sub.index, "tasa_suavizada_eb"] = eb["tasa_suavizada"]
            df.loc[sub.index, "peso_local_eb"] = eb["peso_local"]
            resumen_eb[str(clave)] = {
                "tasa_global": eb["tasa_global"],
                "varianza_entre_areas": eb["varianza_entre_areas"],
            }
    else:
        eb = suavizado_eb_poisson_gamma(
            df["casos"].astype("float64"), df["poblacion"], por=por
        )
        df["tasa_suavizada_eb"] = eb["tasa_suavizada"]
        df["peso_local_eb"] = eb["peso_local"]
        resumen_eb["global"] = {
            "tasa_global": eb["tasa_global"],
            "varianza_entre_areas": eb["varianza_entre_areas"],
        }
    df["tasa_suavizada_eb"] = pd.to_numeric(df["tasa_suavizada_eb"])
    df["peso_local_eb"] = pd.to_numeric(df["peso_local_eb"])

    df["agrupador"] = agrupador_id
    df["preliminar"] = df["anio"].isin(anios_preliminares)
    df["source_id"] = source_id
    df["source_version"] = source_version
    df["poblacion_version"] = poblacion_version
    df["pipeline_version"] = PIPELINE_VERSION
    df["fecha_calculo"] = ahora_iso()

    verificar_politica_publicacion(df, agrupador_id=agrupador_id)
    publicable, reporte_sup = suprimir_celdas_pequenas(
        df, "casos", k=k, grupo=[d for d in dimensiones if d != "comuna_cut"]
    )
    # Si el conteo se suprime, la tasa cruda derivada también debe suprimirse:
    # dejarla permite reconstruir el conteo multiplicando por la población.
    publicable.loc[publicable["suprimido"], "tasa_cruda"] = pd.NA

    meta = {
        "agrupador": agrupador_id,
        "dimensiones": dimensiones,
        "filas": len(publicable),
        "suavizado_eb": {"agrupado_por": grupo_suav or "panel completo", "por_grupo": resumen_eb},
        "supresion": {
            "k": reporte_sup.k,
            "filas_suprimidas": reporte_sup.filas_suprimidas,
            "complementarias": reporte_sup.filas_suprimidas_complementarias,
            "porcentaje": reporte_sup.porcentaje_suprimido,
        },
        "advertencias": _advertencias(publicable, reporte_sup.porcentaje_suprimido),
    }
    return publicable, meta


def _advertencias(df: pd.DataFrame, pct_suprimido: float) -> list[str]:
    avisos = []
    if pct_suprimido > 0.5:
        avisos.append(
            f"Se suprimió el {pct_suprimido:.0%} de las celdas: a esta desagregación el "
            f"indicador comunal aporta poco. Considerar agregar años o subir de nivel."
        )
    if df["preliminar"].any():
        avisos.append(
            "La serie incluye años preliminares. No usarlos como punto final de tendencia."
        )
    if (df["peso_local_eb"] < 0.2).mean() > 0.5:
        avisos.append(
            "En más de la mitad de las áreas el suavizado domina al dato local: las "
            "diferencias entre comunas son mayormente ruido. No rankear."
        )
    return avisos
