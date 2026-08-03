"""Ingestor del visualizador de listas de espera del MINSAL.

Es la fuente que tiene la dimensión que al PDF de la Glosa 06 le falta —**mediana de días
de espera por Servicio de Salud**— y le falta la que el PDF sí tiene, que es el desglose por
especialidad. Son complementarias y **ninguna las cruza**: no existe fuente pública que diga
cuánto se espera por psiquiatría en una región concreta (ver A-015 en `docs/05-CALIDAD.md`
para la lección sobre inferir de la forma de los datos en vez de leer la fuente).

Estado: **verificado contra la fuente real** el 2026-07-29, bajando los 29 Servicios de
Salud más el agregado nacional: 780 filas, 30 series, 26 trimestres (2019-03 a 2025-06).
Nacional al 2025-06: 2.699.409 registros en espera de consulta de especialidad, mediana
264 días.

El sitio sirve un JSON por servicio, sin sesión ni token:

    https://www.listaesperasalud.cl/data/data_{SERVICIO}.json

Trampas de esta fuente, todas verificadas sobre la descarga completa:

1. **La mediana no existe antes de 2022.** Cobertura por año: 0 % en 2019-2021, 50 % en
   2022, 100 % desde 2023. Una serie de medianas que arranque en 2019 está comparando
   contra vacío. Se conserva el nulo y se declara; no se imputa.
2. **`ges_pacientes` está en el 3 % de las celdas** y `ges_mediana` se cae al 3 % en 2025.
   La lista GES es la peor cubierta de las tres.
3. **El trimestre viene como texto en español** —`"MARZO 2019"`— y hay que llevarlo a ISO
   (`2019-03`) para que ordene y se una con el resto del proyecto. `"ene-24"` es
   exactamente lo que `CLAUDE.md` §5 prohíbe dejar pasar.
4. **`promedio` y `mediana` son días y vienen con decimales.** 281,9 días de promedio es
   un promedio; 274,5 de mediana es lo que da un conjunto de tamaño par. Tiparlas como
   entero revienta la ingesta del archivo real. Es el caso **inverso** a A-010, donde los
   decimales aparecían en un conteo de personas y sí eran un error de la fuente: la
   pregunta no es si el número tiene coma, es qué mide.
5. **El campo `servicio` del JSON es un slug**, no el nombre de despliegue: dice
   `ARICA_Y_PARINACOTA`, no `Servicio de Salud Arica y Parinacota`. Resolverlo a nombre
   legible es trabajo de silver.
6. **El nombre de archivo de O'Higgins lleva apóstrofo tipográfico** (U+2019), no el recto.
   `data_SERVICIO_DE_SALUD_O’HIGGINS.json` responde 200 y con `'` da 404. Es la misma
   familia de trampas que `territorio.ALIAS` cubre para nombres de comuna, ahora en una
   ruta HTTP; por eso el slug se construye acá y no se escribe a mano.

Lo que este módulo **no** hace: resolver el Servicio de Salud a territorio comunal (un
Servicio agrupa varias comunas y el mapeo no es trivial), ni calcular nada.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from .base import Ingestor

log = logging.getLogger(__name__)

#: Las tres listas que publica el visualizador, con las cuatro métricas de cada una.
LISTAS = ("consulta", "quirurgica", "ges")
METRICAS = ("registros", "pacientes", "promedio", "mediana")

#: Métricas que son **conteos** y no pueden ser fraccionarias.
METRICAS_CONTEO = ("registros", "pacientes")
#: Métricas que son **días** y sí lo son legítimamente: un promedio de 281,9 días es un
#: promedio, y una mediana de 274,5 es lo que da un conjunto de tamaño par. Forzarlas a
#: entero reventaba la ingesta del archivo real —519 de 692 celdas de `ges_promedio` traen
#: decimales—, y redondearlas en silencio alteraría el dato. Ver A-010 para el caso
#: contrario: allá los decimales estaban en un CONTEO y sí eran un error de la fuente.
METRICAS_DIAS = ("promedio", "mediana")

#: El mes del trimestre, en el texto de la fuente. El corte es el último día del mes.
MESES = {"MARZO": "03", "JUNIO": "06", "SEPTIEMBRE": "09", "DICIEMBRE": "12"}

#: Primer año con medianas publicadas. Antes de esto la columna viene nula en toda la
#: serie y no es un dato faltante al azar: la fuente no las calculaba.
PRIMER_ANIO_CON_MEDIANA = 2022


def slug_servicio(nombre: str) -> str:
    """Nombre de archivo del JSON para un Servicio de Salud.

    Replica lo que hace el JavaScript del sitio: mayúsculas, espacios a guion bajo y
    tildes eliminadas. **No toca el apóstrofo**, y ahí está la trampa: el archivo de
    O'Higgins usa el tipográfico `’` (U+2019) y la misma URL con `'` responde 404.
    """
    s = nombre.upper().replace(" ", "_")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def periodo_iso(trimestre: str) -> str:
    """Pasa `"MARZO 2019"` a `"2019-03"`.

    Falla ante un mes desconocido en vez de devolver algo ordenable pero falso: un período
    mal formado se une en silencio con el trimestre equivocado.
    """
    partes = str(trimestre or "").strip().upper().split()
    if len(partes) != 2 or partes[0] not in MESES or not partes[1].isdigit():
        raise SchemaDriftError(
            f"[listaespera_minsal] trimestre no reconocido: {trimestre!r}. "
            f"Se esperaba '<MES> <AÑO>' con el mes en {sorted(MESES)}."
        )
    return f"{partes[1]}-{MESES[partes[0]]}"


class ListaEsperaMinsal(Ingestor):
    source_id = "listaespera_minsal"
    columnas_requeridas = (
        "servicio",
        "periodo",
        "anio",
        *(f"{lista}_{m}" for lista in LISTAS for m in METRICAS),
    )
    columnas_opcionales = ("trimestre",)

    def _leer(self, ruta: Path) -> pd.DataFrame:
        crudo = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if not isinstance(crudo, list) or not crudo:
            raise SchemaDriftError(
                f"[{self.source_id}] {Path(ruta).name} no es una lista de registros. "
                f"¿El sitio devolvió una página de error con código 200?"
            )
        df = pd.DataFrame(crudo)

        faltan = [c for c in ("servicio", "trimestre") if c not in df.columns]
        if faltan:
            raise SchemaDriftError(
                f"[{self.source_id}] faltan columnas de identificación {faltan}. "
                f"Presentes: {list(df.columns)[:8]}."
            )
        metricas = [f"{lista}_{m}" for lista in LISTAS for m in METRICAS]
        ausentes = [c for c in metricas if c not in df.columns]
        if ausentes:
            raise SchemaDriftError(
                f"[{self.source_id}] faltan métricas: {ausentes}. El visualizador publica "
                f"{len(metricas)} combinaciones de lista × métrica; que desaparezca una es "
                f"un cambio de esquema, no una celda vacía."
            )

        df["periodo"] = df["trimestre"].map(periodo_iso)
        df["anio"] = df["periodo"].str.slice(0, 4).astype("Int64")
        return df

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for lista in LISTAS:
            # Nullable a propósito en ambos casos: un nulo acá significa «la fuente no lo
            # publica» y es distinto de un cero. Rellenarlo con 0 diría que nadie espera.
            for m in METRICAS_CONTEO:
                col = f"{lista}_{m}"
                out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
            for m in METRICAS_DIAS:
                col = f"{lista}_{m}"
                out[col] = pd.to_numeric(out[col], errors="coerce").astype("Float64")
        out["servicio"] = out["servicio"].fillna("").astype(str).str.strip()

        sin_mediana = out[out["anio"] < PRIMER_ANIO_CON_MEDIANA]
        if len(sin_mediana) and sin_mediana["consulta_mediana"].notna().any():
            log.warning(
                "[%s] hay medianas antes de %d, cuando la fuente no las publicaba. "
                "Revisar si cambió la cobertura histórica.",
                self.source_id,
                PRIMER_ANIO_CON_MEDIANA,
            )
        out.attrs["cobertura_mediana"] = {
            f"{lista}_mediana": float(out[f"{lista}_mediana"].notna().mean()) for lista in LISTAS
        }
        log.info(
            "[%s] %d filas, %d servicios, %d trimestres (%s a %s)",
            self.source_id,
            len(out),
            out["servicio"].nunique(),
            out["periodo"].nunique(),
            out["periodo"].min(),
            out["periodo"].max(),
        )
        return out
