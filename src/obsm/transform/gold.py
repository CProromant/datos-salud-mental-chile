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
from ..errors import SuppressionViolationError
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
    refutar_denominador_con_numerador,
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


#: Clasificación del denominador según quién administra la APS de la comuna. No es una
#: escala de calidad: son tres situaciones distintas y solo una permite dividir.
DENOMINADOR_COMPLETO = "completo"
DENOMINADOR_PARCIAL = "parcial"
DENOMINADOR_AUSENTE = "ausente"

#: Bajo esta fracción, el padrón municipal describe a una minoría de la comuna y deja de
#: servirle de denominador. El corte es de **significado y no estadístico**: si la mayoría
#: de los habitantes no está en el padrón, el padrón no es el denominador de esa comuna.
#: Sin esto, Tiltil publica 397 personas en control por mil «inscritos» con un padrón que
#: cubre al 12 % de sus habitantes.
FRACCION_PADRON_MAYORITARIO = 0.5

#: Personas bajo control por cada mil inscritos. Se usa mil y no cien mil porque el
#: denominador es una población inscrita comunal, del orden de miles, y una tasa por
#: 100.000 sobre 8.000 inscritos comunica una precisión que el dato no tiene.
BASE_COBERTURA = 1_000


def tabla_cobertura(
    rem: pd.DataFrame,
    inscritos: pd.DataFrame,
    aps: pd.DataFrame,
    poblacion: pd.DataFrame | None = None,
    k: int = K_SUPRESION_ACTIVIDAD,
    source_version: str | None = None,
    version_inscritos: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Personas bajo control en salud mental **por cada mil inscritos** en la APS municipal.

    Es la tabla que `tabla_rem` no podía dar: convierte «108.496 personas con depresión
    moderada» en «de los inscritos, tantos por mil están en control». Requiere las tres
    entradas porque las tres hacen falta para que el número signifique algo:

    - `rem`: silver del REM, con `comuna_cut`, `periodo`, `etiqueta_norm`, `valor`.
    - `inscritos`: silver de `fonasa_inscritos` (`comuna_cut`, `anio`, `poblacion_inscrita`).
    - `aps`: silver de `deis_establecimientos` (`comuna_cut`, `fraccion_municipal`).
    - `poblacion`: silver del INE, opcional pero **muy recomendable**. Sin ella no se puede
      saber qué fracción de la comuna cubre el padrón, y comunas con un solo establecimiento
      municipal pasan como denominador completo cuando describen a una minoría.

    **Por qué `aps` no es opcional.** `inscritos` cuenta a los inscritos de la APS
    **municipal**; el REM cuenta actividad de **toda** la APS pública. Donde la comuna se
    atiende en un hospital comunitario del Servicio de Salud, el numerador incluye a esa
    población y el denominador no, y la división produce una cobertura inflada que se ve
    perfectamente creíble. Medido sobre el maestro del 2026-07-21, eso pasa en 134 de 344
    comunas, donde vive el 41 % de Chile. Sin esta tabla el error sería invisible.

    Cada fila declara su situación en `denominador`:

    - `completo`  — toda la APS de la comuna es municipal. La cobertura es interpretable.
    - `parcial`   — la comuna es mixta. La cobertura **sobreestima** y va sin valor.
    - `ausente`   — sin APS municipal, sin dato de inscritos, o el dato está marcado por
                    A-013/A-015. No hay denominador y no se calcula nada.

    Solo las filas `completo` llevan `cobertura_por_mil`. En las otras dos la columna queda
    nula: publicar un número con una advertencia al lado es publicar el número, porque la
    advertencia no viaja cuando alguien copia la celda.
    """
    for nombre, df, req in (
        ("rem", rem, ["comuna_cut", "periodo", "etiqueta_norm", "valor"]),
        ("inscritos", inscritos, ["comuna_cut", "anio", "poblacion_inscrita"]),
        ("aps", aps, ["comuna_cut", "fraccion_municipal"]),
    ):
        faltan = [c for c in req if c not in df.columns]
        if faltan:
            raise KeyError(f"El silver de {nombre} no tiene las columnas {faltan}")

    numerador, meta_rem = tabla_rem(rem, k=k, source_version=source_version)
    # `periodo` del REM es `YYYY-MM`; el denominador es anual. El año se saca del propio
    # período y no de una columna aparte: así no hay dos verdades sobre a qué año pertenece
    # una fila.
    numerador["anio"] = numerador["periodo"].str.slice(0, 4).astype("Int64")

    den = inscritos[["comuna_cut", "anio", "poblacion_inscrita"]].copy()
    for col in ("motivo_sin_dato", "total_menor_que_tramos", "denominador_implausible"):
        if col in inscritos.columns:
            den[col] = inscritos[col]

    df = numerador.merge(den, on=["comuna_cut", "anio"], how="left").merge(
        aps[["comuna_cut", "fraccion_municipal"]], on="comuna_cut", how="left"
    )

    # La regla dura: las personas bajo control son un subconjunto de las inscritas, así que
    # un numerador mayor que el denominador PRUEBA que el denominador está mal. Se aplica
    # acá y no en silver porque es el único punto donde conviven las dos cifras.
    df, rep_refutacion = refutar_denominador_con_numerador(df)

    # Un denominador se descarta por cualquiera de estas razones, y da igual cuál: el
    # resultado es el mismo, no se puede dividir.
    marcado = pd.Series(False, index=df.index)
    for col in (
        "total_menor_que_tramos", "denominador_implausible",
        "denominador_refutado", "comuna_refutada",
    ):
        if col in df.columns:
            marcado |= df[col].fillna(False).astype(bool)

    sin_dato = df["poblacion_inscrita"].isna() | df["poblacion_inscrita"].le(0) | marcado

    # Contar establecimientos es una garantía débil: Tiltil tiene **un solo** CESFAM
    # municipal, así que es «100 % municipal», y ese padrón cubre a 2.425 de sus 19.700
    # habitantes. Dividir ahí da 397 personas en control por mil inscritos, que no es una
    # cobertura sino el efecto de un denominador que describe al 12 % de la comuna.
    # Por eso la clasificación mira también qué fracción de la comuna está en el padrón.
    df["padron_sobre_poblacion"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if poblacion is not None:
        tot = poblacion.groupby(["comuna_cut", "anio"], as_index=False)["poblacion"].sum()
        df = df.merge(tot, on=["comuna_cut", "anio"], how="left")
        con_ref = df["poblacion"].notna() & df["poblacion"].gt(0)
        df.loc[con_ref, "padron_sobre_poblacion"] = (
            df.loc[con_ref, "poblacion_inscrita"].astype("Float64")
            / df.loc[con_ref, "poblacion"].astype("Float64")
        ).round(4)
        df = df.drop(columns=["poblacion"])
        # Recalcular las máscaras: el merge pudo reordenar el índice.
        marcado = marcado.reindex(df.index, fill_value=False)
        sin_dato = sin_dato.reindex(df.index, fill_value=True)

    # El corte es de significado, no estadístico: si la mayoría de los habitantes de la
    # comuna no está en el padrón, el padrón no es el denominador de esa comuna.
    padron_minoritario = df["padron_sobre_poblacion"].notna() & df[
        "padron_sobre_poblacion"
    ].lt(FRACCION_PADRON_MAYORITARIO)

    frac = df["fraccion_municipal"]
    df["denominador"] = DENOMINADOR_PARCIAL
    df.loc[frac.eq(1) & ~sin_dato & ~padron_minoritario, "denominador"] = (
        DENOMINADOR_COMPLETO
    )
    df.loc[sin_dato | frac.isna() | frac.eq(0), "denominador"] = DENOMINADOR_AUSENTE

    calculable = df["denominador"].eq(DENOMINADOR_COMPLETO) & df["personas"].notna()
    # Se declara `Float64` y no se deja que pandas infiera: inicializar con `pd.NA` y
    # asignar por máscara deja la columna en `object`, que sobrevive a `to_parquet` y hace
    # fallar cualquier promedio o ranking aguas abajo. Un denominador nulo produce el
    # mismo `NA` que una celda no calculable, así que la división no se protege aparte.
    df["cobertura_por_mil"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.loc[calculable, "cobertura_por_mil"] = (
        df.loc[calculable, "personas"].astype("Float64")
        / df.loc[calculable, "poblacion_inscrita"].astype("Float64")
        * BASE_COBERTURA
    ).round(2)

    df["poblacion_version"] = version_inscritos
    df["fecha_calculo"] = ahora_iso()
    verificar_politica_publicacion(df)

    reparto = df["denominador"].value_counts().to_dict()
    comunas_pub = df.loc[
        df["denominador"].eq(DENOMINADOR_COMPLETO), "comuna_cut"
    ].nunique()
    meta = {
        "fuente": "rem_salud_mental / fonasa_inscritos / deis_establecimientos",
        "filas": len(df),
        "base": BASE_COBERTURA,
        "celdas_por_denominador": reparto,
        "comunas_con_cobertura": comunas_pub,
        "comunas_en_el_numerador": int(df["comuna_cut"].nunique()),
        "fraccion_padron_minima": FRACCION_PADRON_MAYORITARIO,
        "supresion_numerador": meta_rem["supresion"],
        "refutacion_por_numerador": rep_refutacion,
        "advertencias": [
            "La cobertura solo se calcula donde TODA la APS de la comuna es municipal "
            f"({comunas_pub} comunas). Es la única situación en que numerador y "
            "denominador describen la misma población.",
            "En comunas mixtas el denominador cuenta solo a los inscritos municipales "
            "mientras el REM cuenta toda la APS pública: la cobertura sobreestimaría. "
            "Esas filas van con `denominador=parcial` y sin valor.",
            "No es prevalencia ni necesidad. Mide quién llegó al sistema y quedó en "
            "control; una cobertura baja puede ser poca enfermedad o poca capacidad.",
            "El denominador de 2023 no existe: SINIM lo publica como «No Recepcionado» "
            "en las 345 comunas.",
            "Población bajo control es un stock semestral. No se suman los períodos.",
        ],
    }
    return df, meta


#: Las tres listas de espera que publica el visualizador, con su nombre legible.
LISTAS_ESPERA = {
    "consulta": "Consulta nueva de especialidad (No GES)",
    "quirurgica": "Intervención quirúrgica (No GES)",
    "ges": "Garantías de oportunidad GES retrasadas",
}

#: Primer año con medianas publicadas. Antes de esto la fuente no las calculaba, y el nulo
#: no es un dato faltante al azar.
PRIMER_ANIO_CON_MEDIANA = 2022


def tabla_listas_espera(
    silver: pd.DataFrame,
    k: int = K_SUPRESION_ACTIVIDAD,
    source_id: str = "listaespera_minsal",
    source_version: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Listas de espera por Servicio de Salud y trimestre, publicable.

    Pasa la grilla ancha de silver —doce columnas de lista × métrica— a una fila por
    `servicio × periodo × lista`, que es la forma en que se lee y se grafica sin tener que
    recordar qué prefijo significa qué.

    **La unidad territorial es el Servicio de Salud, no la comuna**, y no se baja a comuna:
    repartir la mediana de un Servicio entre sus comunas es una inferencia ecológica.
    `silver.mapa_servicio_comuna` permite hacerlo explícitamente a quien lo necesite, y
    muestra por qué no puede venir regalado: cuatro comunas pertenecen a dos Servicios.

    **Supresión con k=5 sobre `registros`, y hace falta de verdad.** Las garantías GES
    retrasadas bajan a valores de una cifra: 39 celdas entre 1 y 9. Que la unidad sea un
    Servicio de medio millón de personas hace el riesgo remoto, pero la política de
    `docs/06` no se relaja caso a caso (`docs/09`): eso es precisamente lo que la vuelve
    una política. **La supresión complementaria no es opcional acá**: la fila nacional es
    exactamente la suma de los 29 servicios —verificado, diferencia 0 en
    `consulta_registros`—, así que suprimir una sola celda la deja reconstruible por resta.

    El cero **sí se publica**: cero garantías retrasadas no identifica a nadie y es la
    información más útil de la columna.
    """
    faltan = [c for c in ("servicio_clave", "periodo") if c not in silver.columns]
    if faltan:
        raise KeyError(f"El silver de listas de espera no tiene las columnas {faltan}")

    partes = []
    for lista, nombre in LISTAS_ESPERA.items():
        cols = {
            f"{lista}_registros": "registros",
            f"{lista}_pacientes": "pacientes",
            f"{lista}_promedio": "promedio_dias",
            f"{lista}_mediana": "mediana_dias",
        }
        presentes = {k_: v for k_, v in cols.items() if k_ in silver.columns}
        if not presentes:
            continue
        sub = silver[["servicio_clave", "periodo", *presentes]].rename(columns=presentes)
        sub.insert(2, "lista", lista)
        sub.insert(3, "lista_nombre", nombre)
        partes.append(sub)
    df = pd.concat(partes, ignore_index=True)

    df["anio"] = df["periodo"].str.slice(0, 4).astype("Int64")
    df["es_nacional"] = df["servicio_clave"].eq("NACIONAL")
    # La mediana no existe antes de 2022 y el nulo no es un faltante al azar. Se marca para
    # que una serie de tendencia sepa dónde empieza en vez de deducirlo de los huecos.
    df["mediana_disponible"] = df["anio"] >= PRIMER_ANIO_CON_MEDIANA

    df["source_id"] = source_id
    df["source_version"] = source_version
    df["pipeline_version"] = PIPELINE_VERSION
    df["fecha_calculo"] = ahora_iso()
    verificar_politica_publicacion(df)

    # La fila nacional queda fuera del grupo de supresión: es un total, no un par de los
    # servicios, y meterla en el grupo la haría candidata a suprimirse a sí misma.
    servicios = df.loc[~df["es_nacional"]].copy()
    nacional = df.loc[df["es_nacional"]].copy()
    publicable, reporte_sup = suprimir_celdas_pequenas(
        servicios, "registros", k=k, grupo=["periodo", "lista"]
    )
    nacional["suprimido"] = False
    publicable = (
        pd.concat([publicable, nacional], ignore_index=True)
        .sort_values(["lista", "periodo", "servicio_clave"])
        .reset_index(drop=True)
    )

    con_mediana = publicable["mediana_dias"].notna()
    meta = {
        "fuente": source_id,
        "filas": len(publicable),
        "servicios": int(publicable.loc[~publicable["es_nacional"], "servicio_clave"].nunique()),
        "periodos": int(publicable["periodo"].nunique()),
        "rango": [publicable["periodo"].min(), publicable["periodo"].max()],
        "listas": list(LISTAS_ESPERA),
        "supresion": {
            "k": reporte_sup.k,
            "filas_suprimidas": reporte_sup.filas_suprimidas,
            "complementarias": reporte_sup.filas_suprimidas_complementarias,
            "porcentaje": reporte_sup.porcentaje_suprimido,
        },
        "cobertura_mediana": round(float(con_mediana.mean()), 3),
        "advertencias": [
            "La unidad territorial es el Servicio de Salud, NO la comuna. Repartir estos "
            "valores entre las comunas de un Servicio es una inferencia ecológica; cuatro "
            "comunas además pertenecen a dos Servicios a la vez.",
            f"La mediana de días no existe antes de {PRIMER_ANIO_CON_MEDIANA}: la fuente no "
            f"la calculaba. Una tendencia que arranque antes compara contra vacío. La "
            f"columna `mediana_disponible` lo declara fila por fila.",
            "«Registros» no es «personas»: una persona puede tener varias interconsultas en "
            "espera. Ambas columnas están y no son intercambiables.",
            "La espera se cuenta desde la emisión de la interconsulta, no desde que la "
            "persona empezó a necesitar atención: subestima la espera vivida.",
            "Una baja puede deberse a depuración administrativa de la lista y no a más "
            "atención.",
            "No hay desglose por especialidad: estas cifras suman todas. Para psiquiatría "
            "hay que ir al PDF de la Glosa 06, que a su vez no publica días de espera.",
        ],
    }
    return publicable, meta


def tabla_espera_especialidad(
    bronze: pd.DataFrame,
    k: int = K_SUPRESION_ACTIVIDAD,
    source_id: str = "glosa06",
    source_version: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Registros en lista de espera por especialidad médica y trimestre, publicable.

    Es la **única** fuente pública que aísla la espera por psiquiatría: 23.134 adultos y
    12.585 niños y adolescentes al 31 de marzo de 2026.

    **La serie es corta a propósito y crece de a un trimestre.** No es una limitación del
    código: solo hay dos informes descargables desde el índice del MINSAL, y los nombres de
    archivo no siguen patrón, así que los históricos hay que ir consiguiéndolos. Publicar
    dos trimestres y decirlo es más útil que esperar a tener diez.

    **La cifra es nacional.** El informe no cruza especialidad con Servicio de Salud, así
    que no se puede decir cuánto se espera por psiquiatría en una región — aunque la letra
    b) de la propia glosa lo exija. Ver A-015 y la ficha de I-06.
    """
    faltan = [c for c in ("periodo", "especialidad_norm", "registros") if c not in bronze.columns]
    if faltan:
        raise KeyError(f"El bronze de la Glosa 06 no tiene las columnas {faltan}")

    df = bronze.copy()
    df["unidad_territorial"] = "nacional"
    df["source_id"] = source_id
    df["source_version"] = source_version
    df["pipeline_version"] = PIPELINE_VERSION
    df["fecha_calculo"] = ahora_iso()
    verificar_politica_publicacion(df)

    publicable, reporte_sup = suprimir_celdas_pequenas(
        df, "registros", k=k, grupo=["periodo"]
    )
    publicable = publicable.sort_values(["periodo", "especialidad_norm"]).reset_index(drop=True)

    sm = publicable[publicable.get("es_salud_mental", False)]
    meta = {
        "fuente": source_id,
        "filas": len(publicable),
        "periodos": sorted(publicable["periodo"].unique().tolist()),
        "especialidades": int(publicable["especialidad_norm"].nunique()),
        "salud_mental": {
            p: {r.etiqueta: int(r.registros) for r in g.itertuples() if pd.notna(r.registros)}
            for p, g in sm.groupby("periodo")
        },
        "supresion": {
            "k": reporte_sup.k,
            "filas_suprimidas": reporte_sup.filas_suprimidas,
            "porcentaje": reporte_sup.porcentaje_suprimido,
        },
        "advertencias": [
            "La cifra es NACIONAL. El informe no cruza especialidad con Servicio de Salud, "
            "así que no dice cuánto se espera por psiquiatría en una región concreta.",
            "«Registros» no es «personas»: una persona puede tener varias interconsultas.",
            "La espera se cuenta desde la emisión de la interconsulta, no desde que la "
            "persona empezó a necesitar atención.",
            "El informe de 2026-03 no suma su propio total declarado: faltan 11.478 "
            "registros (0,58 %). No usar esta tabla para calcular participaciones. "
            "Ver A-018 en docs/05-CALIDAD.md.",
            "La serie tiene solo los trimestres cuyo PDF se pudo descargar. Los nombres de "
            "archivo publicados no siguen patrón y hay que conseguirlos uno a uno.",
        ],
    }
    return publicable, meta


#: Conceptos del REM que cuentan personas en control por conducta suicida. La llave es la
#: etiqueta normalizada; el valor, el nombre publicable.
CONCEPTOS_CONDUCTA_SUICIDA = {
    "IDEACION": "Ideación suicida",
    "INTENTO": "Intento suicida",
}

#: Primer corte en que el REM registra estos conceptos. Antes no es que fueran cero: no se
#: preguntaban. Una serie que arranque antes lee un quiebre de formulario como una epidemia.
PRIMER_PERIODO_CONDUCTA_SUICIDA = "2019-06"


def tabla_ideacion_intento(
    silver: pd.DataFrame,
    recursos_ayuda: list[str],
    k: int = K_SUPRESION_ACTIVIDAD,
    source_id: str = "rem_salud_mental",
    source_version: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Personas en control por ideación e intento suicida, con las salvaguardas de docs/06.

    **`recursos_ayuda` es obligatorio y el código se niega a producir la tabla sin él.**
    `docs/06` exige que toda salida pública que incluya suicidio lleve enlace a recursos de
    ayuda vigentes en Chile, **verificados en la fecha de publicación**, porque un número
    desactualizado en un producto sobre suicidio es un daño concreto. Hacerlo obligatorio en
    la firma convierte esa regla en algo que no se puede olvidar: no hay valor por defecto
    que un descuido pueda dejar pasar, y este módulo no los inventa porque no le consta que
    estén vigentes hoy.

    **Lo que esta serie NO es.** Personas bajo control por ideación o intento es un *stock*
    de quién está en tratamiento, no un conteo de eventos. Que suba puede significar más
    conducta suicida, más detección, o más gente que llegó a atenderse — y las tres tienen
    implicancias de política opuestas. La serie nacional pasa de 3.624 a 17.023 en ideación
    entre 2019 y 2025; leer eso como «la ideación se quintuplicó» es casi seguramente un
    error de lectura.

    **El quiebre de serie es duro.** El REM no registraba estos conceptos antes de
    2019-06. No aparecen como cero: no existían en el formulario. La tabla se recorta ahí y
    lo declara.
    """
    if not recursos_ayuda:
        raise SuppressionViolationError(
            "[rem_salud_mental] `recursos_ayuda` es obligatorio para publicar una tabla "
            "que incluye conducta suicida (docs/06). Deben ser recursos vigentes en Chile "
            "verificados en la fecha de publicación; el pipeline no los inventa ni trae "
            "valores por defecto, porque un número de ayuda desactualizado en un producto "
            "sobre suicidio es un daño concreto y no un detalle de forma."
        )

    faltan = [c for c in ("comuna_cut", "periodo", "etiqueta_norm", "valor")
              if c not in silver.columns]
    if faltan:
        raise KeyError(f"El silver del REM no tiene las columnas {faltan}")

    sub = silver[silver["etiqueta_norm"].isin(CONCEPTOS_CONDUCTA_SUICIDA)]
    if "es_total_etario" in sub.columns:
        sub = sub[sub["es_total_etario"]]
    if "sexo" in sub.columns:
        sub = sub[sub["sexo"] == "ambos"]

    antes = len(sub)
    sub = sub[sub["periodo"] >= PRIMER_PERIODO_CONDUCTA_SUICIDA]
    recortadas = antes - len(sub)

    df = (
        sub.groupby(["comuna_cut", "periodo", "etiqueta_norm"], dropna=False)["valor"]
        .sum().reset_index().rename(columns={"valor": "personas"})
    )
    df["concepto"] = df["etiqueta_norm"].map(CONCEPTOS_CONDUCTA_SUICIDA)
    df["source_id"] = source_id
    df["source_version"] = source_version
    df["pipeline_version"] = PIPELINE_VERSION
    df["fecha_calculo"] = ahora_iso()
    verificar_politica_publicacion(df)

    publicable, reporte_sup = suprimir_celdas_pequenas(
        df, "personas", k=k, grupo=["periodo", "etiqueta_norm"]
    )
    publicable = publicable.sort_values(
        ["periodo", "etiqueta_norm", "comuna_cut"]
    ).reset_index(drop=True)

    meta = {
        "fuente": source_id,
        "filas": len(publicable),
        "conceptos": list(CONCEPTOS_CONDUCTA_SUICIDA.values()),
        "primer_periodo": PRIMER_PERIODO_CONDUCTA_SUICIDA,
        "filas_anteriores_al_quiebre_descartadas": recortadas,
        "supresion": {
            "k": reporte_sup.k,
            "filas_suprimidas": reporte_sup.filas_suprimidas,
            "porcentaje": reporte_sup.porcentaje_suprimido,
        },
        "recursos_ayuda": list(recursos_ayuda),
        "revision_clinica": "PENDIENTE — docs/06 la exige antes de publicar",
        "advertencias": [
            "ES UN STOCK, NO UN CONTEO DE EVENTOS. Son personas bajo control en el "
            "programa, no intentos ocurridos en el período. No se suman los cortes.",
            "UNA SUBIDA NO SIGNIFICA MÁS CONDUCTA SUICIDA. Puede ser más detección, más "
            "acceso o un cambio de registro. La serie nacional de ideación pasa de 3.624 "
            "(2019) a 17.023 (2025) y esa magnitud es difícil de atribuir a la conducta.",
            f"LA SERIE EMPIEZA EN {PRIMER_PERIODO_CONDUCTA_SUICIDA}. Antes el REM no "
            f"registraba estos conceptos: no son ceros, no existían en el formulario.",
            "Solo cubre la red pública. Quien se atiende en el sistema privado no aparece.",
            "No permite rankear comunas: con eventos poco frecuentes en territorios chicos, "
            "un orden ordena ruido y estigmatiza.",
            "REVISIÓN CLÍNICA PENDIENTE. docs/06 la exige antes de cualquier publicación "
            "que incluya suicidio.",
        ],
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
