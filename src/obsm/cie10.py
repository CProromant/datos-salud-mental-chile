"""Agrupadores CIE-10 para salud mental, y la política de publicación asociada.

Dos decisiones importantes viven en este módulo, no en la capa de presentación:

1. **Qué cuenta como qué.** Las definiciones son explícitas y citables, para que un
   tercero pueda reproducir exactamente la misma serie.
2. **Qué no se publica jamás.** El agrupador de suicidio existe; el desglose por
   método no se expone. `es_publicable()` es la única puerta y `quality.py` la
   invoca antes de escribir cualquier tabla en `gold`.

Nota de verificación: las descripciones de rango que siguen corresponden a la
estructura estándar de CIE-10. Antes de la primera publicación hay que contrastar
cada rango contra la lista tabular oficial vigente en Chile (tarea de Fase 1,
registrada en docs/05-CALIDAD.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_RE_CODIGO = re.compile(r"^([A-Z])(\d{2})(\d?)$")


def normalizar_codigo(codigo: str) -> str:
    """Normaliza un código CIE-10 a la forma `LNN` o `LNNN`, sin punto.

    >>> normalizar_codigo("x60.1")
    'X601'
    >>> normalizar_codigo(" F32 ")
    'F32'
    """
    if codigo is None:
        return ""
    c = str(codigo).strip().upper().replace(".", "").replace(" ", "")
    return c


def _partes(codigo: str) -> tuple[str, int, str] | None:
    m = _RE_CODIGO.match(normalizar_codigo(codigo)[:4])
    if not m:
        return None
    return m.group(1), int(m.group(2)), m.group(3)


def en_rango(codigo: str, inicio: str, fin: str) -> bool:
    """¿El código está en el rango [inicio, fin] inclusive, a nivel de 3 caracteres?

    >>> en_rango("F32.1", "F30", "F39")
    True
    >>> en_rango("F40", "F30", "F39")
    False
    """
    p = _partes(codigo)
    pi, pf = _partes(inicio), _partes(fin)
    if not (p and pi and pf):
        return False
    letra, num, _ = p
    if letra != pi[0] or letra != pf[0]:
        return False
    return pi[1] <= num <= pf[1]


@dataclass(frozen=True)
class Agrupador:
    """Definición reproducible de un grupo de códigos."""

    id: str
    nombre: str
    rangos: tuple[tuple[str, str], ...] = ()
    codigos: tuple[str, ...] = ()
    publicable: bool = True
    nota: str = ""
    incluye_en_denominador: bool = True
    excluye: tuple[str, ...] = field(default=())

    def contiene(self, codigo: str) -> bool:
        c = normalizar_codigo(codigo)
        if not c:
            return False
        if any(c.startswith(normalizar_codigo(x)) for x in self.excluye):
            return False
        if any(c.startswith(normalizar_codigo(x)) for x in self.codigos):
            return True
        return any(en_rango(c, a, b) for a, b in self.rangos)


# --------------------------------------------------------------------------------------
# Agrupadores
# --------------------------------------------------------------------------------------

TRASTORNOS_MENTALES = Agrupador(
    id="TRASTORNOS_MENTALES",
    nombre="Trastornos mentales y del comportamiento (capítulo V)",
    rangos=(("F00", "F99"),),
    nota="Capítulo completo. Como causa básica de muerte captura poco; sirve en morbilidad.",
)

SUICIDIO = Agrupador(
    id="SUICIDIO",
    nombre="Muerte por suicidio (lesiones autoinfligidas intencionalmente)",
    rangos=(("X60", "X84"),),
    codigos=("Y870",),
    nota=(
        "Definición estándar: X60-X84 más secuelas (Y87.0). "
        "Y10-Y34 (intención indeterminada) NO se incluye en la serie principal; "
        "se calcula aparte como análisis de sensibilidad."
    ),
)

INTENCION_INDETERMINADA = Agrupador(
    id="INTENCION_INDETERMINADA",
    nombre="Eventos de intención no determinada",
    rangos=(("Y10", "Y34"),),
    codigos=("Y872",),
    nota="Solo para sensibilidad del indicador de suicidio. Nunca sumar sin declararlo.",
)

LESION_AUTOINFLIGIDA_MORBILIDAD = Agrupador(
    id="LESION_AUTOINFLIGIDA_MORBILIDAD",
    nombre="Lesión autoinfligida intencionalmente (morbilidad: egresos y urgencias)",
    rangos=(("X60", "X84"),),
    nota=(
        "En morbilidad estos códigos aparecen como causa externa acompañando a un "
        "diagnóstico principal (frecuentemente intoxicación, T36-T50). La disponibilidad "
        "de la causa externa varía por fuente: verificar antes de publicar."
    ),
)

CONSUMO_SUSTANCIAS = Agrupador(
    id="CONSUMO_SUSTANCIAS",
    nombre="Trastornos por consumo de sustancias psicoactivas",
    rangos=(("F10", "F19"),),
)

ESQUIZOFRENIA_Y_PSICOSIS = Agrupador(
    id="ESQUIZOFRENIA_Y_PSICOSIS",
    nombre="Esquizofrenia, trastorno esquizotípico y trastornos delirantes",
    rangos=(("F20", "F29"),),
)

TRASTORNOS_ANIMO = Agrupador(
    id="TRASTORNOS_ANIMO",
    nombre="Trastornos del humor (afectivos)",
    rangos=(("F30", "F39"),),
)

TRASTORNOS_ANSIEDAD = Agrupador(
    id="TRASTORNOS_ANSIEDAD",
    nombre="Trastornos neuróticos, relacionados con el estrés y somatomorfos",
    rangos=(("F40", "F48"),),
    nota="Incluye el grueso de lo que queda FUERA de las garantías GES.",
)

TRASTORNOS_ALIMENTARIOS = Agrupador(
    id="TRASTORNOS_ALIMENTARIOS",
    nombre="Trastornos de la conducta alimentaria",
    codigos=("F50",),
)

TRASTORNOS_PERSONALIDAD = Agrupador(
    id="TRASTORNOS_PERSONALIDAD",
    nombre="Trastornos de la personalidad y del comportamiento adulto",
    rangos=(("F60", "F69"),),
)

DESARROLLO_Y_INFANCIA = Agrupador(
    id="DESARROLLO_Y_INFANCIA",
    nombre="Trastornos del desarrollo y de inicio en la infancia y adolescencia",
    rangos=(("F80", "F98"),),
    nota="Incluye F84 (espectro autista) y F90 (hipercinéticos).",
)

DEMENCIAS = Agrupador(
    id="DEMENCIAS",
    nombre="Demencias",
    rangos=(("F00", "F03"),),
    codigos=("G30",),
    nota=(
        "Decisión explícita: se incluye G30 (Alzheimer), que se codifica en el capítulo "
        "neurológico. Al cruzar con TRASTORNOS_MENTALES hay solapamiento: no sumar "
        "agrupadores entre sí sin deduplicar por registro."
    ),
)

AGRUPADORES: dict[str, Agrupador] = {
    a.id: a
    for a in (
        TRASTORNOS_MENTALES,
        SUICIDIO,
        INTENCION_INDETERMINADA,
        LESION_AUTOINFLIGIDA_MORBILIDAD,
        CONSUMO_SUSTANCIAS,
        ESQUIZOFRENIA_Y_PSICOSIS,
        TRASTORNOS_ANIMO,
        TRASTORNOS_ANSIEDAD,
        TRASTORNOS_ALIMENTARIOS,
        TRASTORNOS_PERSONALIDAD,
        DESARROLLO_Y_INFANCIA,
        DEMENCIAS,
    )
}


def clasificar(codigo: str) -> list[str]:
    """Devuelve los ids de agrupadores que contienen el código (pueden ser varios)."""
    return [a.id for a in AGRUPADORES.values() if a.contiene(codigo)]


# --------------------------------------------------------------------------------------
# Política de publicación
# --------------------------------------------------------------------------------------

#: Dimensiones cuya desagregación pública está prohibida por política editorial.
#: Ver docs/06-ETICA-Y-DATOS.md. No se relaja por conveniencia analítica.
DIMENSIONES_PROHIBIDAS_PUBLICACION = {
    "metodo_suicidio",
    "codigo_cie10_detalle_x",  # subcódigos individuales de X60-X84
    "mecanismo_lesion",
}


#: Niveles de detalle que `es_publicable` sabe evaluar. Cualquier otro valor es un error
#: del llamador, no un caso permitido: ver por qué en `es_publicable`.
NIVELES_DETALLE = frozenset({"agrupador", "codigo"})


def es_publicable(agrupador_id: str, nivel_detalle: str = "agrupador") -> bool:
    """¿Se puede publicar esta salida?

    `nivel_detalle`:
      - "agrupador": el conteo del grupo completo. Permitido.
      - "codigo": desglose código a código. Prohibido para SUICIDIO y
        LESION_AUTOINFLIGIDA_MORBILIDAD, porque equivale a publicar métodos.

    Un `nivel_detalle` desconocido **lanza** en vez de devolver un booleano. Esta función
    hace cumplir una regla no negociable de `docs/06`, y antes fallaba abierto: un typo
    como `"subcodigo"` no coincidía con la condición, se saltaba la prohibición y devolvía
    True. Un guarda que un error de tipeo convierte en permiso no es un guarda. Ante un
    nivel que no se sabe evaluar, la respuesta correcta no es «sí» ni «no», es detenerse.
    """
    if nivel_detalle not in NIVELES_DETALLE:
        raise ValueError(
            f"nivel_detalle desconocido: {nivel_detalle!r}. Válidos: "
            f"{sorted(NIVELES_DETALLE)}. No se asume un nivel por defecto porque esta "
            f"función decide si algo se publica o no."
        )
    if nivel_detalle == "codigo" and agrupador_id in {
        "SUICIDIO",
        "LESION_AUTOINFLIGIDA_MORBILIDAD",
        "INTENCION_INDETERMINADA",
    }:
        return False
    ag = AGRUPADORES.get(agrupador_id)
    return bool(ag and ag.publicable)
