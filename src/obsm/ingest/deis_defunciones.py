"""Ingestor de defunciones DEIS.

Estado: **verificado contra la fuente real** el 2026-07-27, sobre
`DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.zip`
(sha256 `311b5653…`, 3.182.446 filas, 27 columnas, separador `;`, encoding latin-1).

El mapa de columnas anterior era una hipótesis y **erraba en tres puntos**: la columna
de año se llama `AÑO` y no `ANO_DEF`; no existe ninguna columna `SEXO`, solo
`SEXO_NOMBRE`; y la región es `NOMBRE_REGION`, no `REGION`. Con ese mapa la ingesta
fallaba con `SchemaDriftError` —el comportamiento correcto— pero no ingería nada.

Trampas de esta fuente, todas verificadas sobre el archivo completo:

1. **1990–1996 NO está en CIE-10, está en CIE-9.** El corte es limpio: hasta 1996 el
   100 % de `DIAG1` empieza en dígito, desde 1997 el 100 % empieza en letra. Aplicar los
   agrupadores de `cie10.py` a esos años no da error: da **cero**. Una serie de suicidio
   que arrancara en 1990 mostraría siete años planos en cero y nadie lo notaría. Por eso
   `_posproceso` agrega `clasificacion_causa`. Filtrar es decisión de `transform/`, no
   del ingestor.
2. **`COD_COMUNA` viene sin el cero a la izquierda** en las regiones 01 a 09: 1.551.470
   filas traen 4 caracteres y 1.630.976 traen 5. Hay que pasarlo por
   `territorio.formatear_cut_comuna` antes de cualquier join.
3. **`EDAD_TIPO` puede venir vacío.** Son pocas filas (26), pero la versión anterior las
   trataba como años cumplidos: una edad de 3 en unidad desconocida se volvía 3 años.
   Ahora quedan nulas y marcadas.
4. `SEXO_NOMBRE` incluye `Indeterminado` (183 filas). Es una categoría real de la fuente,
   no un dato faltante, y se conserva como tal.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..io import detectar_separador, leer_texto
from .base import Ingestor, renombrar_columnas

#: Mapeo {nombre_en_la_fuente: nombre_canonico}. La coincidencia es laxa (sin tildes ni
#: mayúsculas). Los marcados «real» se leyeron del archivo publicado; el resto son
#: variantes toleradas de otras entregas de DEIS. Dos claves nunca deben apuntar al
#: mismo destino: `renombrar_columnas` no resuelve colisiones.
MAPA_COLUMNAS = {
    "AÑO": "anio",  # real
    "ANO_DEF": "anio",  # variante tolerada
    "AÑO_DEF": "anio",  # variante tolerada
    "FECHA_DEF": "fecha_defuncion",  # real
    "SEXO_NOMBRE": "sexo_nombre",  # real; `_leer` deriva `sexo` de aquí
    "SEXO": "sexo",  # variante tolerada
    "EDAD_TIPO": "edad_tipo",  # real
    "EDAD_CANT": "edad_cantidad",  # real
    "COD_COMUNA": "comuna_cut_fuente",  # real
    "COMUNA": "comuna_nombre",  # real
    "NOMBRE_REGION": "region_nombre",  # real
    "DIAG1": "causa_cie10",  # real
    "DIAG2": "causa_secundaria",  # real
    "LUGAR_DEFUNCION": "lugar_defuncion",  # real
}

#: Primer año publicado en CIE-10. Verificado sobre el archivo completo: 1996 es 100 %
#: CIE-9 y 1997 es 100 % CIE-10, sin años mezclados.
ANIO_INICIO_CIE10 = 1997

#: `edad_tipo` codifica la unidad de la edad. Una edad de "3" en tipo "meses" leída como
#: 3 años convierte una muerte infantil en preescolar.
UNIDADES_EDAD = {1: "anios", 2: "meses", 3: "dias", 4: "horas"}

#: Valores reales de `SEXO_NOMBRE` más variantes toleradas de otras entregas.
MAPA_SEXO = {
    "HOMBRE": "hombre",
    "MUJER": "mujer",
    "INDETERMINADO": "indeterminado",
    "1": "hombre",
    "2": "mujer",
    "M": "hombre",
    "F": "mujer",
}


def clasificar_codigo_causa(codigo: object) -> str:
    """Devuelve 'cie10', 'cie9' o 'desconocido' según la forma del código.

    CIE-10 usa letra seguida de dígitos (`X60`, `F32`); CIE-9 usa solo dígitos
    (`E950` se publica como `9509`, `9109`). No se infiere por año a propósito: se lee
    el código, porque el año es un campo más y también puede venir mal.
    """
    s = str(codigo).strip()
    if not s or s.lower() == "nan":
        return "desconocido"
    if s[0].isalpha():
        return "cie10"
    if s[0].isdigit():
        return "cie9"
    return "desconocido"


class DeisDefunciones(Ingestor):
    source_id = "deis_defunciones"
    columnas_requeridas = ("anio", "sexo", "causa_cie10")
    columnas_opcionales = (
        "comuna_nombre",
        "comuna_cut_fuente",
        "edad_cantidad",
        "edad_tipo",
        "fecha_defuncion",
        "region_nombre",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        texto, encoding = leer_texto(ruta)
        primera = texto.split("\n", 1)[0]
        sep = detectar_separador(primera)
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str, low_memory=False)
        df.attrs["encoding"] = encoding
        df.attrs["separador"] = sep
        df = renombrar_columnas(df, MAPA_COLUMNAS)

        # El archivo publicado no trae `SEXO`, solo `SEXO_NOMBRE`. Se deriva acá y no
        # con dos entradas del mapa apuntando a `sexo`, porque `renombrar_columnas` no
        # resuelve colisiones: dejaría dos columnas con el mismo nombre.
        if "sexo" not in df.columns and "sexo_nombre" in df.columns:
            df["sexo"] = df["sexo_nombre"]
        return df

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["anio"] = pd.to_numeric(out["anio"], errors="coerce").astype("Int64")

        if "edad_cantidad" in out.columns:
            cant = pd.to_numeric(out["edad_cantidad"], errors="coerce")
            tipo = pd.to_numeric(out.get("edad_tipo"), errors="coerce")
            conocida = tipo.isin(list(UNIDADES_EDAD))
            # Unidad conocida y distinta de años -> 0 años cumplidos.
            # Unidad desconocida -> nulo, nunca 0 ni "años" (trampa 3 del docstring).
            out["edad_anios"] = cant.where(tipo == 1, 0).where(conocida, pd.NA)
            out["edad_unidad_original"] = tipo.map(UNIDADES_EDAD).fillna("desconocido")
        else:
            out["edad_anios"] = pd.NA
            out["edad_unidad_original"] = "ausente"

        out["causa_cie10"] = (
            out["causa_cie10"].astype(str).str.upper().str.replace(".", "", regex=False)
        )
        out["clasificacion_causa"] = out["causa_cie10"].map(clasificar_codigo_causa)

        out["sexo"] = (
            out["sexo"].astype(str).str.strip().str.upper().map(MAPA_SEXO).fillna("desconocido")
        )
        return out
