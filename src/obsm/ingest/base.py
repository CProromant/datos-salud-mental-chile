"""Contrato base de los ingestores.

Un ingestor hace exactamente tres cosas: obtener el archivo, verificar que cumple el
contrato declarado, y escribir bronze con su manifiesto. **No** normaliza territorio,
no calcula nada y no decide nada de negocio: eso vive en `transform/`.

La separación importa porque los ingestores son la parte que se rompe sola cuando la
fuente cambia, y conviene que se rompa sin arrastrar lógica analítica con ella.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from ..io import Manifiesto, ahora_iso, detectar_encoding, ruta_capa, sha256_archivo
from ..quality import detectar_filas_total
from ..registry import Fuente

log = logging.getLogger(__name__)


class Ingestor(ABC):
    """Base de todos los ingestores.

    Subclases deben declarar `source_id` y `columnas_requeridas`, e implementar
    `_leer`. El resto (validación, manifiesto, escritura) es común.
    """

    source_id: str = ""
    #: Nombres de columna que deben existir tras `_leer`. Su ausencia es SchemaDriftError.
    columnas_requeridas: tuple[str, ...] = ()
    #: Columnas conocidas pero opcionales; su ausencia se registra, no falla.
    columnas_opcionales: tuple[str, ...] = ()

    def __init__(self, fuente: Fuente | None = None):
        self.fuente = fuente

    # -- API pública ------------------------------------------------------------------

    #: Nombre de la columna booleana que marca filas de total. Se calcula sobre el
    #: texto crudo y viaja hasta silver.
    COL_FILA_TOTAL = "_es_fila_total"

    def preparar(self, ruta_local: Path) -> pd.DataFrame:
        """Lee, marca filas de total, valida el contrato y posprocesa.

        El orden importa: las filas de total se detectan **antes** de cualquier
        coerción numérica. Una fila "TOTAL PAIS;;;;" pierde su única pista textual
        en cuanto se convierte la columna de año a entero, y a partir de ahí es
        indistinguible de una fila con datos faltantes.
        """
        df = self._leer(Path(ruta_local))
        df[self.COL_FILA_TOTAL] = detectar_filas_total(df)
        self.validar_esquema(df)
        return self._posproceso(df)

    def ingerir(self, ruta_local: Path, forzar: bool = False) -> tuple[pd.DataFrame, Manifiesto]:
        """Lee un archivo ya descargado, valida el contrato y escribe bronze."""
        ruta_local = Path(ruta_local)
        df = self.preparar(ruta_local)

        manifiesto = Manifiesto(
            source_id=self.source_id,
            url=(self.fuente.url_principal if self.fuente else None),
            fecha_extraccion=ahora_iso(),
            sha256=sha256_archivo(ruta_local),
            bytes=ruta_local.stat().st_size,
            encoding=detectar_encoding(ruta_local),
            filas=len(df),
            notas=[f"archivo_origen={ruta_local.name}"],
        )
        destino = ruta_capa("bronze", self.source_id, f"{ruta_local.stem}.parquet")
        destino.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(destino, index=False)
        manifiesto.escribir(destino.with_suffix(".manifiesto.json"))
        log.info("bronze escrito: %s (%d filas)", destino, len(df))
        return df, manifiesto

    def validar_esquema(self, df: pd.DataFrame) -> None:
        faltantes = [c for c in self.columnas_requeridas if c not in df.columns]
        if faltantes:
            raise SchemaDriftError(
                f"[{self.source_id}] faltan columnas requeridas: {faltantes}. "
                f"Columnas presentes: {list(df.columns)[:25]}. "
                f"Esto es un cambio de esquema de la fuente: NO adaptar el parser en "
                f"silencio; revisar la fuente, actualizar el contrato y agregar un test."
            )
        opcionales_faltantes = [c for c in self.columnas_opcionales if c not in df.columns]
        if opcionales_faltantes:
            log.warning(
                "[%s] columnas opcionales ausentes: %s", self.source_id, opcionales_faltantes
            )

    # -- A implementar por la subclase -------------------------------------------------

    @abstractmethod
    def _leer(self, ruta: Path) -> pd.DataFrame:
        """Lee el archivo crudo y devuelve un DataFrame con nombres ya renombrados."""

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza mínima específica de la fuente. Por defecto, identidad."""
        return df


def renombrar_columnas(df: pd.DataFrame, mapa: dict[str, str]) -> pd.DataFrame:
    """Renombra por coincidencia laxa (sin tildes, sin espacios, minúsculas).

    Las fuentes cambian mayúsculas y acentos entre años sin cambiar el significado;
    eso no es un cambio de esquema y no debe hacer fallar la ingesta.
    """
    from ..territorio import normalizar_texto

    normalizado = {normalizar_texto(k).replace(" ", ""): v for k, v in mapa.items()}
    nuevas = {}
    for col in df.columns:
        clave = normalizar_texto(str(col)).replace(" ", "")
        if clave in normalizado:
            nuevas[col] = normalizado[clave]
    return df.rename(columns=nuevas)
