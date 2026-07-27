"""Reconciliación contra cifras oficiales: el portero de la publicación.

`quality.verificar_reconciliacion` sabía comparar dos números desde el principio, pero
**nadie la llamaba**: la regla de CLAUDE.md §7 —«si no cuadra, no se publica»— dependía de
que una persona se acordara de correr la comprobación a mano. Un pipeline que valida solo
cuando alguien se acuerda no valida.

Este módulo cierra eso: carga las anclas declaradas en `config/anclas.yml`, las evalúa
contra las tablas de silver y devuelve un reporte. `transform.gold` lo invoca antes de
escribir, así que una serie que dejó de cuadrar hace fallar la publicación en vez de
producir un CSV con aspecto correcto.

Lo que este módulo NO hace: inventar anclas. Un ancla sin `referencia` y sin
`fecha_verificacion` no se carga, porque un número sin procedencia no valida nada —
solo traslada la fe de un lugar a otro.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .errors import ObsmError, ReconciliationError
from .quality import verificar_reconciliacion

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parents[2]
RUTA_ANCLAS = RAIZ / "config" / "anclas.yml"

TIPOS_METRICA = {"conteo_filas", "suma_columna"}


@dataclass
class Ancla:
    """Una cifra oficial publicada contra la que se contrasta un total calculado."""

    id: str
    descripcion: str
    source_id: str
    metrica: dict
    valor: float
    referencia: str
    fecha_verificacion: str
    filtro: dict = field(default_factory=dict)
    #: Filtro por prefijo de código, para capítulos CIE-10 (`V`,`W`,`X`,`Y` = causas
    #: externas). No se puede hacer por igualdad porque un capítulo son miles de códigos.
    filtro_prefijo: dict = field(default_factory=dict)
    unidad: str | None = None
    tolerancia_relativa: float = 0.005
    fuente_ancla: str | None = None
    nota: str | None = None

    def evaluar(self, df: pd.DataFrame) -> float:
        """Calcula el valor observado en `df` aplicando filtros y métrica."""
        sub = df
        for col, esperado in self.filtro.items():
            if col not in sub.columns:
                raise ReconciliationError(
                    f"[{self.id}] la tabla no tiene la columna de filtro {col!r}. "
                    f"Columnas: {list(sub.columns)[:15]}"
                )
            sub = sub[sub[col] == esperado]

        for col, prefijos in self.filtro_prefijo.items():
            if col not in sub.columns:
                raise ReconciliationError(
                    f"[{self.id}] la tabla no tiene la columna de filtro por prefijo "
                    f"{col!r}. Columnas: {list(sub.columns)[:15]}"
                )
            codigos = sub[col].fillna("").astype(str).str.upper()
            sub = sub[codigos.str.startswith(tuple(str(p).upper() for p in prefijos))]

        tipo = self.metrica.get("tipo")
        if tipo == "conteo_filas":
            return float(len(sub))
        if tipo == "suma_columna":
            col = self.metrica.get("columna")
            if col not in sub.columns:
                raise ReconciliationError(
                    f"[{self.id}] la tabla no tiene la columna {col!r} que pide la métrica."
                )
            return float(sub[col].sum())
        raise ReconciliationError(
            f"[{self.id}] tipo de métrica desconocido: {tipo!r}. Válidos: {sorted(TIPOS_METRICA)}"
        )


def cargar_anclas(ruta: Path | str | None = None) -> list[Ancla]:
    """Lee `config/anclas.yml` y valida que cada ancla tenga procedencia."""
    ruta = Path(ruta) if ruta else RUTA_ANCLAS
    if not ruta.exists():
        raise ObsmError(f"No existe el archivo de anclas en {ruta}")
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    anclas: list[Ancla] = []
    campos = set(Ancla.__dataclass_fields__)
    for item in datos.get("anclas", []):
        desconocidos = set(item) - campos
        if desconocidos:
            raise ObsmError(
                f"[{item.get('id', '?')}] campos desconocidos en anclas.yml: "
                f"{sorted(desconocidos)}"
            )
        a = Ancla(**item)
        _validar(a)
        anclas.append(a)

    ids = [a.id for a in anclas]
    if len(ids) != len(set(ids)):
        raise ObsmError("Hay ids de ancla duplicados en anclas.yml")
    return anclas


def _validar(a: Ancla) -> None:
    if not a.referencia or not a.fecha_verificacion:
        raise ObsmError(
            f"[{a.id}] ancla sin procedencia: falta `referencia` o `fecha_verificacion`. "
            f"Un número sin origen comprobable no valida nada."
        )
    if a.metrica.get("tipo") not in TIPOS_METRICA:
        raise ObsmError(
            f"[{a.id}] métrica inválida: {a.metrica!r}. Tipos válidos: {sorted(TIPOS_METRICA)}"
        )
    if a.metrica.get("tipo") == "suma_columna" and not a.metrica.get("columna"):
        raise ObsmError(f"[{a.id}] métrica `suma_columna` sin `columna`")
    for col, prefijos in a.filtro_prefijo.items():
        if not isinstance(prefijos, list) or not prefijos:
            raise ObsmError(
                f"[{a.id}] filtro_prefijo[{col!r}] debe ser una lista no vacía; "
                f"llegó {prefijos!r}. Un prefijo vacío haría pasar todas las filas."
            )
        if any(not str(pre).strip() for pre in prefijos):
            raise ObsmError(
                f"[{a.id}] filtro_prefijo[{col!r}] tiene un prefijo vacío: {prefijos!r}. "
                f"`startswith('')` es verdadero para todo y anularía el filtro."
            )
    if a.valor <= 0:
        raise ObsmError(f"[{a.id}] valor de ancla no positivo: {a.valor}")
    if not 0 < a.tolerancia_relativa < 1:
        raise ObsmError(
            f"[{a.id}] tolerancia fuera de rango: {a.tolerancia_relativa}. "
            f"Una tolerancia de 0 nunca pasa y una de 1 acepta cualquier cosa."
        )


def reconciliar(
    tablas: dict[str, pd.DataFrame],
    anclas: list[Ancla] | None = None,
    estricto: bool = True,
) -> list[dict[str, Any]]:
    """Evalúa las anclas cuya fuente esté presente en `tablas`.

    `tablas` mapea `source_id` a la tabla silver correspondiente. Las anclas de fuentes
    ausentes se omiten y se reportan como tales: no se puede reconciliar lo que no se
    cargó, y silenciarlo sería peor que declararlo.

    Con `estricto=True` (el modo de publicación) la primera ancla fuera de tolerancia
    lanza `ReconciliationError`. Con `estricto=False` se evalúan todas y se devuelve el
    reporte completo, que es lo que sirve para diagnosticar.
    """
    anclas = anclas if anclas is not None else cargar_anclas()
    resultados: list[dict[str, Any]] = []

    for a in anclas:
        if a.source_id not in tablas:
            resultados.append({
                "ancla": a.id,
                "estado": "omitida",
                "motivo": f"no se cargó la tabla de {a.source_id!r}",
            })
            continue

        observado = a.evaluar(tablas[a.source_id])
        fila: dict[str, Any] = {
            "ancla": a.id,
            "descripcion": a.descripcion,
            "source_id": a.source_id,
            "observado": observado,
            "oficial": a.valor,
            "tolerancia": a.tolerancia_relativa,
            "referencia": a.referencia,
        }
        try:
            dif = verificar_reconciliacion(
                observado, a.valor, a.tolerancia_relativa, etiqueta=a.id
            )
            fila.update({"estado": "ok", "diferencia_relativa": dif})
            log.info("reconciliación ok: %s (dif %.4f%%)", a.id, dif * 100)
        except ReconciliationError as exc:
            fila.update({
                "estado": "FALLA",
                "diferencia_relativa": abs(observado - a.valor) / abs(a.valor),
                "detalle": str(exc),
            })
            resultados.append(fila)
            if estricto:
                raise
            log.error("reconciliación FALLA: %s", exc)
            continue
        resultados.append(fila)

    return resultados


def resumen(resultados: list[dict[str, Any]]) -> dict[str, int]:
    """Cuenta por estado. Útil para decidir si la corrida se publica."""
    conteo = {"ok": 0, "FALLA": 0, "omitida": 0}
    for r in resultados:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
    return conteo
