"""Entrada/salida: descarga con caché, hash, detección de encoding y manifiesto.

Todo el I/O del proyecto pasa por acá para que la procedencia sea automática y no
dependa de que alguien se acuerde de anotarla.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import PIPELINE_VERSION
from .errors import SourceUnavailableError

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parents[2]
DIR_DATOS = RAIZ / "data"
ENCODINGS_CANDIDATOS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


# --------------------------------------------------------------------------------------
# Manifiesto de procedencia
# --------------------------------------------------------------------------------------

@dataclass
class Manifiesto:
    """Procedencia de un artefacto de datos. Se escribe junto a cada salida.

    Sin esto, un CSV publicado es una afirmación sin respaldo. Con esto, cualquiera
    puede rehacer exactamente el mismo archivo o mostrar que la fuente cambió.
    """

    source_id: str
    url: str | None
    fecha_extraccion: str
    sha256: str | None
    bytes: int | None
    encoding: str | None
    pipeline_version: str = PIPELINE_VERSION
    source_version: str | None = None
    filas: int | None = None
    notas: list[str] = field(default_factory=list)

    def escribir(self, destino: Path) -> Path:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destino


def ahora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_archivo(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for chunk in iter(lambda: fh.read(bloque), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------------------
# Lectura robusta
# --------------------------------------------------------------------------------------

def detectar_encoding(ruta: Path, muestra_bytes: int = 200_000) -> str:
    """Detecta el encoding probando candidatos en orden de plausibilidad.

    Las fuentes del sector público chileno mezclan UTF-8, CP1252 y Latin-1, a veces
    dentro del mismo portal. Adivinar mal no rompe la lectura: rompe los nombres de
    comuna, que es peor porque falla silenciosamente en el join.
    """
    ruta = Path(ruta)
    # Se lee SOLO la muestra. `read_bytes()[:muestra_bytes]` cargaba el archivo entero
    # antes de recortar: con las defunciones DEIS eso son 869 MB para mirar 200 KB, y el
    # ingestor no llegaba a arrancar. Un fixture de 15 filas no puede exponer esto.
    with ruta.open("rb") as fh:
        datos = fh.read(muestra_bytes)
    # Un corte a mitad de carácter multibyte haría fallar a UTF-8 por el final del buffer
    # y no por el contenido, que es justo el falso negativo que llevaría a latin-1.
    datos = datos.rsplit(b"\n", 1)[0] if b"\n" in datos else datos
    for enc in ENCODINGS_CANDIDATOS:
        try:
            texto = datos.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        # Señal de mojibake: si aparecen estas secuencias, decodificamos con el
        # encoding equivocado aunque no haya lanzado excepción.
        if any(marca in texto for marca in ("Ã±", "Ã³", "Ã©", "Ã­", "Â¿")):
            continue
        return enc
    return "latin-1"  # nunca falla; queda registrado en el manifiesto


def leer_texto(ruta: Path) -> tuple[str, str]:
    """Devuelve (contenido, encoding_usado).

    Carga el archivo completo en memoria: úsala solo cuando de verdad se necesite todo
    el texto. Para leer el encabezado de un CSV grande está `leer_primera_linea`.
    """
    enc = detectar_encoding(ruta)
    return Path(ruta).read_text(encoding=enc), enc


def leer_primera_linea(ruta: Path) -> tuple[str, str]:
    """Devuelve (primera_linea, encoding_usado) sin cargar el resto del archivo.

    Los ingestores necesitan el encabezado para detectar el separador, no el contenido.
    Leerlo con `leer_texto` cuesta un archivo entero en RAM por cada ingesta.
    """
    enc = detectar_encoding(ruta)
    with Path(ruta).open("r", encoding=enc) as fh:
        return fh.readline().rstrip("\r\n"), enc


def detectar_separador(primera_linea: str) -> str:
    """Heurística simple: gana el separador con más ocurrencias fuera de comillas."""
    candidatos = {";": 0, ",": 0, "\t": 0, "|": 0}
    en_comillas = False
    for ch in primera_linea:
        if ch == '"':
            en_comillas = not en_comillas
        elif not en_comillas and ch in candidatos:
            candidatos[ch] += 1
    return max(candidatos, key=lambda k: candidatos[k])


_RE_NUM = re.compile(r"[^\d,.\-]")


def _inferir_decimal(s: str) -> str:
    """Decide si el separador decimal es coma o punto en una cadena ya limpia.

    El caso genuinamente ambiguo es un único separador seguido de exactamente tres
    dígitos: "1.500" son mil quinientos en una planilla chilena y uno coma cinco en
    una anglosajona. La regla elegida, con su costo declarado:

      - dos o más separadores del mismo tipo  -> ese tipo es de miles;
      - coma y punto juntos                   -> manda el que aparece más a la derecha;
      - un separador con 3 dígitos detrás     -> es de miles, SALVO que la parte
        entera sea "0", porque "0.005" es casi siempre una proporción, no cinco;
      - cualquier otro caso                   -> decimal.

    El costo: una proporción escrita "1.000" se leerá como mil. Por eso las funciones
    que leen tasas o proporciones deben pasar `decimal` explícitamente en vez de
    confiar en la inferencia.
    """
    tiene_coma, tiene_punto = "," in s, "." in s
    if tiene_coma and tiene_punto:
        return "," if s.rfind(",") > s.rfind(".") else "."
    sep = "," if tiene_coma else ("." if tiene_punto else ".")
    if not (tiene_coma or tiene_punto):
        return "."
    if s.count(sep) >= 2:
        return "." if sep == "," else ","  # el separador repetido es de miles
    entero, _, resto = s.rpartition(sep)
    if len(resto) == 3 and entero.lstrip("-") != "0":
        return "." if sep == "," else ","  # miles
    return sep


def a_numero(valor, decimal: str | None = None) -> float:
    """Convierte texto numérico chileno a float.

    Maneja "1.234,5" (punto de miles, coma decimal), "1,234.5" y "1234.5".
    Devuelve NaN ante vacío o basura, nunca lanza: la limpieza informa, no aborta.

    >>> a_numero("1.234,5")
    1234.5
    >>> a_numero("12,7%")
    12.7
    >>> a_numero("")
    nan
    """
    if valor is None:
        return float("nan")
    if isinstance(valor, (int, float)):
        return float(valor)
    s = _RE_NUM.sub("", str(valor).strip())
    if not s or s in {"-", ".", ","}:
        return float("nan")
    if decimal is None:
        decimal = _inferir_decimal(s)
    s = s.replace(".", "").replace(",", ".") if decimal == "," else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return float("nan")


# --------------------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------------------

def descargar(
    url: str,
    destino: Path,
    source_id: str,
    timeout: int = 60,
    reintentos: int = 3,
    user_agent: str = f"obsm/{PIPELINE_VERSION}",
    forzar: bool = False,
) -> Manifiesto:
    """Descarga con reintentos y devuelve el manifiesto. No reescribe si ya existe.

    `requests` se importa dentro de la función a propósito: el resto del paquete
    debe poder usarse (y testearse) sin red ni dependencia HTTP.
    """
    import requests  # noqa: PLC0415

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists() and not forzar:
        log.info("Ya existe en caché: %s", destino)
    else:
        ultimo_error: Exception | None = None
        for intento in range(1, reintentos + 1):
            try:
                resp = requests.get(
                    url, timeout=timeout, headers={"User-Agent": user_agent}, stream=True
                )
                resp.raise_for_status()
                with destino.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        fh.write(chunk)
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_error = exc
                log.warning("Intento %d/%d falló para %s: %s", intento, reintentos, url, exc)
        else:
            raise SourceUnavailableError(f"No se pudo descargar {url}: {ultimo_error}")

    return Manifiesto(
        source_id=source_id,
        url=url,
        fecha_extraccion=ahora_iso(),
        sha256=sha256_archivo(destino),
        bytes=destino.stat().st_size,
        encoding=detectar_encoding(destino),
    )


def ruta_capa(capa: str, source_id: str, nombre: str) -> Path:
    """Ruta canónica dentro del almacén: data/<capa>/<source_id>/<nombre>."""
    if capa not in {"raw", "bronze", "silver", "gold"}:
        raise ValueError(f"Capa desconocida: {capa}")
    return DIR_DATOS / capa / source_id / nombre
