"""Ingestor de defunciones DEIS.

Estado: **funcional contra fixture, no verificado contra la fuente real.** El mapa de
columnas de abajo es una hipótesis razonable sobre el archivo publicado; la Fase 1
exige abrir el archivo real, corregir el mapa y agregar un fixture derivado de su
estructura (nunca de sus datos: el archivo tiene registros individuales).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..io import detectar_separador, leer_texto
from .base import Ingestor, renombrar_columnas

#: Hipótesis de mapeo {nombre_en_la_fuente: nombre_canonico}. La coincidencia es laxa
#: (sin tildes ni mayúsculas), por lo que basta una variante por concepto.
MAPA_COLUMNAS = {
    "ANO_DEF": "anio",
    "AÑO_DEF": "anio",
    "FECHA_DEF": "fecha_defuncion",
    "SEXO": "sexo",
    "SEXO_NOMBRE": "sexo_nombre",
    "EDAD_CANT": "edad_cantidad",
    "EDAD_TIPO": "edad_tipo",
    "COMUNA": "comuna_nombre",
    "NOMBRE_COMUNA": "comuna_nombre",
    "COD_COMUNA": "comuna_cut_fuente",
    "COMUNA_RESIDENCIA": "comuna_nombre",
    "REGION": "region_nombre",
    "COD_REGION": "region_cut_fuente",
    "DIAG1": "causa_cie10",
    "CAUSA_BASICA": "causa_cie10",
    "CODIGO_CIE10": "causa_cie10",
}

#: `edad_tipo` codifica la unidad de la edad (años, meses, días, horas). Una edad de
#: "3" en tipo "meses" leída como 3 años convierte una muerte infantil en preescolar.
UNIDADES_EDAD = {1: "anios", 2: "meses", 3: "dias", 4: "horas"}


class DeisDefunciones(Ingestor):
    source_id = "deis_defunciones"
    columnas_requeridas = ("anio", "sexo", "causa_cie10")
    columnas_opcionales = (
        "comuna_nombre",
        "comuna_cut_fuente",
        "edad_cantidad",
        "edad_tipo",
        "fecha_defuncion",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        texto, encoding = leer_texto(ruta)
        primera = texto.split("\n", 1)[0]
        sep = detectar_separador(primera)
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str, low_memory=False)
        df.attrs["encoding"] = encoding
        df.attrs["separador"] = sep
        return renombrar_columnas(df, MAPA_COLUMNAS)

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["anio"] = pd.to_numeric(out["anio"], errors="coerce").astype("Int64")

        if "edad_cantidad" in out.columns:
            cant = pd.to_numeric(out["edad_cantidad"], errors="coerce")
            tipo = pd.to_numeric(out.get("edad_tipo", 1), errors="coerce").fillna(1)
            # Toda unidad distinta de años se convierte a 0 años cumplidos.
            out["edad_anios"] = cant.where(tipo == 1, 0)
            out["edad_unidad_original"] = tipo.map(UNIDADES_EDAD).fillna("desconocido")
        else:
            out["edad_anios"] = pd.NA
            out["edad_unidad_original"] = "ausente"

        out["causa_cie10"] = (
            out["causa_cie10"].astype(str).str.upper().str.replace(".", "", regex=False)
        )
        out["sexo"] = out["sexo"].astype(str).str.strip().str.upper().map(
            {"1": "hombre", "2": "mujer", "M": "hombre", "F": "mujer",
             "HOMBRE": "hombre", "MUJER": "mujer"}
        ).fillna("desconocido")
        return out
