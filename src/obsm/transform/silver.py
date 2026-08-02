"""bronze → silver: normalización territorial, etaria y de clasificación.

Funciones puras sobre DataFrames. Acá y solo acá se aplica `territorio` y `cie10`.
"""

from __future__ import annotations

import re

import pandas as pd

from ..cie10 import AGRUPADORES
from ..errors import ReconciliationError
from ..indicators.tasas import LIMITE_AVPP, TOPE_EDAD_PIPELINE, grupo_quinquenal
from ..quality import detectar_filas_total
from ..territorio import (
    COMUNA_DESCONOCIDA,
    DPA,
    cargar_dpa,
    formatear_cut_comuna,
    normalizar_serie_comunas,
    normalizar_texto,
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


#: El motivo que marca a una comuna cuya APS no administra el municipio. Es el único
#: centinela que sigue siendo verdad después de que la fuente dejó de escribirlo.
MOTIVO_SIN_SERVICIO = "sin_servicio_municipal"

#: Motivo con el que se marca un cero reinterpretado, para que se distinga en el dato
#: publicado de un cero que sí venía declarado como tal por la fuente.
MOTIVO_CERO_REINTERPRETADO = "sin_servicio_municipal_inferido"


#: Dependencias que administran APS municipal. `fonasa_inscritos` cuenta a los inscritos de
#: estos establecimientos y de nadie más.
DEPENDENCIAS_MUNICIPALES = ("municipal", "delegado")


def componer_aps_comunal(
    df: pd.DataFrame, dpa: DPA | None = None
) -> tuple[pd.DataFrame, dict]:
    """Cuenta, por comuna, cuánta de su atención primaria pública administra el municipio.

    Devuelve (silver, reporte) con una fila por `comuna_cut`: `aps_total`, `aps_municipal`,
    `aps_servicio_salud` y `fraccion_municipal`.

    **Para qué sirve.** `fonasa_inscritos` es un padrón de APS **municipal**; el REM cuenta
    actividad de toda la APS pública. Donde la comuna se atiende en un hospital comunitario
    del Servicio de Salud, numerador y denominador describen poblaciones distintas y la
    cobertura que salga de dividirlos no significa nada. Esta tabla dice dónde pasa eso.

    Medido sobre el maestro del 2026-07-21: de 344 comunas con APS pública, **204** la tienen
    enteramente municipal, **120** son mixtas y **20 no tienen ningún establecimiento
    municipal**. Entre estas últimas están Tocopilla, Andacollo, Isla de Pascua, Llaillay y
    Hualaihué, que son exactamente las que SINIM marca `Sin Servicio`: dos fuentes
    independientes coincidiendo sobre las mismas comunas.

    **Advertencia de vigencias.** El maestro es un corte actual. Aplicar esta composición a
    años anteriores atribuye al pasado la organización de hoy. Para una serie hace falta
    reconstruir vigencias con `fecha_inicio` y `fecha_cierre`, que esta función no hace.
    """
    reporte: dict = {"filas_entrada": len(df)}
    out = df.copy()

    for col in ("vigente", "nivel_atencion", "sistema_salud", "dependencia"):
        if col not in out.columns:
            raise ReconciliationError(
                f"[deis_establecimientos] falta la columna {col!r} para componer la APS. "
                f"Presentes: {list(out.columns)[:12]}."
            )

    aps = out[
        out["vigente"].fillna(False).astype(bool)
        & out["nivel_atencion"].eq("primario")
        & out["sistema_salud"].eq("publico")
    ].copy()
    reporte["aps_publica_vigente"] = len(aps)
    if aps.empty:
        raise ReconciliationError(
            "[deis_establecimientos] ningún establecimiento quedó como APS pública vigente. "
            "Revisar las glosas de nivel, estado y sistema antes de relajar el filtro."
        )

    aps["comuna_cut"], rep_cut = resolver_cut(aps["comuna_cut_fuente"], dpa=dpa)
    reporte.update(rep_cut)
    aps["_municipal"] = aps["dependencia"].isin(DEPENDENCIAS_MUNICIPALES)
    aps["_servicio"] = aps["dependencia"].eq("servicio de salud")

    agregado = (
        aps.groupby("comuna_cut")
        .agg(
            aps_total=("establecimiento_deis", "nunique"),
            aps_municipal=("_municipal", "sum"),
            aps_servicio_salud=("_servicio", "sum"),
        )
        .reset_index()
    )
    agregado["region_cut"] = agregado["comuna_cut"].str[:2]
    agregado["fraccion_municipal"] = agregado["aps_municipal"] / agregado["aps_total"]
    agregado = agregado.sort_values("comuna_cut").reset_index(drop=True)

    reporte["comunas_con_aps"] = len(agregado)
    reporte["comunas_solo_municipal"] = int((agregado["fraccion_municipal"] == 1).sum())
    reporte["comunas_mixtas"] = int(
        agregado["fraccion_municipal"].between(0, 1, inclusive="neither").sum()
    )
    reporte["comunas_sin_aps_municipal"] = int((agregado["fraccion_municipal"] == 0).sum())
    return agregado, reporte


#: Código SINIM de la variable que trae el total inscrito. El archivo puede traer además
#: los tramos etarios, que sirven para verificarlo (ver `quality.CODIGOS_TRAMOS_INSCRITOS`).
CODIGO_TOTAL_INSCRITOS = "HPISM"


def normalizar_inscritos(
    df: pd.DataFrame, dpa: DPA | None = None, variable: str = CODIGO_TOTAL_INSCRITOS
) -> tuple[pd.DataFrame, dict]:
    """Lleva la población inscrita en APS municipal de bronze a la grilla canónica.

    Devuelve (silver, reporte) con una fila por `comuna_cut × anio`, la población inscrita
    y el motivo cuando no hay número.

    **Acá se resuelve A-013 y es la razón de que esta función exista.** Hasta ~2019 SINIM
    escribía `Sin Servicio` en las comunas cuya atención primaria no administra el
    municipio sino el Servicio de Salud; desde entonces escribe `0`. La realidad no cambió:
    cambió la codificación. Un `0` en un denominador da división por cero o cobertura
    infinita, y como numerador afirma que no hay nadie inscrito en una comuna con CESFAM
    funcionando.

    La reinterpretación **necesita la serie completa de la comuna**, no una fila: se marca
    el cero solo si esa misma comuna declaró `Sin Servicio` en algún año. Por eso vive acá
    y no en el ingestor, que ve el archivo pero no debe inferir nada entre filas.

    No se imputa ningún valor. Una comuna sin APS municipal no tiene denominador comunal, y
    publicar una cobertura para ella sería inventarla.
    """
    reporte: dict = {"filas_entrada": len(df)}
    out = df.copy()

    if "_es_fila_total" in out.columns:
        marca_total = out["_es_fila_total"].fillna(False).astype(bool)
        reporte["filas_total_descartadas"] = int(marca_total.sum())
        out = out.loc[~marca_total].copy()

    # Un archivo puede traer varias variables. Quedarse con la del total se declara acá y
    # no se hereda de cómo se pidió la descarga: si mañana el pedido incluye una variable
    # más, esta función sigue devolviendo lo mismo.
    if "variable_codigo" in out.columns:
        disponibles = sorted(set(out["variable_codigo"]))
        out = out.loc[out["variable_codigo"] == variable].copy()
        if out.empty:
            raise ReconciliationError(
                f"[fonasa_inscritos] el archivo no trae la variable {variable!r}. "
                f"Disponibles: {disponibles}."
            )
        reporte["variable"] = variable
        reporte["variables_descartadas"] = [v for v in disponibles if v != variable]

    out["comuna_cut"], rep_cut = resolver_cut(out["comuna_cut_fuente"], dpa=dpa)
    reporte.update(rep_cut)
    out["region_cut"] = out["comuna_cut"].str[:2]
    out["motivo_sin_dato"] = out["motivo_sin_dato"].fillna("").astype(str)

    # Las comunas que alguna vez declararon no tener APS municipal. Se calcula sobre el
    # CUT resuelto y no sobre el código de la fuente: dos grafías del mismo código
    # partirían la comuna en dos y dejarían la mitad de sus ceros sin reinterpretar.
    sin_servicio = set(
        out.loc[out["motivo_sin_dato"] == MOTIVO_SIN_SERVICIO, "comuna_cut"].unique()
    )
    reporte["comunas_sin_servicio_municipal"] = len(sin_servicio)

    cero_sospechoso = (
        (out["poblacion_inscrita"] == 0)
        & (out["motivo_sin_dato"] == "")
        & out["comuna_cut"].isin(sin_servicio)
    )
    reporte["ceros_reinterpretados"] = int(cero_sospechoso.sum())
    out.loc[cero_sospechoso, "motivo_sin_dato"] = MOTIVO_CERO_REINTERPRETADO
    out.loc[cero_sospechoso, "poblacion_inscrita"] = pd.NA

    # Un cero que queda en pie es un cero de una comuna que nunca declaró «Sin Servicio».
    # No se toca: puede ser real y borrarlo sería falsificar el diagnóstico.
    reporte["ceros_conservados"] = int((out["poblacion_inscrita"] == 0).sum())

    dimensiones = ["comuna_cut", "region_cut", "anio"]
    agregado = (
        out[[*dimensiones, "poblacion_inscrita", "motivo_sin_dato"]]
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )
    duplicadas = agregado.duplicated(subset=dimensiones).sum()
    if duplicadas:
        raise ReconciliationError(
            f"[fonasa_inscritos] {duplicadas} pares comuna×año duplicados tras normalizar. "
            f"Un denominador con la comuna repetida se suma solo al unir y hunde la "
            f"cobertura sin que nada lo advierta."
        )

    reporte["filas_salida"] = len(agregado)
    con_dato = agregado["poblacion_inscrita"].notna()
    reporte["celdas_con_dato"] = int(con_dato.sum())
    reporte["inscritos_total"] = int(agregado.loc[con_dato, "poblacion_inscrita"].sum())
    reporte["motivos"] = (
        agregado.loc[agregado["motivo_sin_dato"] != "", "motivo_sin_dato"]
        .value_counts()
        .to_dict()
    )
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

    # El formulario escribe el nombre a veces en la columna de grupo y a veces en la de
    # concepto. Sin unificarlo, 2,2 millones de personas quedaban agrupadas bajo una
    # etiqueta vacía: no es que faltara el dato, es que el nombre estaba en la otra columna.
    grupo = out["grupo"].fillna("").astype(str).str.strip()
    concepto = out["concepto"].fillna("").astype(str).str.strip()
    out["etiqueta"] = concepto.where(concepto != "", grupo)
    reporte["conceptos_sin_etiqueta"] = int((out["etiqueta"] == "").sum())

    # El formulario escribe el mismo concepto con distinta grafía según el año:
    # «DEPRESIÓN MODERADA» y «Depresión moderada», «Síndrome de Rett» y «Síndrome de
    # rett», y hasta erratas propias como «post traumatico» sin tilde. Sin una llave
    # normalizada quedan como conceptos distintos: quien filtre por una forma pierde las
    # filas de la otra, y el total nacional se parte en dos sin que nada lo advierta.
    out["etiqueta_norm"] = out["etiqueta"].map(normalizar_texto).str.upper()
    reporte["etiquetas_distintas"] = int(out["etiqueta"].nunique())
    reporte["etiquetas_normalizadas"] = int(out["etiqueta_norm"].nunique())

    dimensiones = [
        "comuna_cut", "region_cut", "periodo", "codigo_prestacion", "grupo", "concepto",
        "etiqueta", "etiqueta_norm", "grupo_edad", "sexo", "es_total_etario",
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
    # El formulario trae algunos conteos con decimales, que son errores de digitación de
    # la fuente. No se redondean acá: se cuentan y se declaran (ver A-010).
    reporte["celdas_con_valor_fraccionario"] = int(
        (agregado["valor"].notna() & (agregado["valor"] % 1 != 0)).sum()
    )
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
