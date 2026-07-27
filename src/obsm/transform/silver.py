"""bronze → silver: normalización territorial, etaria y de clasificación.

Funciones puras sobre DataFrames. Acá y solo acá se aplica `territorio` y `cie10`.
"""

from __future__ import annotations

import pandas as pd

from ..cie10 import AGRUPADORES
from ..indicators.tasas import grupo_quinquenal
from ..quality import detectar_filas_total
from ..territorio import (
    COMUNA_DESCONOCIDA,
    DPA,
    cargar_dpa,
    formatear_cut_comuna,
    normalizar_serie_comunas,
)


def normalizar_defunciones(
    df: pd.DataFrame, dpa: DPA | None = None, agrupadores: list[str] | None = None
) -> tuple[pd.DataFrame, dict]:
    """Lleva defunciones de bronze a la grilla canónica.

    Devuelve (silver, reporte). El reporte es parte de la salida, no un efecto
    secundario: la tasa de comunas no resueltas y el número de filas-total
    descartadas son indicadores de calidad que se publican junto con los datos.
    """
    reporte: dict = {"filas_entrada": len(df)}
    out = df.copy()

    # 1. Filas de total mezcladas con el detalle. Se prefiere la marca que puso el
    #    ingestor sobre el texto crudo: en bronze las pistas textuales ya se perdieron
    #    en la coerción de tipos.
    if "_es_fila_total" in out.columns:
        marca_total = out["_es_fila_total"].fillna(False).astype(bool)
    else:
        marca_total = detectar_filas_total(out)
    reporte["filas_total_descartadas"] = int(marca_total.sum())
    out = out.loc[~marca_total].copy()

    # 2. Territorio. Se prefiere el código de la fuente; el nombre es respaldo.
    if "comuna_cut_fuente" in out.columns and out["comuna_cut_fuente"].notna().any():
        # Dos formas distintas de estar mal, y hay que contarlas por separado. Un CUT
        # puede estar bien formado y aun así no existir: DEIS usa 99999 como centinela
        # de "comuna ignorada". Validar solo el formato dejaba pasar ese centinela como
        # si fuera una comuna real, con region_cut 99, y reportaba cut_invalidos=0.
        vigentes = (dpa or cargar_dpa()).por_cut
        cuts = []
        mal_formados = 0
        fuera_de_dpa = 0
        for v in out["comuna_cut_fuente"]:
            try:
                cut = formatear_cut_comuna(v)
            except Exception:  # noqa: BLE001
                cuts.append(COMUNA_DESCONOCIDA)
                mal_formados += 1
                continue
            if cut not in vigentes:
                cuts.append(COMUNA_DESCONOCIDA)
                if cut != COMUNA_DESCONOCIDA:
                    fuera_de_dpa += 1
                continue
            cuts.append(cut)
        out["comuna_cut"] = cuts
        reporte["cut_mal_formados"] = mal_formados
        reporte["cut_fuera_de_dpa"] = fuera_de_dpa
        reporte["cut_invalidos"] = mal_formados + fuera_de_dpa
        reporte["cut_desconocidos"] = int((out["comuna_cut"] == COMUNA_DESCONOCIDA).sum())
        reporte["fuente_territorio"] = "codigo"
    elif "comuna_nombre" in out.columns:
        cuts, rep_terr = normalizar_serie_comunas(out["comuna_nombre"], dpa=dpa)
        out["comuna_cut"] = cuts
        reporte["territorio"] = rep_terr
        reporte["fuente_territorio"] = "nombre"
    else:
        out["comuna_cut"] = COMUNA_DESCONOCIDA
        reporte["fuente_territorio"] = "ausente"

    out["region_cut"] = out["comuna_cut"].str[:2]

    # 3. Edad.
    if "edad_anios" in out.columns:
        out["grupo_edad"] = [
            grupo_quinquenal(e) if pd.notna(e) else "desconocido" for e in out["edad_anios"]
        ]
    else:
        out["grupo_edad"] = "desconocido"
        reporte["edad_ausente"] = True

    # 4. Clasificación CIE-10. Una defunción puede caer en más de un agrupador
    #    (p. ej. DEMENCIAS y TRASTORNOS_MENTALES): se generan columnas booleanas
    #    en vez de una etiqueta única, para no forzar una jerarquía falsa.
    ids = agrupadores or list(AGRUPADORES)
    for aid in ids:
        ag = AGRUPADORES[aid]
        out[f"es_{aid.lower()}"] = out["causa_cie10"].map(ag.contiene)

    reporte["filas_salida"] = len(out)
    return out, reporte


def agregar_defunciones(
    silver: pd.DataFrame,
    agrupador_id: str,
    dimensiones: list[str] | None = None,
) -> pd.DataFrame:
    """Agrega defunciones de un agrupador a la grilla comuna × año × dimensiones.

    Nunca devuelve la columna de código CIE-10: la agregación es el punto en que se
    pierde el detalle de método, y se pierde a propósito (ver docs/06).
    """
    col = f"es_{agrupador_id.lower()}"
    if col not in silver.columns:
        raise KeyError(f"El silver no tiene la columna {col}; ¿se clasificó con ese agrupador?")
    dimensiones = dimensiones or ["comuna_cut", "anio", "sexo", "grupo_edad"]
    sub = silver.loc[silver[col]].copy()
    g = (
        sub.groupby(dimensiones, dropna=False)
        .size()
        .reset_index(name="casos")
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )
    g["agrupador"] = agrupador_id
    return g
