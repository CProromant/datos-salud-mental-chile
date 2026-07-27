"""Ingestores. Uno por fuente; el registro permite invocarlos desde la CLI."""

from .base import Ingestor, renombrar_columnas
from .deis_defunciones import DeisDefunciones

#: source_id -> clase de ingestor. Una fuente sin entrada acá no es ingerible aún.
INGESTORES: dict[str, type[Ingestor]] = {
    DeisDefunciones.source_id: DeisDefunciones,
}

__all__ = ["INGESTORES", "DeisDefunciones", "Ingestor", "renombrar_columnas"]
