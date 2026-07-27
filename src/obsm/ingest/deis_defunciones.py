"""Ingestor de defunciones DEIS.

Estado: **verificado contra la fuente real** el 2026-07-27, sobre
`DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.zip`
(sha256 `311b5653…`, 3.182.446 filas, 27 columnas, separador `;`, encoding latin-1).

El diccionario que viene dentro del ZIP describe la **semántica** de los campos, pero sus
**nombres no corresponden** a los del CSV: declara `ANO_DEF`, `GLOSA_SEXO` y
`CODIGO_COMUNA_RESIDENCIA` donde el archivo trae `AÑO`, `SEXO_NOMBRE` y `COD_COMUNA`.
Sirve para entender qué significa cada columna, no para mapearlas.

Trampas de esta fuente, todas verificadas sobre el archivo completo:

1. **El suicidio NO está en `DIAG1`, está en `DIAG2`.** `DIAG1` es la causa básica y trae
   la naturaleza de la lesión (`T71X`, asfixia); `DIAG2` es la causa externa y trae el
   código `X` (`X704`, `X709`). Conteo sobre 1997–2023: X60–X84 aparece **0 veces** en
   `DIAG1` y **46.805** en `DIAG2`. Un agrupador de suicidio aplicado solo a `DIAG1`
   devuelve cero en veintisiete años sin lanzar ningún error. Por eso `causa_cie10` se
   **deriva**: es la causa externa cuando existe, y la básica cuando no. Así los
   agrupadores de causa externa (SUICIDIO, X60-X84) y los de enfermedad (TRASTORNOS_ANIMO,
   F30-F39) leen ambos la columna correcta.
2. **1990–1996 NO está en CIE-10, está en CIE-9.** El corte es limpio: hasta 1996 el
   100 % de `DIAG1` empieza en dígito, desde 1997 el 100 % empieza en letra. Los
   agrupadores de `cie10.py` sobre CIE-9 tampoco fallan: dan cero. `_posproceso` agrega
   `clasificacion_causa`; filtrar es decisión de `transform/`, no del ingestor.
   **No se sabe cómo se codifica el suicidio en esos años**: `E95x`, la clase habitual de
   CIE-9 para lesiones autoinfligidas, aparece 0 veces en las 536.746 filas del período.
   Queda como pendiente en `docs/05-CALIDAD.md`; hasta resolverlo, la serie de suicidio
   no puede empezar antes de 1997.
3. **`COD_COMUNA` viene sin el cero a la izquierda** en las regiones 01 a 09: 1.551.470
   filas traen 4 caracteres y 1.630.976 traen 5. Es la comuna de **residencia** (el
   diccionario la llama `CODIGO_COMUNA_RESIDENCIA`), que es la correcta para tasas. Hay
   que pasarla por `territorio.formatear_cut_comuna` antes de cualquier join.
4. **`EDAD_TIPO` puede venir vacío.** Son pocas filas (26), pero leerlas como años
   cumplidos convierte una edad de 3 en unidad desconocida en 3 años. Quedan nulas.
5. `SEXO_NOMBRE` incluye `Indeterminado` (183 filas). El diccionario lo declara como
   categoría (`9: Indeterminado`), no como dato faltante, y se conserva como tal.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from ..io import detectar_separador, leer_primera_linea
from .base import Ingestor, renombrar_columnas

#: Mapeo {nombre_en_la_fuente: nombre_canonico}. La coincidencia es laxa (sin tildes ni
#: mayúsculas). Los marcados «real» se leyeron del archivo publicado; el resto son
#: variantes toleradas de otras entregas de DEIS.
#:
#: Varias claves pueden apuntar al mismo destino a propósito (`AÑO` y `ANO_DEF`), porque
#: son entregas distintas de la misma fuente. `renombrar_columnas` no resuelve colisiones,
#: así que si un archivo trajera dos de ellas a la vez el resultado serían dos columnas
#: con el mismo nombre: `_leer` lo detecta y lanza SchemaDriftError en vez de continuar.
MAPA_COLUMNAS = {
    "AÑO": "anio",  # real
    "ANO_DEF": "anio",  # variante tolerada (así lo llama el diccionario)
    "AÑO_DEF": "anio",  # variante tolerada
    "FECHA_DEF": "fecha_defuncion",  # real
    "SEXO_NOMBRE": "sexo_nombre",  # real; `_leer` deriva `sexo` de aquí
    "GLOSA_SEXO": "sexo_nombre",  # variante tolerada (nombre del diccionario)
    "SEXO": "sexo",  # variante tolerada
    "EDAD_TIPO": "edad_tipo",  # real
    "EDAD_CANT": "edad_cantidad",  # real
    "COD_COMUNA": "comuna_cut_fuente",  # real (es comuna de RESIDENCIA)
    "CODIGO_COMUNA_RESIDENCIA": "comuna_cut_fuente",  # variante tolerada
    "COMUNA": "comuna_nombre",  # real
    "GLOSA_COMUNA_RESIDENCIA": "comuna_nombre",  # variante tolerada
    "NOMBRE_REGION": "region_nombre",  # real
    "GLOSA_REG_RES": "region_nombre",  # variante tolerada
    "DIAG1": "causa_basica",  # real: naturaleza de la lesión / enfermedad
    "DIAG2": "causa_externa",  # real: causa externa. Acá vive el suicidio.
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
    "9": "indeterminado",
    "M": "hombre",
    "F": "mujer",
}


def clasificar_codigo_causa(codigo: object) -> str:
    """Devuelve 'cie10', 'cie9' o 'desconocido' según la forma del código.

    CIE-10 usa letra seguida de dígitos (`X70`, `F32`); en este archivo los códigos
    anteriores a 1997 son solo dígitos (`9509`, `9109`). No se infiere por año a
    propósito: se lee el código, porque el año es un campo más y también puede venir mal.
    """
    s = str(codigo).strip()
    if not s or s.lower() == "nan":
        return "desconocido"
    if s[0].isalpha():
        return "cie10"
    if s[0].isdigit():
        return "cie9"
    return "desconocido"


def _limpiar_codigo(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip().str.upper().str.replace(".", "", regex=False)


class DeisDefunciones(Ingestor):
    source_id = "deis_defunciones"
    columnas_requeridas = ("anio", "sexo", "causa_basica")
    columnas_opcionales = (
        "causa_externa",
        "comuna_nombre",
        "comuna_cut_fuente",
        "edad_cantidad",
        "edad_tipo",
        "fecha_defuncion",
        "region_nombre",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        # Solo el encabezado: el archivo real pesa 869 MB y aquí únicamente se necesita
        # la primera línea para decidir el separador.
        primera, encoding = leer_primera_linea(ruta)
        sep = detectar_separador(primera)
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str, low_memory=False)
        df.attrs["encoding"] = encoding
        df.attrs["separador"] = sep
        df = renombrar_columnas(df, MAPA_COLUMNAS)

        # Dos columnas de origen mapeadas al mismo destino producirían dos columnas
        # homónimas, y a partir de ahí `df["anio"]` devuelve un DataFrame en vez de una
        # Serie: el error aparecería mucho más tarde y en otro lugar.
        duplicadas = sorted({c for c in df.columns if list(df.columns).count(c) > 1})
        if duplicadas:
            raise SchemaDriftError(
                f"[{self.source_id}] el archivo trae varias columnas que mapean al mismo "
                f"destino: {duplicadas}. Revisar MAPA_COLUMNAS contra este archivo antes "
                f"de continuar; no elegir una en silencio."
            )

        # El archivo publicado no trae `SEXO`, solo `SEXO_NOMBRE`. Se deriva acá y no con
        # dos entradas del mapa apuntando a `sexo`, para no provocar la colisión de arriba.
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
            # Unidad desconocida -> nulo, nunca 0 ni "años" (trampa 4 del docstring).
            out["edad_anios"] = cant.where(tipo == 1, 0).where(conocida, pd.NA)
            out["edad_unidad_original"] = tipo.map(UNIDADES_EDAD).fillna("desconocido")
        else:
            out["edad_anios"] = pd.NA
            out["edad_unidad_original"] = "ausente"

        out["causa_basica"] = _limpiar_codigo(out["causa_basica"])
        if "causa_externa" in out.columns:
            out["causa_externa"] = _limpiar_codigo(out["causa_externa"])
        else:
            out["causa_externa"] = ""

        # Columna de clasificación: la causa externa manda cuando existe, porque ahí vive
        # el código que definen los agrupadores de lesiones (X60-X84 para suicidio). Para
        # las muertes por enfermedad `causa_externa` viene vacía y manda la básica, que es
        # donde están los códigos F. Ver trampa 1 del docstring.
        externa = out["causa_externa"]
        out["causa_cie10"] = externa.where(externa != "", out["causa_basica"])
        out["origen_causa_cie10"] = (externa != "").map({True: "externa", False: "basica"})
        out["clasificacion_causa"] = out["causa_cie10"].map(clasificar_codigo_causa)

        out["sexo"] = (
            out["sexo"].astype(str).str.strip().str.upper().map(MAPA_SEXO).fillna("desconocido")
        )
        return out
