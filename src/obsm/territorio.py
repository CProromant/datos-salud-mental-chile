"""Normalización territorial: comunas y regiones a códigos CUT canónicos.

Este es el módulo del que dependen todos los joins del proyecto. Un error acá
no produce un error visible: produce un dato silenciosamente mal agregado.

Diseño en dos capas, deliberadamente separadas:

1. **Normalización de nombres** (`normalizar_texto`, `ALIAS`): resuelve las múltiples
   grafías oficiales y de facto de un mismo nombre. Es puro, completo y testeado.
2. **Resolución a código CUT** (`cargar_dpa`, `normalizar_comuna`): requiere la tabla
   oficial de División Político-Administrativa del INE. El repositorio trae una
   **semilla incompleta** en `config/territorio_comunas.csv`; el pipeline se niega a
   construir `gold` si la tabla no está completa (ver `validar_dpa`).

Por qué la tabla no viene completa: escribir 346 códigos de memoria es exactamente
el tipo de fabricación que CLAUDE.md §2.1 prohíbe. La tabla se carga desde la fuente
oficial en la Fase 1.
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .errors import TerritorioError

# --------------------------------------------------------------------------------------
# Regiones. Los códigos de región de 2 dígitos son estables y de uso normativo.
# Ñuble (16) fue creada en 2018 a partir de comunas de Biobío (08).
# --------------------------------------------------------------------------------------

REGIONES: dict[str, str] = {
    "15": "Arica y Parinacota",
    "01": "Tarapacá",
    "02": "Antofagasta",
    "03": "Atacama",
    "04": "Coquimbo",
    "05": "Valparaíso",
    "13": "Metropolitana de Santiago",
    "06": "Libertador General Bernardo O'Higgins",
    "07": "Maule",
    "16": "Ñuble",
    "08": "Biobío",
    "09": "La Araucanía",
    "14": "Los Ríos",
    "10": "Los Lagos",
    "11": "Aysén del General Carlos Ibáñez del Campo",
    "12": "Magallanes y de la Antártica Chilena",
}

#: Código reservado para comuna desconocida, ignorada o residencia en el extranjero.
#: Nunca se reparte proporcionalmente entre comunas conocidas: eso inventa datos.
COMUNA_DESCONOCIDA = "99999"
REGION_DESCONOCIDA = "99"

#: Año en que Ñuble empieza a existir como región. Antes de esto, sus comunas
#: se reportan bajo la región 08.
ANIO_CREACION_NUBLE = 2018

#: Número oficial de comunas del país. Si `cargar_dpa` devuelve menos, la tabla
#: está incompleta y el pipeline no debe publicar agregados territoriales.
#: (Valor a confirmar contra la DPA vigente del INE en Fase 1.)
N_COMUNAS_ESPERADO = 346


# --------------------------------------------------------------------------------------
# Normalización de texto
# --------------------------------------------------------------------------------------

def normalizar_texto(s: str) -> str:
    """Normaliza un nombre para comparación: sin tildes, sin puntuación, minúsculas.

    No es reversible ni sirve para mostrar; sirve solo como llave de comparación.

    >>> normalizar_texto("  O'Higgins ")
    'ohiggins'
    >>> normalizar_texto("Llay-Llay")
    'llay llay'
    >>> normalizar_texto("ÑUÑOA")
    'nunoa'
    """
    if s is None:
        return ""
    s = str(s).strip().lower()
    # Descomponer y eliminar diacríticos (incluye ñ -> n, que es lo que queremos
    # para comparar, porque las fuentes escriben "Nuble" y "Ñuble" indistintamente).
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Apóstrofos y puntos desaparecen; guiones y barras pasan a espacio.
    s = s.replace("'", "").replace("’", "").replace(".", "")
    for ch in "-/_,":
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s


#: Alias conocidos: {nombre_normalizado_alterno: nombre_normalizado_canonico}.
#:
#: Reglas para agregar entradas:
#:   - solo grafías realmente observadas en fuentes, no variantes hipotéticas;
#:   - toda entrada nueva requiere un test en tests/test_territorio.py;
#:   - jamás resolver un alias con un `if` dentro de un ingestor.
ALIAS: dict[str, str] = {
    # Grafías oficiales alternativas o históricas
    "coihaique": "coyhaique",
    "aisen": "aysen",
    "puerto aysen": "aysen",
    "puerto aisen": "aysen",
    "til til": "tiltil",
    "llay llay": "llaillay",
    "paiguano": "paihuano",
    "marchigue": "marchihue",
    "trehuaco": "treguaco",
    "alto bio bio": "alto biobio",
    "chol chol": "cholchol",
    "ollague": "ollague",  # tras normalizar, Ollagüe y Ollague colapsan igual
    # Nombre de la comuna vs. nombre de su capital
    "puerto natales": "natales",
    "rapa nui": "isla de pascua",
    "navarino": "cabo de hornos",
    "puerto williams": "cabo de hornos",
    # Abreviaciones frecuentes en planillas
    "calera": "la calera",
    "santiago centro": "santiago",
    "san vicente": "san vicente de tagua tagua",
    "concepcion penco": "penco",
}


def aplicar_alias(nombre_normalizado: str) -> str:
    """Devuelve el nombre canónico normalizado para un nombre ya normalizado."""
    return ALIAS.get(nombre_normalizado, nombre_normalizado)


# --------------------------------------------------------------------------------------
# Códigos
# --------------------------------------------------------------------------------------

def formatear_cut_comuna(valor: str | int) -> str:
    """Devuelve un CUT comunal de 5 dígitos como string con ceros a la izquierda.

    Los códigos comunales NUNCA deben viajar como enteros: `05101` se convierte
    en `5101` y el join falla en silencio para toda la región de Valparaíso.

    >>> formatear_cut_comuna(5101)
    '05101'
    >>> formatear_cut_comuna(" 13101 ")
    '13101'
    """
    s = str(valor).strip()
    if not s or s.lower() in {"nan", "none", ""}:
        raise TerritorioError("CUT comunal vacío")
    if not s.isdigit():
        raise TerritorioError(f"CUT comunal no numérico: {valor!r}")
    if len(s) > 5:
        raise TerritorioError(f"CUT comunal demasiado largo: {valor!r}")
    return s.zfill(5)


def region_de_comuna(cut_comuna: str) -> str:
    """Los dos primeros dígitos del CUT comunal son el CUT regional."""
    return formatear_cut_comuna(cut_comuna)[:2]


def region_vigente(cut_comuna: str, anio: int, dpa: DPA | None = None) -> str:
    """Región a la que pertenecía la comuna en un año dado.

    Resuelve el caso Ñuble: entre el inicio de la serie y 2017, las comunas hoy
    en la región 16 aparecen bajo la 08. Para comparar series largas hay que
    decidir un marco y aplicarlo consistentemente; este observatorio usa el
    **marco territorial vigente** (16 siempre) y expone esta función para poder
    reconstruir el marco histórico cuando se reconcilia con publicaciones antiguas.
    """
    cut = formatear_cut_comuna(cut_comuna)
    reg_actual = cut[:2]
    if reg_actual == "16" and anio < ANIO_CREACION_NUBLE:
        return "08"
    return reg_actual


# --------------------------------------------------------------------------------------
# Tabla DPA
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Comuna:
    cut: str
    nombre: str
    nombre_norm: str
    region_cut: str
    provincia: str | None = None


class DPA:
    """División Político-Administrativa cargada en memoria, con índices de búsqueda."""

    def __init__(self, comunas: list[Comuna]):
        self.comunas = comunas
        self.por_cut: dict[str, Comuna] = {c.cut: c for c in comunas}
        self.por_nombre: dict[str, list[Comuna]] = {}
        for c in comunas:
            self.por_nombre.setdefault(c.nombre_norm, []).append(c)

    def __len__(self) -> int:
        return len(self.comunas)

    @property
    def completa(self) -> bool:
        return len(self.comunas) >= N_COMUNAS_ESPERADO

    def nombres_ambiguos(self) -> list[str]:
        """Nombres normalizados que corresponden a más de una comuna."""
        return [n for n, cs in self.por_nombre.items() if len(cs) > 1]


def ruta_dpa_por_defecto() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "territorio_comunas.csv"


@lru_cache(maxsize=8)
def cargar_dpa(ruta: str | None = None) -> DPA:
    """Carga la tabla de comunas desde CSV.

    Columnas esperadas: comuna_cut, comuna_nombre, region_cut, provincia (opcional).
    """
    p = Path(ruta) if ruta else ruta_dpa_por_defecto()
    if not p.exists():
        raise TerritorioError(
            f"No existe la tabla DPA en {p}. Descargar la DPA oficial del INE "
            f"(ver docs/01-FUENTES.md, fuente ine_proyecciones/DPA)."
        )
    comunas: list[Comuna] = []
    with p.open(encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            if not fila.get("comuna_cut"):
                continue
            nombre = fila["comuna_nombre"].strip()
            cut = formatear_cut_comuna(fila["comuna_cut"])
            comunas.append(
                Comuna(
                    cut=cut,
                    nombre=nombre,
                    nombre_norm=aplicar_alias(normalizar_texto(nombre)),
                    region_cut=fila.get("region_cut", cut[:2]).zfill(2),
                    provincia=(fila.get("provincia") or None),
                )
            )
    return DPA(comunas)


def validar_dpa(dpa: DPA, estricto: bool = True) -> list[str]:
    """Valida integridad de la tabla DPA. Devuelve la lista de problemas.

    Con `estricto=True` (el modo de `obsm build gold`) una tabla incompleta es un
    error: publicar agregados comunales con una DPA parcial produce silenciosamente
    un país al que le faltan comunas.
    """
    problemas: list[str] = []
    if len(dpa) < N_COMUNAS_ESPERADO:
        problemas.append(
            f"DPA incompleta: {len(dpa)} comunas cargadas, se esperan {N_COMUNAS_ESPERADO}"
        )
    regiones_desconocidas = {c.region_cut for c in dpa.comunas} - set(REGIONES)
    if regiones_desconocidas:
        problemas.append(f"CUT de región desconocidos: {sorted(regiones_desconocidas)}")
    for c in dpa.comunas:
        if c.cut[:2] != c.region_cut:
            problemas.append(
                f"Inconsistencia: comuna {c.cut} ({c.nombre}) declara región {c.region_cut}"
            )
    duplicados = [cut for cut in dpa.por_cut if sum(1 for c in dpa.comunas if c.cut == cut) > 1]
    if duplicados:
        problemas.append(f"CUT duplicados: {sorted(set(duplicados))}")
    if estricto and problemas:
        raise TerritorioError("; ".join(problemas))
    return problemas


# --------------------------------------------------------------------------------------
# Resolución
# --------------------------------------------------------------------------------------

def normalizar_comuna(
    nombre: str,
    region_cut: str | None = None,
    dpa: DPA | None = None,
    estricto: bool = True,
) -> str:
    """Resuelve un nombre de comuna a su CUT de 5 dígitos.

    `region_cut` es opcional pero obligatorio cuando el nombre es ambiguo dentro
    de la DPA cargada. Ante ambigüedad sin región, falla: adivinar la comuna más
    poblada es el tipo de atajo que produce series equivocadas y difíciles de
    detectar después.

    Con `estricto=False` devuelve `COMUNA_DESCONOCIDA` en vez de lanzar, para
    permitir ingestas exploratorias que reportan tasa de no resolución.
    """
    dpa = dpa or cargar_dpa()
    clave = aplicar_alias(normalizar_texto(nombre))
    candidatos = dpa.por_nombre.get(clave, [])

    if region_cut:
        region_cut = str(region_cut).zfill(2)
        candidatos = [c for c in candidatos if c.region_cut == region_cut] or candidatos

    if len(candidatos) == 1:
        return candidatos[0].cut
    if not candidatos:
        if estricto:
            raise TerritorioError(
                f"Comuna no resuelta: {nombre!r} (normalizada: {clave!r}). "
                f"Si es una grafía legítima, agregarla a territorio.ALIAS con test."
            )
        return COMUNA_DESCONOCIDA
    if estricto:
        raise TerritorioError(
            f"Comuna ambigua: {nombre!r} corresponde a "
            f"{[(c.cut, c.region_cut) for c in candidatos]}. Se requiere region_cut."
        )
    return COMUNA_DESCONOCIDA


def normalizar_serie_comunas(
    nombres, region_cuts=None, dpa: DPA | None = None
) -> tuple[list[str], dict]:
    """Normaliza una secuencia de nombres y devuelve (cuts, reporte).

    El reporte incluye la tasa de no resolución, que es una métrica de calidad de
    primera clase: si sube de un corte a otro, la fuente cambió algo.
    """
    dpa = dpa or cargar_dpa()
    # Materializar ANTES de medir: si `nombres` es un generador, medir su largo lo
    # consume y la lista posterior queda vacía. Falla en silencio, con cero filas.
    nombres = list(nombres)
    region_cuts = list(region_cuts) if region_cuts is not None else [None] * len(nombres)
    if len(region_cuts) != len(nombres):
        raise TerritorioError(
            f"nombres ({len(nombres)}) y region_cuts ({len(region_cuts)}) no coinciden"
        )
    cuts: list[str] = []
    no_resueltos: dict[str, int] = {}
    for nombre, reg in zip(nombres, region_cuts, strict=True):
        try:
            cuts.append(normalizar_comuna(nombre, reg, dpa=dpa, estricto=True))
        except TerritorioError:
            cuts.append(COMUNA_DESCONOCIDA)
            no_resueltos[str(nombre)] = no_resueltos.get(str(nombre), 0) + 1
    total = len(nombres)
    reporte = {
        "total": total,
        "no_resueltos": sum(no_resueltos.values()),
        "tasa_no_resolucion": (sum(no_resueltos.values()) / total) if total else 0.0,
        "detalle": dict(sorted(no_resueltos.items(), key=lambda kv: -kv[1])),
    }
    return cuts, reporte
