"""Ingestores. Uno por fuente; el registro permite invocarlos desde la CLI."""

from .base import Ingestor, renombrar_columnas
from .deis_defunciones import DeisDefunciones
from .ine_proyecciones import IneProyecciones
from .rem_poblacion_control import RemPoblacionControl

#: source_id -> clase de ingestor. Una fuente sin entrada acá no es ingerible aún.
INGESTORES: dict[str, type[Ingestor]] = {
    DeisDefunciones.source_id: DeisDefunciones,
    IneProyecciones.source_id: IneProyecciones,
    RemPoblacionControl.source_id: RemPoblacionControl,
}

__all__ = [
    "INGESTORES",
    "DeisDefunciones",
    "IneProyecciones",
    "Ingestor",
    "RemPoblacionControl",
    "renombrar_columnas",
]
