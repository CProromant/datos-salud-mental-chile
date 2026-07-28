"""Ingestor del REM Serie P, sección P6: población en control de salud mental.

Es la fuente que da lo que la mortalidad no puede dar. En el archivo de defunciones la
depresión son once muertes al año en todo Chile, porque casi nadie muere de depresión.
Acá son decenas de miles de personas en tratamiento, por comuna y por mes.

**Dos decisiones de diseño que no son opcionales:**

1. **Se filtra por `CodigoPrestacion` mientras se lee, no después.** El archivo trae todas
   las secciones del REM-P mezcladas y solo el 7,8 % es P6 —87.186 filas de 1.117.209 en
   2023—. Cargar el archivo completo para descartar el 92 % es lo que hizo que el ingestor
   de defunciones no llegara a arrancar (A-006). Se lee por trozos y se descarta al vuelo.

2. **El significado viene de `config/rem_secciones.yml`, por año.** Las columnas del archivo
   son genéricas: `Col01` a `Col38`. Lo que cuenta cada una depende del `CodigoPrestacion`
   de la fila y del año, porque el formulario se reordena. Un mapeo fijo en código quedaría
   obsoleto en la próxima publicación de DEIS.

El resultado es una tabla larga: una fila por establecimiento, mes, concepto y celda del
formulario, con su grupo etario y sexo ya resueltos.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yaml

from ..errors import SchemaDriftError
from ..io import detectar_separador, leer_primera_linea
from .base import Ingestor

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parents[3]
RUTA_MAPEO = RAIZ / "config" / "rem_secciones.yml"

#: Columnas de identificación del archivo, con su nombre canónico.
MAPA_COLUMNAS = {
    "Ano": "anio",
    "Mes": "mes",
    "IdservicioSalud": "servicio_salud",
    "IdServicio": "servicio_salud",
    "IdEstablecimiento": "establecimiento_deis",
    "CodigoPrestacion": "codigo_prestacion",
    "IdRegion": "region_cut_fuente",
    "IdComuna": "comuna_cut_fuente",
}

#: Cuántas filas se leen de una vez. El archivo de un año son ~1,1 millones de filas y
#: 113 MB; en trozos de este tamaño el proceso nunca pasa de unos cientos de megas.
FILAS_POR_TROZO = 200_000


def cargar_mapeo(ruta: Path | str | None = None) -> dict:
    """Lee `config/rem_secciones.yml`. Regenerable con `obsm rem mapear`."""
    ruta = Path(ruta) if ruta else RUTA_MAPEO
    if not ruta.exists():
        raise SchemaDriftError(
            f"No existe el mapeo del REM en {ruta}. Sin él las columnas del archivo son "
            f"`Col01`..`Col38` sin significado. Generarlo con `obsm rem mapear`."
        )
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


class RemPoblacionControl(Ingestor):
    source_id = "rem_salud_mental"
    columnas_requeridas = (
        "anio", "mes", "comuna_cut_fuente", "codigo_prestacion", "columna", "valor",
    )
    columnas_opcionales = ("establecimiento_deis", "region_cut_fuente", "servicio_salud")

    def __init__(self, fuente=None, mapeo: dict | None = None, hoja: str = "P6"):
        super().__init__(fuente)
        self._mapeo = mapeo
        self.hoja = hoja

    @property
    def mapeo(self) -> dict:
        if self._mapeo is None:
            self._mapeo = cargar_mapeo()
        return self._mapeo

    def _mapeo_del_anio(self, anio: int) -> dict:
        anios = self.mapeo.get("anios", {})
        # El YAML puede traer las claves como int o como str según cómo se generó.
        for clave in (anio, str(anio)):
            if clave in anios:
                return anios[clave]
        disponibles = sorted(str(a) for a in anios)
        raise SchemaDriftError(
            f"[{self.source_id}] no hay mapeo para {anio}. Años mapeados: {disponibles}. "
            f"Motivos de los que faltan: {self.mapeo.get('no_legibles', [])}. "
            f"Sin mapeo, las columnas del archivo no tienen significado."
        )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        primera, encoding = leer_primera_linea(ruta)
        sep = detectar_separador(primera)
        cabecera = [c.strip() for c in primera.split(sep)]

        anio = self._anio_del_archivo(ruta, sep, encoding)
        mapa_anio = self._mapeo_del_anio(anio)
        codigos = set(mapa_anio["conceptos"])
        cols_datos = [c for c in cabecera if c.lower().startswith("col")]
        if not cols_datos:
            raise SchemaDriftError(
                f"[{self.source_id}] el archivo no tiene columnas `ColNN`. "
                f"Encabezado: {cabecera[:12]}"
            )

        col_codigo = self._nombre_original(cabecera, "codigo_prestacion")
        trozos: list[pd.DataFrame] = []
        leidas = descartadas = 0
        for trozo in pd.read_csv(
            ruta, sep=sep, dtype=str, encoding=encoding, chunksize=FILAS_POR_TROZO
        ):
            leidas += len(trozo)
            # El filtro va acá y no después: solo el 7,8 % del archivo es de esta sección.
            sub = trozo[trozo[col_codigo].isin(codigos)]
            descartadas += len(trozo) - len(sub)
            if len(sub):
                trozos.append(sub.copy())

        log.info(
            "[%s] %s: %d filas leídas, %d descartadas por no ser de la sección %s",
            self.source_id, ruta.name, leidas, descartadas, self.hoja,
        )
        if not trozos:
            raise SchemaDriftError(
                f"[{self.source_id}] ninguna fila del archivo pertenece a la sección "
                f"{self.hoja} de {anio}. ¿Cambió la codificación de las prestaciones?"
            )

        ancho = pd.concat(trozos, ignore_index=True)
        return self._a_formato_largo(ancho, cabecera, cols_datos, mapa_anio)

    # -- ayudas --------------------------------------------------------------------------

    def _anio_del_archivo(self, ruta: Path, sep: str, encoding: str) -> int:
        """Lee el año de la primera fila de datos, no del nombre del archivo.

        El nombre puede venir renombrado por quien lo descargó; el contenido no.
        """
        muestra = pd.read_csv(ruta, sep=sep, dtype=str, encoding=encoding, nrows=5)
        col = self._nombre_original(list(muestra.columns), "anio")
        anios = pd.to_numeric(muestra[col], errors="coerce").dropna()
        if anios.empty:
            raise SchemaDriftError(f"[{self.source_id}] no se pudo leer el año de {ruta.name}")
        return int(anios.iloc[0])

    def _nombre_original(self, cabecera: list[str], canonico: str) -> str:
        for original, destino in MAPA_COLUMNAS.items():
            if destino == canonico and original in cabecera:
                return original
        raise SchemaDriftError(
            f"[{self.source_id}] falta la columna {canonico!r}. Encabezado: {cabecera[:12]}"
        )

    def _a_formato_largo(
        self, ancho: pd.DataFrame, cabecera: list[str], cols_datos: list[str], mapa_anio: dict
    ) -> pd.DataFrame:
        """Pasa las `ColNN` a filas y les pega su concepto, grupo etario y sexo."""
        ident = [c for c in cabecera if c in MAPA_COLUMNAS]
        largo = ancho.melt(
            id_vars=ident, value_vars=cols_datos, var_name="columna", value_name="valor"
        )
        largo = largo.rename(columns={c: MAPA_COLUMNAS[c] for c in ident})
        largo["columna"] = largo["columna"].str.upper()

        # Una celda vacía en el formulario es «no se reportó», no un cero. Se descartan
        # acá porque son la mayor parte del volumen: el formulario es ancho y disperso.
        largo = largo[largo["valor"].notna() & (largo["valor"].astype(str).str.strip() != "")]

        conceptos = mapa_anio["conceptos"]
        columnas = mapa_anio["columnas"]
        largo["grupo"] = largo["codigo_prestacion"].map(
            lambda c: conceptos.get(c, {}).get("grupo", "")
        )
        largo["concepto"] = largo["codigo_prestacion"].map(
            lambda c: conceptos.get(c, {}).get("concepto", "")
        )
        largo["grupo_edad_fuente"] = largo["columna"].map(
            lambda c: columnas.get(c, {}).get("grupo_edad", "")
        )
        largo["sexo"] = largo["columna"].map(lambda c: columnas.get(c, {}).get("sexo", ""))
        return largo.reset_index(drop=True)

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in ("anio", "mes"):
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

        # `valor` queda en float, no en entero, y no es un descuido. El archivo trae unos
        # pocos valores fraccionarios —«123.55 personas» en 2014— que son errores de
        # digitación del formulario. Forzarlos a entero haría una de dos cosas malas:
        # reventar la ingesta del año completo, o redondear en silencio y alterar el dato.
        # Se conservan tal cual y se cuentan; redondear es decisión de la capa que publica,
        # que además puede declararlo. Ver CLAUDE.md §7: un dato raro se documenta, no se
        # arregla.
        out["valor"] = pd.to_numeric(out["valor"], errors="coerce")
        fraccionarios = out["valor"].notna() & (out["valor"] % 1 != 0)
        if fraccionarios.any():
            log.warning(
                "[%s] %d valores fraccionarios en un conteo de personas (ej. %s). "
                "Son errores de digitación de la fuente; se conservan sin redondear.",
                self.source_id, int(fraccionarios.sum()),
                out.loc[fraccionarios, "valor"].head(3).tolist(),
            )
        out.attrs["valores_fraccionarios"] = int(fraccionarios.sum())
        # El código territorial se deja como string y sin rellenar: resolver comunas es
        # trabajo de silver (ver la tabla de capas en docs/02-ARQUITECTURA.md).
        for col in ("comuna_cut_fuente", "region_cut_fuente", "establecimiento_deis"):
            if col in out.columns:
                out[col] = out[col].fillna("").astype(str).str.strip()
        return out
