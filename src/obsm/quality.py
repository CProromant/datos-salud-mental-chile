"""Reglas de calidad, supresión estadística y reconciliación.

Todo lo que se escribe en `gold` pasa por acá. La lógica está centralizada a
propósito: la supresión implementada ad hoc en cada script es la forma más común
de filtrar celdas pequeñas sin darse cuenta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from .cie10 import DIMENSIONES_PROHIBIDAS_PUBLICACION, es_publicable
from .errors import ReconciliationError, SuppressionViolationError

#: Umbral por defecto para conteos de mortalidad a nivel comunal.
#: Más exigente que el habitual (5) porque el evento es sensible y el territorio, chico.
K_SUPRESION_MORTALIDAD = 10
#: Umbral para conteos de actividad asistencial (menos sensible, sin riesgo de
#: identificación de un fallecido en una comuna pequeña).
K_SUPRESION_ACTIVIDAD = 5

#: Un prefijo "total"/"subtotal" al inicio de la celda es señal inequívoca.
#: "Totoral" no matchea porque \b exige frontera de palabra tras "total".
_RE_TOTAL_PREFIJO = re.compile(r"^\s*(sub)?total(es)?\b", re.IGNORECASE)

#: Palabras que solo son señal de total cuando ocupan la celda COMPLETA.
#: Como prefijo darían falsos positivos reales: "País Vasco S.A." no es un total.
_CELDAS_TOTAL = {
    "pais",
    "total pais",
    "total general",
    "total servicio",
    "total nacional",
    "nacional",
    "resumen",
}


@dataclass
class ReporteSupresion:
    filas_totales: int
    filas_suprimidas: int
    filas_suprimidas_complementarias: int
    k: int

    @property
    def porcentaje_suprimido(self) -> float:
        return self.filas_suprimidas / self.filas_totales if self.filas_totales else 0.0


def _columnas_texto(df: pd.DataFrame) -> list[str]:
    """Columnas que contienen texto.

    Ojo: en pandas < 3 las columnas de texto son `object`; desde pandas 3 el dtype
    por defecto es `str`. Filtrar solo por `== object` funciona en una versión y
    devuelve una lista vacía en la otra, sin error visible. Por eso se pregunta por
    "no numérica" en vez de por un dtype concreto.
    """
    return [
        c
        for c in df.columns
        if not pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_bool_dtype(df[c])
        and not pd.api.types.is_datetime64_any_dtype(df[c])
    ]


def detectar_filas_total(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.Series:
    """Marca filas que son totales o subtotales mezclados con el detalle.

    Sumar una tabla que trae sus propios totales duplica exactamente el país, y el
    error pasa desapercibido porque el resultado "se ve razonable".
    """
    from .territorio import normalizar_texto  # import local: evita ciclo en carga

    columnas = columnas or _columnas_texto(df)
    marca = pd.Series(False, index=df.index)
    for col in columnas:
        serie = df[col].astype(str)
        marca |= serie.str.match(_RE_TOTAL_PREFIJO).fillna(False)
        marca |= serie.map(lambda v: normalizar_texto(v) in _CELDAS_TOTAL).fillna(False)
    return marca


def suprimir_celdas_pequenas(
    df: pd.DataFrame,
    col_conteo: str,
    k: int = K_SUPRESION_MORTALIDAD,
    grupo: list[str] | None = None,
    valor_suprimido=pd.NA,
) -> tuple[pd.DataFrame, ReporteSupresion]:
    """Suprime celdas con conteo entre 1 y k-1, más supresión complementaria.

    El cero **no** se suprime: informar cero eventos no identifica a nadie y es
    información relevante. Sí se suprimen los valores 1..k-1.

    Supresión complementaria: si dentro de un grupo queda exactamente una celda
    suprimida y se conoce el total del grupo, la celda es reconstruible por resta.
    En ese caso se suprime además la celda no suprimida de menor valor.

    Devuelve una copia; nunca muta el DataFrame de entrada.
    """
    out = df.copy()
    conteo = pd.to_numeric(out[col_conteo], errors="coerce")
    riesgo = (conteo >= 1) & (conteo < k)
    complementarias = 0

    if grupo:
        for _, sub in out.groupby(grupo, dropna=False, sort=False):
            idx = sub.index
            sup_en_grupo = riesgo.loc[idx]
            if sup_en_grupo.sum() == 1:
                candidatos = conteo.loc[idx][~sup_en_grupo].dropna()
                if len(candidatos) > 0:
                    riesgo.loc[candidatos.idxmin()] = True
                    complementarias += 1

    out.loc[riesgo, col_conteo] = valor_suprimido
    out["suprimido"] = riesgo.values
    reporte = ReporteSupresion(
        filas_totales=len(out),
        filas_suprimidas=int(riesgo.sum()),
        filas_suprimidas_complementarias=complementarias,
        k=k,
    )
    return out, reporte


def verificar_politica_publicacion(df: pd.DataFrame, agrupador_id: str | None = None) -> None:
    """Falla si la tabla contiene una dimensión prohibida o un detalle no publicable."""
    prohibidas = set(df.columns) & DIMENSIONES_PROHIBIDAS_PUBLICACION
    if prohibidas:
        raise SuppressionViolationError(
            f"La tabla contiene dimensiones prohibidas para publicación: {sorted(prohibidas)}. "
            f"Ver docs/06-ETICA-Y-DATOS.md."
        )
    if agrupador_id and not es_publicable(agrupador_id, nivel_detalle="agrupador"):
        raise SuppressionViolationError(f"Agrupador no publicable: {agrupador_id}")
    if agrupador_id in {"SUICIDIO", "LESION_AUTOINFLIGIDA_MORBILIDAD"}:
        # Un desglose por código dentro de estos agrupadores equivale a publicar método.
        col_codigo = {"codigo_cie10", "causa_cie10", "codigo"} & set(df.columns)
        for col in col_codigo:
            distintos = df[col].astype(str).str.upper().str[:4].nunique()
            if distintos > 1:
                raise SuppressionViolationError(
                    f"La tabla desglosa {agrupador_id} por '{col}' ({distintos} códigos): "
                    f"equivale a publicar método de suicidio. Agregar antes de publicar."
                )


def verificar_reconciliacion(
    valor_calculado: float,
    valor_oficial: float,
    tolerancia_relativa: float = 0.005,
    etiqueta: str = "",
) -> float:
    """Compara un total calculado contra un ancla oficial. Devuelve la diferencia relativa.

    Sin esta verificación el pipeline puede estar perfectamente ordenado y
    perfectamente equivocado.
    """
    if valor_oficial == 0:
        raise ReconciliationError(f"Ancla oficial en cero para {etiqueta!r}")
    dif = abs(valor_calculado - valor_oficial) / abs(valor_oficial)
    if dif > tolerancia_relativa:
        raise ReconciliationError(
            f"Reconciliación fallida {etiqueta!r}: calculado={valor_calculado:,.0f} "
            f"oficial={valor_oficial:,.0f} diferencia={dif:.2%} "
            f"tolerancia={tolerancia_relativa:.2%}"
        )
    return dif


def validar_sin_duplicados(df: pd.DataFrame, llave: list[str]) -> None:
    """La llave primaria declarada debe ser única. Si no, hay doble conteo."""
    dup = df.duplicated(subset=llave, keep=False)
    if dup.any():
        ejemplos = df.loc[dup, llave].drop_duplicates().head(5).to_dict("records")
        raise ValueError(f"Llave {llave} duplicada en {int(dup.sum())} filas. Ejemplos: {ejemplos}")


#: Variables etarias que SINIM publica junto al total inscrito.
#:
#: **No son el desglose del total, y confundirlas cuesta caro.** El total (`HPISM`) dice
#: «Población Inscrita Validada en Servicios de Salud **Municipal**»; estas dicen «Población
#: Validada como **Beneficiaria** por FONASA». Son universos distintos: beneficiario de
#: FONASA es cualquiera cubierto por el seguro, viva donde viva su CESFAM; inscrito
#: municipal es quien está registrado en un establecimiento que administra el municipio.
#:
#: En la mayoría de las comunas casi coinciden, y por eso durante dieciocho años el total
#: superó a esta suma en las 4.863 celdas comparables. Divergen justo donde la APS **no** la
#: administra el municipio: ahí los beneficiarios siguen siendo miles y los inscritos
#: municipales pueden ser once. Verificado contra el archivo de FONASA (A-015).
CODIGOS_TRAMOS_BENEFICIARIOS = ("HPVM6", "HPV2064", "HPVM64")

#: Alias histórico. El nombre anterior decía «INSCRITOS» y esa era justamente la confusión.
CODIGOS_TRAMOS_INSCRITOS = CODIGOS_TRAMOS_BENEFICIARIOS


def marcar_total_incoherente_con_tramos(
    inscritos: pd.DataFrame,
    tramos: pd.DataFrame,
    codigos: tuple[str, ...] = CODIGOS_TRAMOS_BENEFICIARIOS,
) -> tuple[pd.DataFrame, dict]:
    """Marca las comunas donde los inscritos municipales no cubren a los beneficiarios.

    Devuelve (inscritos + `total_menor_que_tramos` + `razon_tramos`, reporte). **No corrige
    ningún valor.**

    Qué detecta realmente: que la APS de esa comuna **no es municipal**, o lo es solo en
    parte. Cuando el hospital comunitario del Servicio de Salud atiende a la población y el
    municipio solo administra una posta rural, el denominador municipal cae a un puñado de
    personas mientras los beneficiarios FONASA siguen siendo toda la comuna. Quirihue 2022:
    11 inscritos municipales —una posta— y ~4.200 beneficiarios adultos.

    **Qué NO detecta: un error.** Esta función se escribió creyendo que los tramos eran el
    desglose etario del total y que `total < suma(tramos)` era imposible por construcción.
    Es falso: son universos distintos (ver `CODIGOS_TRAMOS_BENEFICIARIOS`). La desigualdad
    se cumple casi siempre por magnitud, no por definición, y donde se rompe el dato está
    bien: lo que falla es suponer que el denominador municipal sirve para toda la comuna.

    Sigue siendo útil justamente por eso. El REM cuenta actividad de **toda** la APS
    pública, municipal y dependiente del Servicio de Salud; este denominador cuenta solo la
    municipal. Donde divergen, la cobertura calculada con ambos no significa nada, y esta
    marca es la señal de que no significa nada.

    `tramos` es la tabla larga de bronze con `comuna_cut`, `anio`, `variable_codigo` y
    `poblacion_inscrita`.
    """
    presentes = sorted(set(tramos["variable_codigo"]) & set(codigos))
    faltantes = [c for c in codigos if c not in presentes]

    ancho = (
        tramos[tramos["variable_codigo"].isin(codigos)]
        .pivot_table(
            index=["comuna_cut", "anio"],
            columns="variable_codigo",
            values="poblacion_inscrita",
            aggfunc="sum",
        )
        .reset_index()
    )
    # min_count exige los tres tramos: con uno faltante la suma sería una cota más baja de
    # lo que corresponde y la comparación acusaría coherencia donde no la hay.
    columnas = [c for c in codigos if c in ancho.columns]
    ancho["_cota"] = ancho[columnas].sum(axis=1, min_count=len(codigos)) if columnas else pd.NA

    out = inscritos.merge(
        ancho[["comuna_cut", "anio", "_cota"]], on=["comuna_cut", "anio"], how="left"
    )
    comparable = out["poblacion_inscrita"].notna() & out["_cota"].notna()
    out["razon_tramos"] = out["poblacion_inscrita"] / out["_cota"].where(out["_cota"] > 0)
    out["total_menor_que_tramos"] = comparable & (out["poblacion_inscrita"] < out["_cota"])

    reporte = {
        "tramos_esperados": list(codigos),
        "tramos_faltantes": faltantes,
        "celdas_comparables": int(comparable.sum()),
        "celdas_incoherentes": int(out["total_menor_que_tramos"].sum()),
        "comunas_incoherentes": int(out.loc[out["total_menor_que_tramos"], "comuna_cut"].nunique()),
        "anios_incoherentes": sorted(
            int(a) for a in out.loc[out["total_menor_que_tramos"], "anio"].unique()
        ),
    }
    return out.drop(columns=["_cota"]), reporte


def refutar_denominador_con_numerador(
    df: pd.DataFrame,
    col_numerador: str = "personas",
    col_denominador: str = "poblacion_inscrita",
) -> tuple[pd.DataFrame, dict]:
    """Refuta un denominador cuando el numerador lo supera, y extiende el defecto a la serie.

    Devuelve (df + `denominador_refutado` + `comuna_refutada`, reporte).

    **La regla dura.** Las personas bajo control en la APS son un **subconjunto** de las
    inscritas en ella: nadie está en control sin estar inscrito. Entonces
    `numerador > denominador` no es improbable, es **imposible**, y prueba que el denominador
    no describe a esa población. No hay umbral que elegir.

    Es la tercera comprobación independiente sobre esta fuente, y hace falta porque las otras
    dos dejan pasar casos:

    - `marcar_total_incoherente_con_tramos` prueba la contradicción dentro del propio
      denominador, pero calla cuando el total y sus tramos se rompen juntos, que es lo que
      pasa en 2025.
    - `FRACCION_MINIMA_INSCRITOS` compara contra el INE con un umbral **elegido a mano** del
      1 %, y resultó demasiado laxo: Sierra Gorda declara 24 inscritos sobre 1.806
      habitantes —un 1,33 %— y pasó el filtro para producir una cobertura de **11.458 por
      mil**. Queda como señal secundaria, no como criterio.

    **Por qué se propaga a toda la serie de la comuna.** El defecto no es de una celda sino
    del régimen con que esa comuna reporta: son comunas históricamente «Costo Fijo» cuyo
    padrón municipal dejó de describir a su población. Probado el defecto en un año, los
    siguientes del mismo régimen no son confiables aunque falte la prueba individual
    —precisamente porque en 2025 el derrumbe conjunto borra la evidencia—. Se marca desde el
    **primer año con prueba en adelante**, nunca hacia atrás: los años anteriores están
    verificados y descartarlos sería tirar dato bueno.
    """
    out = df.copy()
    comparable = out[col_numerador].notna() & out[col_denominador].notna()
    out["denominador_refutado"] = comparable & (
        out[col_numerador].astype("Float64") > out[col_denominador].astype("Float64")
    )

    probadas = out.loc[out["denominador_refutado"], ["comuna_cut", "anio"]]
    primer_anio = probadas.groupby("comuna_cut")["anio"].min()
    desde = out["comuna_cut"].map(primer_anio)
    out["comuna_refutada"] = desde.notna() & out["anio"].ge(desde)

    reporte = {
        "celdas_comparables": int(comparable.sum()),
        "celdas_refutadas": int(out["denominador_refutado"].sum()),
        "comunas_refutadas": int(len(primer_anio)),
        "celdas_por_propagacion": int(
            (out["comuna_refutada"] & ~out["denominador_refutado"]).sum()
        ),
        "primer_anio_por_comuna": {str(c): int(a) for c, a in sorted(primer_anio.items())},
    }
    return out, reporte


#: Bajo esta fracción de la población de la comuna, el padrón municipal deja de servir como
#: denominador comunal. **No marca un dato erróneo**: marca que la APS de esa comuna es en
#: los hechos no municipal, así que su padrón municipal no describe a la comuna. Quirihue
#: tiene once inscritos municipales sobre 12.244 habitantes y los once son correctos.
#: Señal SECUNDARIA: resultó demasiado laxa por sí sola (ver
#: `refutar_denominador_con_numerador`).
FRACCION_MINIMA_INSCRITOS = 0.01


def marcar_denominador_implausible(
    inscritos: pd.DataFrame,
    poblacion: pd.DataFrame,
    fraccion_minima: float = FRACCION_MINIMA_INSCRITOS,
) -> tuple[pd.DataFrame, dict]:
    """Marca las comunas donde el padrón municipal no describe a la comuna.

    Devuelve (inscritos + columna `denominador_implausible`, reporte). **No borra ni imputa
    nada.**

    Qué marca: que los inscritos en APS **municipal** son una fracción despreciable de los
    habitantes, señal de que la atención primaria de esa comuna la presta un establecimiento
    dependiente del Servicio de Salud y no el municipio. El REM cuenta la actividad de
    ambos; este padrón cuenta solo el municipal. Dividir uno por otro da una cobertura sin
    sentido —del orden de miles por ciento—, y esta marca existe para impedirlo.

    **El nombre de la columna quedó mal puesto y se conserva por compatibilidad.** El valor
    no es implausible: Quirihue tiene once inscritos municipales sobre 12.244 habitantes
    porque su único establecimiento municipal es una posta rural, y los once son correctos.
    Lo implausible sería usarlos de denominador comunal.

    `poblacion` debe traer `comuna_cut`, `anio` y `poblacion` ya agregada.
    """
    total = poblacion.groupby(["comuna_cut", "anio"], as_index=False)["poblacion"].sum()
    out = inscritos.merge(total, on=["comuna_cut", "anio"], how="left")

    comparables = out["poblacion_inscrita"].notna() & out["poblacion"].gt(0)
    fraccion = out["poblacion_inscrita"] / out["poblacion"]
    out["denominador_implausible"] = comparables & fraccion.lt(fraccion_minima)

    reporte = {
        "fraccion_minima": fraccion_minima,
        "celdas_comparables": int(comparables.sum()),
        "celdas_sin_poblacion_de_referencia": int((~comparables).sum()),
        "celdas_implausibles": int(out["denominador_implausible"].sum()),
        "comunas_implausibles": int(
            out.loc[out["denominador_implausible"], "comuna_cut"].nunique()
        ),
    }
    return out.drop(columns=["poblacion"]), reporte


def validar_cobertura_territorial(
    df: pd.DataFrame, col_cut: str, n_esperado: int, umbral_alerta: float = 0.95
) -> dict:
    """Reporta qué fracción de las comunas esperadas está presente.

    Una caída brusca de cobertura entre cortes casi siempre significa que la fuente
    cambió de formato, no que desaparecieron comunas.
    """
    presentes = df[col_cut].astype(str).nunique()
    cobertura = presentes / n_esperado if n_esperado else 0.0
    return {
        "comunas_presentes": presentes,
        "comunas_esperadas": n_esperado,
        "cobertura": cobertura,
        "alerta": cobertura < umbral_alerta,
    }
