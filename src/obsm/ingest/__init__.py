"""Ingestores. Uno por fuente; el registro permite invocarlos desde la CLI."""

from .base import Ingestor, renombrar_columnas
from .deis_defunciones import DeisDefunciones
from .deis_egresos import DeisEgresos
from .deis_establecimientos import DeisEstablecimientos
from .fonasa_inscritos import FonasaInscritos
from .glosa06 import Glosa06
from .ine_proyecciones import IneProyecciones
from .listaespera_minsal import ListaEsperaMinsal
from .rem_poblacion_control import RemPoblacionControl

#: source_id -> clase de ingestor. Una fuente sin entrada acá no es ingerible aún.
INGESTORES: dict[str, type[Ingestor]] = {
    DeisDefunciones.source_id: DeisDefunciones,
    DeisEgresos.source_id: DeisEgresos,
    DeisEstablecimientos.source_id: DeisEstablecimientos,
    FonasaInscritos.source_id: FonasaInscritos,
    Glosa06.source_id: Glosa06,
    IneProyecciones.source_id: IneProyecciones,
    ListaEsperaMinsal.source_id: ListaEsperaMinsal,
    RemPoblacionControl.source_id: RemPoblacionControl,
}

__all__ = [
    "INGESTORES",
    "DeisDefunciones",
    "DeisEgresos",
    "DeisEstablecimientos",
    "FonasaInscritos",
    "Glosa06",
    "IneProyecciones",
    "Ingestor",
    "ListaEsperaMinsal",
    "RemPoblacionControl",
    "renombrar_columnas",
]
