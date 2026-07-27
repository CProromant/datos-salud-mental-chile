"""Registro de fuentes: carga `config/sources.yml` y hace cumplir su semántica.

La regla que este módulo impone es la más importante del proyecto: **una fuente cuya
URL no fue verificada no se ingiere en un pipeline de producción**. El catálogo puede
contener hipótesis; el pipeline no puede tratarlas como hechos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ObsmError, SourceNotVerifiedError

RAIZ = Path(__file__).resolve().parents[2]
RUTA_SOURCES = RAIZ / "config" / "sources.yml"

ESTADOS_VALIDOS = {"no_verificada", "verificada", "rota"}
ORIGENES_VALIDOS = {"busqueda_web", "por_confirmar", "verificada_en_sesion"}


@dataclass
class Fuente:
    id: str
    nombre: str
    organismo: str | None = None
    estado: str = "no_verificada"
    origen_url: str | None = None
    url_indice: str | None = None
    url_espejo: str | None = None
    ejemplos_url_observados: list[str] = field(default_factory=list)
    fecha_verificacion: str | None = None
    formato: Any = None
    granularidad: str | None = None
    periodicidad: str | None = None
    prioridad: int | None = None
    fase: int | None = None
    variables_esperadas: list[str] = field(default_factory=list)
    ancla_reconciliacion: str | None = None
    tolerancia_reconciliacion: float = 0.005
    depende_de: list[str] = field(default_factory=list)
    nivel_maximo_publicable: str | None = None
    notas: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def verificada(self) -> bool:
        return self.estado == "verificada"

    @property
    def url_principal(self) -> str | None:
        if self.url_indice:
            return self.url_indice
        if self.ejemplos_url_observados:
            return self.ejemplos_url_observados[0]
        return self.url_espejo


class Registro:
    def __init__(self, fuentes: list[Fuente], defaults: dict | None = None):
        self.fuentes = {f.id: f for f in fuentes}
        self.defaults = defaults or {}

    def __len__(self) -> int:
        return len(self.fuentes)

    def __iter__(self):
        return iter(self.fuentes.values())

    def get(self, source_id: str) -> Fuente:
        if source_id not in self.fuentes:
            raise ObsmError(
                f"Fuente desconocida: {source_id!r}. Fuentes disponibles: "
                f"{sorted(self.fuentes)}"
            )
        return self.fuentes[source_id]

    def exigir_verificada(self, source_id: str, permitir_no_verificada: bool = False) -> Fuente:
        """Devuelve la fuente solo si está verificada (o si se autoriza explícitamente)."""
        f = self.get(source_id)
        if f.verificada or permitir_no_verificada:
            return f
        raise SourceNotVerifiedError(
            f"La fuente {source_id!r} está en estado {f.estado!r} (origen_url="
            f"{f.origen_url!r}). Correr `obsm sources verify` y actualizar "
            f"config/sources.yml antes de ingerir. Para desarrollo local usar "
            f"--permitir-no-verificada."
        )

    def por_fase(self, fase: int) -> list[Fuente]:
        return sorted(
            (f for f in self if f.fase == fase), key=lambda f: (f.prioridad or 99, f.id)
        )

    def resumen(self) -> dict:
        return {
            "total": len(self),
            "verificadas": sum(1 for f in self if f.estado == "verificada"),
            "no_verificadas": sum(1 for f in self if f.estado == "no_verificada"),
            "rotas": sum(1 for f in self if f.estado == "rota"),
        }


_CAMPOS = set(Fuente.__dataclass_fields__) - {"extra"}


def cargar_registro(ruta: Path | str | None = None) -> Registro:
    ruta = Path(ruta) if ruta else RUTA_SOURCES
    if not ruta.exists():
        raise ObsmError(f"No existe el catálogo de fuentes en {ruta}")
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    fuentes: list[Fuente] = []
    for item in datos.get("fuentes", []):
        conocidos = {k: v for k, v in item.items() if k in _CAMPOS}
        extra = {k: v for k, v in item.items() if k not in _CAMPOS}
        f = Fuente(**conocidos, extra=extra)
        _validar(f)
        fuentes.append(f)
    ids = [f.id for f in fuentes]
    if len(ids) != len(set(ids)):
        raise ObsmError("Hay ids de fuente duplicados en sources.yml")
    return Registro(fuentes, datos.get("defaults", {}))


def _validar(f: Fuente) -> None:
    if f.estado not in ESTADOS_VALIDOS:
        raise ObsmError(f"[{f.id}] estado inválido: {f.estado!r}")
    if f.origen_url and f.origen_url not in ORIGENES_VALIDOS:
        raise ObsmError(f"[{f.id}] origen_url inválido: {f.origen_url!r}")
    if f.estado == "verificada" and not f.fecha_verificacion:
        raise ObsmError(
            f"[{f.id}] declarada verificada sin fecha_verificacion. "
            f"Una verificación sin fecha caduca sin que nadie lo note."
        )
    if f.estado == "verificada" and f.origen_url == "por_confirmar":
        raise ObsmError(
            f"[{f.id}] contradicción: estado verificada con origen_url por_confirmar"
        )


def verificar_urls(registro: Registro, timeout: int = 30) -> list[dict]:
    """Comprueba con HEAD (y GET de respaldo) que las URLs del catálogo respondan.

    No promueve fuentes automáticamente a `verificada`: la promoción es una decisión
    humana que además exige mirar el contenido, no solo el código de estado.
    """
    import requests  # noqa: PLC0415

    resultados = []
    for f in registro:
        url = f.url_principal
        if not url:
            resultados.append({"id": f.id, "url": None, "resultado": "sin_url"})
            continue
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:
                r = requests.get(url, timeout=timeout, stream=True)
            resultados.append(
                {
                    "id": f.id,
                    "url": url,
                    "status": r.status_code,
                    "content_type": r.headers.get("Content-Type"),
                    "content_length": r.headers.get("Content-Length"),
                    "resultado": "ok" if r.status_code < 400 else "error",
                }
            )
        except Exception as exc:  # noqa: BLE001
            resultados.append({"id": f.id, "url": url, "resultado": "fallo", "error": str(exc)})
    return resultados
