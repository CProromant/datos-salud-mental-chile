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
from ..indicators.tasas import (
    POBLACION_ESTANDAR_OMS_80,
    POR_DEFECTO,
    suavizado_eb_poisson_gamma,
    tasa_cruda,
    tasa_estandarizada_directa,
)
from ..io import ahora_iso
from ..quality import (
    K_SUPRESION_ACTIVIDAD,
    K_SUPRESION_MORTALIDAD,
    suprimir_celdas_pequenas,
    verificar_politica_publicacion,
)

DIMENSIONES_BASE = ["comuna_cut", "anio"]


def _unir_en_ventana(
    base: pd.DataFrame,
    conteos: pd.DataFrame,
    dimensiones: list[str],
    anios_cobertura: tuple[int, int] | None,
) -> tuple[pd.DataFrame, dict]:
    """Une denominador con numerador recortando a la ventana con datos en ambos lados.

    El recorte no es cosmético. Las proyecciones del INE llegan a 2035 y las defunciones a
    2023: sin él, el `fillna(0)` posterior publicaría doce años futuros con «cero
    suicidios» y tasa 0,0. Dentro de la ventana un cero significa «no hubo muertes»; fuera
    significa «no hay dato», y son afirmaciones opuestas.

    Devuelve además la ventana **efectiva**, que no siempre es la pedida: el numerador
    empieza en 1997 (primer año CIE-10) y el denominador en 2002, así que 1997-2001 se cae
    por no tener población. Esos casos no están en la salida y el reporte los declara, en
    vez de dejar que alguien lo deduzca comparando totales.
    """
    if "anio" not in dimensiones or not len(conteos):
        df = base.merge(conteos, on=dimensiones, how="left")
        df["casos"] = df["casos"].fillna(0).astype("Int64")
        return df, {"anios_cobertura": None, "filas_denominador_descartadas": 0}

    if anios_cobertura is None:
        anios_cobertura = (int(conteos["anio"].min()), int(conteos["anio"].max()))
    desde, hasta = anios_cobertura
    antes = len(base)
    base = base[base["anio"].between(desde, hasta)].copy()
    recorte: dict = {
        "anios_cobertura": [desde, hasta],
        "filas_denominador_descartadas": antes - len(base),
    }

    df = base.merge(conteos, on=dimensiones, how="left")
    df["casos"] = df["casos"].fillna(0).astype("Int64")

    if len(df):
        ef_desde, ef_hasta = int(df["anio"].min()), int(df["anio"].max())
        recorte["anios_efectivos"] = [ef_desde, ef_hasta]
        fuera = conteos[~conteos["anio"].between(ef_desde, ef_hasta)]
        recorte["casos_fuera_de_ventana"] = int(fuera["casos"].sum()) if len(fuera) else 0

    # Un caso puede caerse por no tener denominador aunque su año esté cubierto: pasa con
    # el centinela 99999 de «comuna ignorada» (A-007) y con cualquier código que la fuente
    # traiga y la DPA no reconozca. El join es sobre la población, así que esos casos
    # desaparecen sin dejar rastro. Publicar un total que no cuadra con el de la fuente y
    # no decir por qué es la forma más barata de perder la confianza en toda la serie.
    en_ventana = conteos[conteos["anio"].between(*recorte["anios_efectivos"])] if (
        recorte.get("anios_efectivos")
    ) else conteos
    perdidos = int(en_ventana["casos"].sum()) - int(df["casos"].sum())
    recorte["casos_sin_denominador"] = perdidos
    if perdidos:
        sin_pob = set(en_ventana[dimensiones[0]]) - set(df[dimensiones[0]])
        recorte["areas_sin_denominador"] = sorted(str(a) for a in sin_pob)[:20]
    return df, recorte


def estandarizar_por_edad(
    agregado: pd.DataFrame,
    poblacion: pd.DataFrame,
    dimensiones: list[str],
    col_edad: str = "grupo_edad",
    poblacion_estandar: dict[str, float] | None = None,
    por: int = POR_DEFECTO,
) -> pd.DataFrame:
    """Tasa estandarizada por edad (método directo) para cada área de `dimensiones`.

    Existe porque la tasa cruda no permite comparar territorios con estructuras etarias
    distintas: una comuna envejecida tiene más muertes por razones demográficas antes que
    sanitarias. La estandarización responde «cuánto moriría esta comuna si tuviera la
    estructura de edad de la población estándar».

    Ambas tablas deben traer `col_edad` con **la misma grilla**. Se usa por defecto el
    estándar OMS colapsado a `80+`, que es lo que permite el denominador del INE: con el
    estándar sin colapsar, `tasa_estandarizada_directa` descartaría el grupo abierto y
    devolvería una tasa calculada sin adultos mayores (ver `colapsar_estandar`).
    """
    estandar = poblacion_estandar or POBLACION_ESTANDAR_OMS_80
    faltan = [c for c in (*dimensiones, col_edad) if c not in poblacion.columns]
    if faltan:
        raise KeyError(f"La población no tiene las columnas {faltan} para estandarizar")

    llave = [*dimensiones, col_edad]
    pob = poblacion.groupby(llave, dropna=False)["poblacion"].sum()
    cas = agregado.groupby(llave, dropna=False)["casos"].sum()

    filas = []
    for clave, pob_area in pob.groupby(dimensiones, sort=False):
        idx = pob_area.reset_index().set_index(col_edad)["poblacion"]
        casos_area = cas.reindex(pob_area.index, fill_value=0).reset_index()
        casos_idx = casos_area.set_index(col_edad)["casos"].astype("float64")
        r = tasa_estandarizada_directa(casos_idx, idx, poblacion_estandar=estandar, por=por)
        valores = clave if isinstance(clave, tuple) else (clave,)
        fila = dict(zip(dimensiones, valores, strict=True))
        fila.update({
            "tasa_estandarizada": r["tasa_estandarizada"],
            "ee_estandarizada": r["error_estandar"],
            "ic95_inferior": r["ic95_inferior"],
            "ic95_superior": r["ic95_superior"],
            "grupos_edad_descartados": len(r["grupos_descartados"]),
        })
        filas.append(fila)
    return pd.DataFrame(filas)


def tasas_comunales(
    agregado: pd.DataFrame,
    poblacion: pd.DataFrame,
    agrupador_id: str,
    dimensiones: list[str] | None = None,
    grupo_suavizado: list[str] | None = None,
    anios_preliminares: tuple[int, ...] = (),
    anios_cobertura: tuple[int, int] | None = None,
    avpp: pd.DataFrame | None = None,
    estandarizar: bool = True,
    poblacion_estandar: dict[str, float] | None = None,
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

    `anios_cobertura` es (desde, hasta) inclusive y recorta el denominador a la ventana
    del numerador. Si se omite se infiere del rango de años del agregado. Importa
    porque las proyecciones del INE llegan a 2035 y las defunciones a 2023: sin recorte
    se publicarían años futuros con tasa cero.
    """
    dimensiones = dimensiones or DIMENSIONES_BASE
    faltan = [d for d in dimensiones if d not in poblacion.columns]
    if faltan:
        raise KeyError(f"La tabla de población no tiene las dimensiones {faltan}")

    base = poblacion.groupby(dimensiones, dropna=False)["poblacion"].sum().reset_index()
    conteos = agregado.groupby(dimensiones, dropna=False)["casos"].sum().reset_index()
    df, recorte = _unir_en_ventana(base, conteos, dimensiones, anios_cobertura)

    df["tasa_cruda"] = tasa_cruda(df["casos"].astype("float64"), df["poblacion"], por=por)

    # Estandarización por edad. Solo es posible si numerador y denominador conservan la
    # estructura etaria; si el agregado ya viene colapsado, no hay nada que estandarizar
    # y se dice en el reporte en vez de devolver una columna vacía sin explicación.
    puede_estandarizar = (
        estandarizar and "grupo_edad" in agregado.columns and "grupo_edad" in poblacion.columns
        and "grupo_edad" not in dimensiones
    )
    if puede_estandarizar:
        est = estandarizar_por_edad(
            agregado, poblacion, dimensiones, poblacion_estandar=poblacion_estandar, por=por
        )
        df = df.merge(est, on=dimensiones, how="left")

    if avpp is not None:
        cols = [*dimensiones, "avpp"]
        faltan_avpp = [c for c in cols if c not in avpp.columns]
        if faltan_avpp:
            raise KeyError(f"La tabla de AVPP no tiene las columnas {faltan_avpp}")
        df = df.merge(avpp[cols], on=dimensiones, how="left")
        df["avpp"] = df["avpp"].fillna(0.0)

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
    # Todo lo derivado del conteo se suprime con él. Dejar cualquiera de estas columnas
    # permite reconstruir el número suprimido:
    #   - `tasa_cruda`, multiplicando por la población;
    #   - `tasa_estandarizada` y su intervalo, que dependen del mismo numerador;
    #   - `avpp`, que es peor: con un solo caso revela la EDAD EXACTA del fallecido,
    #     porque el aporte es 80 − edad. Es el dato más identificable de toda la salida.
    derivadas = [
        "tasa_cruda", "tasa_estandarizada", "ee_estandarizada",
        "ic95_inferior", "ic95_superior", "avpp",
    ]
    for col in derivadas:
        if col in publicable.columns:
            publicable.loc[publicable["suprimido"], col] = pd.NA

    meta = {
        "agrupador": agrupador_id,
        "dimensiones": dimensiones,
        "filas": len(publicable),
        "cobertura": recorte,
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


def tabla_rem(
    silver: pd.DataFrame,
    dimensiones: list[str] | None = None,
    usar_total_etario: bool = True,
    k: int = K_SUPRESION_ACTIVIDAD,
    source_id: str = "rem_salud_mental",
    source_version: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Personas bajo control en salud mental, publicable, **en conteos y no en tasas**.

    No devuelve tasas a propósito. El denominador correcto para cobertura de atención
    primaria es la **población inscrita** en FONASA, no la proyección comunal del INE:
    dividir por la proyección incluye a quien se atiende en el sistema privado y produce
    un número que parece una cobertura y no lo es. Mientras `fonasa_inscritos` no esté
    verificada, se publican conteos, que son honestos por sí solos.

    `usar_total_etario` decide de cuál de las dos mitades del formulario sale la cifra. El
    REM trae, para cada concepto, una columna de total y diecisiete de detalle etario que
    cuentan a **la misma gente**: mezclarlas duplica personas. Con `True` se usa la fila de
    total; con `False`, el detalle, que permite desagregar por edad a cambio de más
    supresión.
    """
    dimensiones = dimensiones or ["comuna_cut", "periodo", "etiqueta_norm"]
    faltan = [d for d in (*dimensiones, "valor") if d not in silver.columns]
    if faltan:
        raise KeyError(f"El silver del REM no tiene las columnas {faltan}")

    sub = silver
    if "es_total_etario" in silver.columns:
        sub = silver[silver["es_total_etario"] == usar_total_etario]
    if "sexo" in sub.columns and "sexo" not in dimensiones:
        # Sumar «ambos sexos» con «hombres» y «mujeres» cuenta a cada persona dos veces:
        # las tres columnas describen la misma población.
        sub = sub[sub["sexo"] == "ambos"]

    df = (
        sub.groupby(dimensiones, dropna=False)["valor"]
        .sum()
        .reset_index()
        .rename(columns={"valor": "personas"})
        .sort_values(dimensiones)
        .reset_index(drop=True)
    )

    # Se agrupa por la llave normalizada, pero se publica una etiqueta legible: la
    # variante más frecuente en los datos. Elegirla por frecuencia y no por criterio
    # propio hace que la decisión sea reproducible y no dependa de quién la tomó.
    if "etiqueta_norm" in dimensiones and "etiqueta" in sub.columns:
        canonica = (
            sub.groupby(["etiqueta_norm", "etiqueta"]).size()
            .reset_index(name="n")
            .sort_values(["etiqueta_norm", "n"], ascending=[True, False])
            .drop_duplicates("etiqueta_norm")
            .set_index("etiqueta_norm")["etiqueta"]
        )
        df.insert(
            list(df.columns).index("etiqueta_norm"),
            "etiqueta", df["etiqueta_norm"].map(canonica),
        )

    df["source_id"] = source_id
    df["source_version"] = source_version
    df["pipeline_version"] = PIPELINE_VERSION
    df["fecha_calculo"] = ahora_iso()

    verificar_politica_publicacion(df)
    publicable, reporte_sup = suprimir_celdas_pequenas(
        df, "personas", k=k, grupo=[d for d in dimensiones if d != "comuna_cut"]
    )

    advertencias = [
        "Son CONTEOS de personas bajo control, no tasas ni cobertura. El denominador "
        "correcto (población inscrita en APS) no está disponible todavía.",
        "Población bajo control es un stock con corte semestral (junio y diciembre), "
        "no un flujo mensual: no se suman los períodos.",
    ]
    if reporte_sup.porcentaje_suprimido > 0.5:
        advertencias.append(
            f"Se suprimió el {reporte_sup.porcentaje_suprimido:.0%} de las celdas: a esta "
            f"desagregación el dato comunal aporta poco."
        )

    meta = {
        "fuente": source_id,
        "dimensiones": dimensiones,
        "filas": len(publicable),
        "origen_de_la_cifra": "total etario" if usar_total_etario else "detalle etario",
        "supresion": {
            "k": reporte_sup.k,
            "filas_suprimidas": reporte_sup.filas_suprimidas,
            "porcentaje": reporte_sup.porcentaje_suprimido,
        },
        "advertencias": advertencias,
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
