"""Ingestor del maestro de establecimientos de salud del DEIS.

Responde una pregunta que ninguna otra fuente del proyecto responde: **quién administra la
atención primaria de cada comuna**. Y de eso depende que un denominador de cobertura
signifique algo.

Estado: **verificado contra la fuente real** el 2026-07-29, sobre `establecimientos_20260721.csv`
(sha256 `f16b9dc1…`, 2.485.250 bytes, 5.707 establecimientos, separador `;`, UTF-8).
**Licencia CC0** declarada en el portal, la única fuente del proyecto sin restricción.

Por qué importa acá. `fonasa_inscritos` cuenta inscritos en APS **municipal**; el REM cuenta
actividad de **toda** la APS pública. Donde la comuna se atiende en un hospital comunitario
dependiente del Servicio de Salud, el numerador incluye a esa población y el denominador no,
y la cobertura que salga de dividirlos no significa nada. Este maestro es lo que permite
saber en qué comunas pasa eso, y dejó de ser una sospecha para ser un conteo (A-015).

Trampas de esta fuente, todas verificadas sobre el archivo completo:

1. **Dos columnas de código y solo una sirve.** `EstablecimientoCodigo` es la vigente y calza
   con las 1.889 del padrón de FONASA; `EstablecimientoCodigoAntiguo` tiene otro formato
   (`03-216`) y da **cero** coincidencias. Elegir por orden de aparición toma la equivocada.
2. **El nivel de atención tiene dos grafías simultáneas.** `Primer Nivel` (2.478) y
   `Primario` (534) conviven en el mismo archivo y son lo mismo; igual `Segundo
   Nivel`/`Secundario` y `Tercer Nivel`/`Terciario`. Filtrar por una sola pierde el 18 % de
   la APS.
3. **`EstadoFuncionamiento` cambia de caja.** `Vigente en Operación Habitual` (5.086) y
   `Vigente en operación habitual` (209) son el mismo estado. Comparar por igualdad exacta
   descarta 209 establecimientos vigentes.
4. **El archivo es UTF-8.** Leerlo como latin-1 no falla: produce `OperaciÃ³n`, que después
   no calza con ningún filtro y se ve como si esos establecimientos no existieran.
5. **Es un corte actual, sin vigencias.** Trae `FechaInicioFuncionamientoEstab` y
   `FechaCierre`, pero la fotografía es la de hoy. Cruzarlo con una serie histórica atribuye
   al pasado la organización presente; para eso hay que reconstruir vigencias, que este
   módulo **no** hace y por eso el resultado no debe usarse año por año sin advertirlo.

Lo que este módulo **no** hace: resolver territorio ni decidir qué es «APS». Bronze traduce
el archivo y normaliza las grafías que son ruido de digitación; la composición de la APS por
comuna se calcula en `transform/silver.py`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from ..io import detectar_separador, leer_primera_linea
from .base import Ingestor, renombrar_columnas

log = logging.getLogger(__name__)

#: {nombre_en_la_fuente: nombre_canonico}. Se toma un subconjunto: el archivo trae 33
#: columnas y las de dirección, teléfono y coordenadas no se usan en este proyecto.
MAPA_COLUMNAS = {
    "EstablecimientoCodigo": "establecimiento_deis",
    "EstablecimientoCodigoAntiguo": "establecimiento_codigo_antiguo",
    "EstablecimientoGlosa": "establecimiento_nombre",
    "TipoEstablecimientoGlosa": "tipo_establecimiento",
    "DependenciaAdministrativa": "dependencia",
    "NivelAtencionEstabglosa": "nivel_atencion_fuente",
    "ComunaCodigo": "comuna_cut_fuente",
    "ComunaGlosa": "comuna_nombre",
    "RegionCodigo": "region_cut_fuente",
    "RegionGlosa": "region_nombre",
    "SeremiSaludGlosa_ServicioDeSaludGlosa": "servicio_salud",
    "TipoSistemaSaludGlosa": "sistema_salud",
    "EstadoFuncionamiento": "estado_funcionamiento",
    "FechaInicioFuncionamientoEstab": "fecha_inicio",
    "FechaCierre": "fecha_cierre",
}

#: Las dos grafías de cada nivel, normalizadas a una. El archivo usa ambas a la vez.
NIVELES = {
    "primer nivel": "primario",
    "primario": "primario",
    "segundo nivel": "secundario",
    "secundario": "secundario",
    "tercer nivel": "terciario",
    "terciario": "terciario",
    "no aplica": "no_aplica",
}


class DeisEstablecimientos(Ingestor):
    source_id = "deis_establecimientos"
    columnas_requeridas = (
        "establecimiento_deis", "comuna_cut_fuente", "dependencia",
        "nivel_atencion", "sistema_salud", "vigente",
    )
    columnas_opcionales = (
        "establecimiento_nombre", "tipo_establecimiento", "comuna_nombre",
        "region_cut_fuente", "servicio_salud", "fecha_inicio", "fecha_cierre",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        primera, encoding = leer_primera_linea(ruta)
        sep = detectar_separador(primera)
        # dtype=str en todo: `ComunaCodigo` y `EstablecimientoCodigo` pierden ceros a la
        # izquierda si pandas los infiere como enteros, y ese daño no se deshace después.
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str)
        df.attrs["encoding"] = encoding

        cabecera = list(df.columns)
        if "EstablecimientoCodigo" not in cabecera:
            raise SchemaDriftError(
                f"[{self.source_id}] falta 'EstablecimientoCodigo'. Presentes: "
                f"{cabecera[:12]}. Ojo: 'EstablecimientoCodigoAntiguo' NO sirve como "
                f"reemplazo — usa otro formato y no calza con el padrón de FONASA."
            )
        df = renombrar_columnas(df, MAPA_COLUMNAS)
        return self._normalizar_glosas(df)

    def _normalizar_glosas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Unifica las grafías que son ruido de digitación, no información.

        Va en `_leer` y no en `_posproceso` porque `preparar` valida el contrato **antes**
        de posprocesar: una columna requerida que nace después haría fallar la ingesta con
        un mensaje que culpa a la fuente.
        """
        from ..territorio import normalizar_texto  # noqa: PLC0415

        out = df.copy()
        nivel = out["nivel_atencion_fuente"].fillna("").map(normalizar_texto).str.lower()
        out["nivel_atencion"] = nivel.map(NIVELES).fillna("")

        desconocidos = sorted(set(nivel[out["nivel_atencion"] == ""]) - {""})
        if desconocidos:
            raise SchemaDriftError(
                f"[{self.source_id}] niveles de atención no reconocidos: {desconocidos[:6]}. "
                f"Conocidos: {sorted(set(NIVELES))}. Un nivel nuevo cambia qué cuenta como "
                f"APS y hay que decidirlo, no adivinarlo."
            )

        # «Vigente en Operación Habitual» y «Vigente en operación habitual» son el mismo
        # estado escrito de dos formas. Comparar por igualdad exacta descarta 209 vigentes.
        estado = out["estado_funcionamiento"].fillna("").map(normalizar_texto).str.lower()
        out["vigente"] = estado.str.startswith("vigente")
        return out

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        from ..territorio import normalizar_texto  # noqa: PLC0415

        out["dependencia"] = out["dependencia"].fillna("").map(normalizar_texto).str.lower()
        out["sistema_salud"] = out["sistema_salud"].fillna("").map(normalizar_texto).str.lower()
        # El código territorial se deja como string sin rellenar: resolver territorio es
        # trabajo de silver (ver la tabla de capas en docs/02-ARQUITECTURA.md).
        for col in ("comuna_cut_fuente", "region_cut_fuente", "establecimiento_deis"):
            if col in out.columns:
                out[col] = out[col].fillna("").astype(str).str.strip()

        log.info(
            "[%s] %d establecimientos, %d vigentes, %d de primer nivel público",
            self.source_id, len(out), int(out["vigente"].sum()),
            int((out["vigente"] & out["nivel_atencion"].eq("primario")
                 & out["sistema_salud"].eq("publico")).sum()),
        )
        return out
