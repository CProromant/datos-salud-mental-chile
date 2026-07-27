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
        raise ValueError(
            f"Llave {llave} duplicada en {int(dup.sum())} filas. Ejemplos: {ejemplos}"
        )


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
