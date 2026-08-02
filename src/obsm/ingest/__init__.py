"""Ingestores. Uno por fuente; el registro permite invocarlos desde la CLI."""

from .base import Ingestor, renombrar_columnas
from .deis_defunciones import DeisDefunciones
from .deis_establecimientos import DeisEstablecimientos
from .fonasa_inscritos import FonasaInscritos
from .ine_proyecciones import IneProyecciones
from .listaespera_minsal import ListaEsperaMinsal
from .rem_poblacion_control import RemPoblacionControl

#: source_id -> clase de ingestor. Una fuente sin entrada acá no es ingerible aún.
INGESTORES: dict[str, type[Ingestor]] = {
    DeisDefunciones.source_id: DeisDefunciones,
    DeisEstablecimientos.source_id: DeisEstablecimientos,
    FonasaInscritos.source_id: FonasaInscritos,
    IneProyecciones.source_id: IneProyecciones,
    ListaEsperaMinsal.source_id: ListaEsperaMinsal,
    RemPoblacionControl.source_id: RemPoblacionControl,
}

__all__ = [
    "INGESTORES",
    "DeisDefunciones",
    "DeisEstablecimientos",
    "FonasaInscritos",
    "IneProyecciones",
    "Ingestor",
    "ListaEsperaMinsal",
    "RemPoblacionControl",
    "renombrar_columnas",
]
