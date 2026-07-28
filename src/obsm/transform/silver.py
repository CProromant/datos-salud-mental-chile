"""bronze → silver: normalización territorial, etaria y de clasificación.

Funciones puras sobre DataFrames. Acá y solo acá se aplica `territorio` y `cie10`.
"""

from __future__ import annotations

import re

import pandas as pd

from ..cie10 import AGRUPADORES
from ..indicators.tasas import LIMITE_AVPP, TOPE_EDAD_PIPELINE, grupo_quinquenal
from ..quality import detectar_filas_total
from ..territorio import (
    COMUNA_DESCONOCIDA,
    DPA,
    cargar_dpa,
    formatear_cut_comuna,
    normalizar_serie_comunas,
)


def resolver_cut(
    codigos: pd.Series, dpa: DPA | None = None
) -> tuple[list[str], dict]:
    """Lleva códigos de comuna de la fuente a CUT canónico, validando existencia.

    Devuelve (cuts, reporte). Hay dos formas distintas de estar mal y se cuentan por
    separado: un código puede estar **bien formado y aun así no existir**. DEIS usa 99999
    como centinela de «comuna ignorada» y el INE trae el CUT sin el cero a la izquierda.
    Validar solo el formato dejaba pasar el centinela como comuna real, con `region_cut`
    99, y reportaba `cut_invalidos: 0` (A-007).
    """
    vigentes = (dpa or cargar_dpa()).por_cut
    cuts: list[str] = []
    mal_formados = 0
    fuera_de_dpa = 0
    for v in codigos:
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
    reporte = {
        "cut_mal_formados": mal_formados,
        "cut_fuera_de_dpa": fuera_de_dpa,
        "cut_invalidos": mal_formados + fuera_de_dpa,
        "cut_desconocidos": sum(1 for c in cuts if c == COMUNA_DESCONOCIDA),
        "fuente_territorio": "codigo",
    }
    return cuts, reporte


def normalizar_poblacion(
    df: pd.DataFrame, dpa: DPA | None = None, tope_edad: int = TOPE_EDAD_PIPELINE
) -> tuple[pd.DataFrame, dict]:
    """Lleva las proyecciones de población de bronze a la grilla canónica.

    Devuelve (silver, reporte) con una fila por `comuna_cut × anio × sexo × grupo_edad` y
    la población sumada. Es el denominador de toda tasa: un defecto acá no produce un
    número raro en una columna, desplaza todas las tasas del proyecto a la vez.

    `tope_edad` debe ser el mismo que usa el numerador. Por eso el valor por defecto es la
    constante compartida y no un literal: numerador y denominador en grillas distintas
    hacen que `tasa_estandarizada_directa` descarte los grupos que no calzan, y una tasa
    calculada sin adultos mayores no se ve rota, se ve baja.
    """
    reporte: dict = {"filas_entrada": len(df)}
    out = df.copy()

    if "_es_fila_total" in out.columns:
        marca_total = out["_es_fila_total"].fillna(False).astype(bool)
        reporte["filas_total_descartadas"] = int(marca_total.sum())
        out = out.loc[~marca_total].copy()

    out["comuna_cut"], rep_cut = resolver_cut(out["comuna_cut_fuente"], dpa=dpa)
    reporte.update(rep_cut)
    out["region_cut"] = out["comuna_cut"].str[:2]

    out["grupo_edad"] = [
        grupo_quinquenal(e, tope=tope_edad) if pd.notna(e) else "desconocido"
        for e in out["edad_anios"]
    ]
    reporte["tope_edad"] = tope_edad

    dimensiones = ["comuna_cut", "region_cut", "anio", "sexo", "grupo_edad"]
    agregado = (
        out.groupby(dimensiones, dropna=False)["poblacion"]
        .sum()
        .reset_index()
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )

    reporte["filas_salida"] = len(agregado)
    reporte["poblacion_total"] = int(agregado["poblacion"].sum())
    # Un cero es un dato («no vive nadie»), no un faltante. Se cuenta, no se filtra: es
    # legítimo en comunas diminutas (A-009) y `tasa_cruda` ya devuelve NaN al dividir.
    reporte["celdas_poblacion_cero"] = int((agregado["poblacion"] == 0).sum())
    return agregado, reporte


#: Traducción de los grupos etarios del REM a la grilla del proyecto.
#: Coinciden exactamente y son idénticos en todos los años revisados (2014-2025): el
#: formulario usa quinquenios y cierra con un grupo abierto en 80, que es la misma grilla
#: que impone el denominador del INE (ver TOPE_EDAD_PIPELINE). No hay que armonizar nada,
#: solo cambiar la escritura.
_RE_GRUPO_REM = re.compile(r"^(\d{1,3})\s*(?:a|-)\s*(\d{1,3})\s*años?$", re.I)
_RE_GRUPO_ABIERTO = re.compile(r"^(\d{1,3})\s*y\s*m[áa]s\s*años?$", re.I)


def grupo_edad_rem(texto: str) -> str:
    """Pasa «0 a 4 años» a «00-04» y «80 y más años» a «80+».

    Devuelve `desconocido` ante cualquier forma que no reconozca, en vez de adivinar:
    un grupo mal asignado mueve personas de un tramo etario a otro sin dejar rastro.
    """
    t = " ".join(str(texto or "").split())
    if not t:
        return "desconocido"
    if m := _RE_GRUPO_ABIERTO.match(t):
        return f"{int(m.group(1))}+"
    if m := _RE_GRUPO_REM.match(t):
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return "desconocido"


def normalizar_rem(
    df: pd.DataFrame, dpa: DPA | None = None
) -> tuple[pd.DataFrame, dict]:
    """Lleva el REM de bronze a la grilla canónica.

    Devuelve (silver, reporte) con una fila por `comuna_cut × periodo × concepto ×
    grupo_edad × sexo`. El período es **semestral**, no mensual: población bajo control es
    un stock con corte en junio y diciembre, y así viene el archivo.

    Se agrega por comuna sumando establecimientos. Un establecimiento no es una unidad de
    análisis publicable —identificar el CESFAM con dos casos de un diagnóstico es
    identificar a las personas—, y el proyecto trabaja a nivel territorial.
    """
    reporte: dict = {"filas_entrada": len(df)}
    out = df.copy()

    out["comuna_cut"], rep_cut = resolver_cut(out["comuna_cut_fuente"], dpa=dpa)
    reporte.update(rep_cut)
    out["region_cut"] = out["comuna_cut"].str[:2]

    # Período ISO mensual: el corte de junio es `2023-06`, el de diciembre `2023-12`.
    out["periodo"] = (
        out["anio"].astype("Int64").astype(str)
        + "-"
        + out["mes"].astype("Int64").astype(str).str.zfill(2)
    )
    reporte["periodos"] = sorted(out["periodo"].dropna().unique().tolist())

    # Las columnas de total y las de detalle etario cuentan a la MISMA gente: sumarlas
    # duplicaría a cada persona. Se marcan para que quien agregue elija una de las dos.
    out["es_total_etario"] = out["grupo_edad_fuente"].fillna("").eq("")

    # Una fila de total se etiqueta `total`, no `desconocido`. La distinción importa:
    # `desconocido` dice «no sabemos en qué tramo está esta gente» y `total` dice «esta
    # fila son todos los tramos juntos». Confundirlas lleva a sumar el total con el
    # detalle y contar a cada persona dos veces.
    out["grupo_edad"] = out["grupo_edad_fuente"].map(grupo_edad_rem)
    out.loc[out["es_total_etario"], "grupo_edad"] = "total"

    no_reconocidos = out["grupo_edad"].eq("desconocido")
    reporte["grupos_edad_no_reconocidos"] = sorted(
        out.loc[no_reconocidos, "grupo_edad_fuente"].dropna().unique().tolist()
    )

    dimensiones = [
        "comuna_cut", "region_cut", "periodo", "codigo_prestacion", "grupo", "concepto",
        "grupo_edad", "sexo", "es_total_etario",
    ]
    agregado = (
        out.groupby(dimensiones, dropna=False)["valor"]
        .sum()
        .reset_index()
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )

    reporte["filas_salida"] = len(agregado)
    reporte["conceptos"] = int(agregado["concepto"].nunique())
    reporte["personas_en_total_etario"] = int(
        agregado.loc[agregado["es_total_etario"] & agregado["sexo"].eq("ambos"), "valor"].sum()
    )
    return agregado, reporte


def normalizar_defunciones(
    df: pd.DataFrame,
    dpa: DPA | None = None,
    agrupadores: list[str] | None = None,
    tope_edad: int = TOPE_EDAD_PIPELINE,
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
        out["comuna_cut"], rep_cut = resolver_cut(out["comuna_cut_fuente"], dpa=dpa)
        reporte.update(rep_cut)
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
        # El tope lo fija el denominador (ver TOPE_EDAD_PIPELINE): las defunciones
        # traen edad exacta y podrían llegar a 85+, pero estandarizar exige que
        # numerador y denominador estén en la misma grilla.
        out["grupo_edad"] = [
            grupo_quinquenal(e, tope=tope_edad) if pd.notna(e) else "desconocido"
            for e in out["edad_anios"]
        ]
        reporte["tope_edad"] = tope_edad
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


def agregar_avpp(
    silver: pd.DataFrame,
    agrupador_id: str,
    dimensiones: list[str] | None = None,
    limite: int = LIMITE_AVPP,
) -> pd.DataFrame:
    """Años de vida potencial perdidos por área, sumando max(0, límite − edad).

    Se calcula acá y no en `gold` porque necesita la **edad de cada defunción**, que solo
    existe antes de agregar. Es también la razón por la que el resultado es sensible:
    el AVPP de un área con una sola muerte revela la edad exacta de esa persona. Quien lo
    publique debe suprimirlo con el mismo umbral que el conteo, no después (ver `gold`).

    Las defunciones sin edad no aportan y se cuentan aparte: tratarlas como cero sería
    afirmar que murieron a los `limite` años.
    """
    col = f"es_{agrupador_id.lower()}"
    if col not in silver.columns:
        raise KeyError(f"El silver no tiene la columna {col}; ¿se clasificó con ese agrupador?")
    dimensiones = dimensiones or ["comuna_cut", "anio"]
    sub = silver.loc[silver[col]].copy()
    sub["_aporte"] = (limite - pd.to_numeric(sub["edad_anios"], errors="coerce")).clip(lower=0)
    g = (
        sub.groupby(dimensiones, dropna=False)
        .agg(avpp=("_aporte", "sum"), casos_sin_edad=("_aporte", lambda s: int(s.isna().sum())))
        .reset_index()
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )
    g["avpp"] = g["avpp"].astype("float64")
    return g


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
