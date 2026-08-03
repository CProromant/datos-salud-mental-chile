"""Ingestor de las estimaciones y proyecciones de población del INE.

Estado: **verificado contra la fuente real** el 2026-07-27, sobre
`ine_estimaciones-y-proyecciones-2002-2035_base-2017_comunas…csv`
(sha256 `c2a88471…`, 9.768.366 bytes, 56.052 filas, 42 columnas, separador `,`,
encoding latin-1).

Es el denominador de toda tasa del proyecto, así que sus defectos no producen un número
raro en una columna: desplazan todas las tasas a la vez.

Trampas de esta fuente, todas verificadas sobre el archivo completo:

1. **Viene en formato ancho.** Una columna `Poblacion <año>` por cada año de 2002 a 2035,
   34 en total. Las 56.052 filas son 346 comunas × 2 sexos × 81 edades. Acá se pasa a
   formato largo, que es la grilla con la que se puede unir a cualquier otra tabla. No es
   lógica de negocio: es leer bien un archivo que está pivoteado.
2. **`Comuna` viene sin el cero a la izquierda** en las regiones 01 a 09 (`1101`, no
   `"01101"`), igual que `COD_COMUNA` en DEIS. Se lee como **string** y se deja tal cual
   en `comuna_cut_fuente`: rellenarlo es resolver territorio, que es trabajo de `silver`
   (ver la tabla de capas en `docs/02-ARQUITECTURA.md`). Lo único que este módulo garantiza
   es no haberlo convertido nunca a entero por el camino, que es como se pierde el cero.
3. **`Edad` 80 es un grupo abierto**, no la edad exacta 80. El archivo llega hasta 80 y
   ahí acumula «80 y más». Tratarlo como edad simple subestima la población mayor y
   **infla** cualquier tasa de ese tramo. Se marca con `edad_es_grupo_abierto`.
4. **La cobertura empieza en 2002.** Las defunciones van de 1990 a 2023, así que hay años
   con numerador y sin denominador. El ingestor no rellena ni extrapola: si un año no está,
   no está (A-008 en `docs/05-CALIDAD.md`).
5. El encabezado del sexo trae la glosa dentro del nombre —`Sexo (1=Hombre 2=Mujer)`— así
   que no se puede mapear por igualdad exacta. Se ubica por prefijo.

La base de las proyecciones es parte de su identidad: un cambio de base recalcula todas las
tasas retroactivamente. Por eso viaja en `source_version` y no se mezclan dos bases en una
misma serie.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from ..io import detectar_separador, leer_primera_linea
from .base import Ingestor, renombrar_columnas

#: Mapeo {nombre_en_la_fuente: nombre_canonico} para las columnas de identificación.
#: Las de población se detectan por patrón, no acá: son 34 y cambian con cada entrega.
MAPA_COLUMNAS = {
    "Region": "region_cut_fuente",
    "Nombre Region": "region_nombre",
    "Provincia": "provincia_cut_fuente",
    "Nombre Provincia": "provincia_nombre",
    "Comuna": "comuna_cut_fuente",
    "Nombre Comuna": "comuna_nombre",
    "Edad": "edad_anios",
}

#: Las columnas de población. `Poblacion 2002`, `Población 2002` y `POBLACION 2002` son la
#: misma cosa: el acento y la caja cambian entre entregas del INE sin cambiar el contenido.
PATRON_ANIO = re.compile(r"^poblaci[oó]n\s*(\d{4})$", re.IGNORECASE)

#: Prefijo del encabezado de sexo. El nombre real trae la glosa dentro:
#: `Sexo (1=Hombre 2=Mujer)`.
PREFIJO_SEXO = "sexo"

#: Códigos de sexo del INE. El archivo solo trae 1 y 2: no hay categoría de indeterminado,
#: a diferencia de DEIS. Un valor fuera de esto es cambio de esquema, no un dato más.
MAPA_SEXO = {"1": "hombre", "2": "mujer"}

#: Última edad publicada. No es la edad 80: es el grupo abierto «80 y más».
EDAD_GRUPO_ABIERTO = 80


class IneProyecciones(Ingestor):
    source_id = "ine_proyecciones"
    columnas_requeridas = ("anio", "comuna_cut_fuente", "sexo", "edad_anios", "poblacion")
    columnas_opcionales = (
        "comuna_nombre",
        "region_cut_fuente",
        "region_nombre",
        "provincia_cut_fuente",
        "provincia_nombre",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        primera, encoding = leer_primera_linea(ruta)
        sep = detectar_separador(primera)
        # dtype=str en todo: `Comuna` pierde el cero a la izquierda en cuanto pandas la
        # infiere como entero, y ese daño no se puede deshacer más adelante.
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str)
        df.attrs["encoding"] = encoding

        columnas_anio = self._columnas_de_anio(df)
        df = renombrar_columnas(df, MAPA_COLUMNAS)
        df = self._renombrar_sexo(df)

        identificadoras = [c for c in df.columns if c not in columnas_anio]
        largo = df.melt(
            id_vars=identificadoras,
            value_vars=list(columnas_anio),
            var_name="_col_anio",
            value_name="poblacion",
        )
        largo["anio"] = largo["_col_anio"].map(columnas_anio)
        return largo.drop(columns=["_col_anio"])

    # -- ayudas de lectura -------------------------------------------------------------

    def _columnas_de_anio(self, df: pd.DataFrame) -> dict[str, str]:
        """Devuelve {nombre_de_columna: año}. Falla si no hay ninguna.

        Que desaparezcan las columnas de población es el cambio de esquema más probable de
        esta fuente —el INE renombra al publicar una base nueva— y el más silencioso: sin
        esta comprobación el melt devolvería una tabla vacía y el denominador sería cero.
        """
        encontradas = {}
        for col in df.columns:
            m = PATRON_ANIO.match(str(col).strip())
            if m:
                encontradas[col] = m.group(1)
        if not encontradas:
            raise SchemaDriftError(
                f"[{self.source_id}] no se encontró ninguna columna de población con el "
                f"patrón 'Poblacion <año>'. Columnas presentes: {list(df.columns)[:15]}. "
                f"El INE probablemente publicó una base nueva con otro encabezado: revisar "
                f"la fuente y actualizar el contrato, no relajar el patrón."
            )
        return encontradas

    def _renombrar_sexo(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ubica la columna de sexo por prefijo y deriva `sexo` desde el código.

        La derivación va acá y no en `_posproceso` porque `preparar` valida el contrato
        de esquema **antes** de posprocesar: una columna requerida que nace después de la
        validación hace fallar la ingesta con un mensaje que culpa a la fuente.
        """
        candidatas = [c for c in df.columns if str(c).strip().lower().startswith(PREFIJO_SEXO)]
        if len(candidatas) != 1:
            raise SchemaDriftError(
                f"[{self.source_id}] se esperaba exactamente una columna de sexo que "
                f"empiece con {PREFIJO_SEXO!r}; se encontraron {len(candidatas)}: "
                f"{candidatas}. Columnas presentes: {list(df.columns)[:15]}."
            )
        out = df.rename(columns={candidatas[0]: "sexo_codigo"})

        codigos = out["sexo_codigo"].fillna("").astype(str).str.strip()
        out["sexo"] = codigos.map(MAPA_SEXO)
        desconocidos = sorted(set(codigos[out["sexo"].isna()]) - {""})
        if desconocidos:
            raise SchemaDriftError(
                f"[{self.source_id}] códigos de sexo no reconocidos: {desconocidos}. "
                f"Esta fuente solo publica 1=Hombre y 2=Mujer; un valor nuevo es un cambio "
                f"de esquema y hay que decidir qué significa antes de contarlo."
            )
        return out

    # -- posproceso --------------------------------------------------------------------

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        out["anio"] = pd.to_numeric(out["anio"], errors="coerce").astype("Int64")
        out["poblacion"] = pd.to_numeric(out["poblacion"], errors="coerce").astype("Int64")
        out["edad_anios"] = pd.to_numeric(out["edad_anios"], errors="coerce").astype("Int64")

        # El código de comuna se deja como string sin tocar: `formatear_cut_comuna` en
        # silver es el único lugar donde se resuelve territorio.
        for col in ("comuna_cut_fuente", "region_cut_fuente", "provincia_cut_fuente"):
            if col in out.columns:
                out[col] = out[col].fillna("").astype(str).str.strip()

        # El 80 del archivo es «80 y más». Marcarlo es la diferencia entre una tasa
        # correcta y una inflada en el tramo mayor.
        out["edad_es_grupo_abierto"] = out["edad_anios"] == EDAD_GRUPO_ABIERTO

        return out
