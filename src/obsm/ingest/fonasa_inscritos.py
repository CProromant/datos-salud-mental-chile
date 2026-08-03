"""Ingestor de la población inscrita validada en servicios de salud municipal.

Es el denominador que le falta al REM: convierte «108.496 personas con depresión moderada»
en «de los inscritos en la APS municipal, tantos por mil están en control». Sin él, una
comuna grande siempre parece tener más enfermedad que una chica.

Estado: **verificado contra la fuente real** el 2026-07-28, sobre la descarga completa de
SINIM (345 comunas × 25 años, 2001–2025, 491.120 bytes). Total nacional 2025: 14.807.159
inscritos, 73,3 % de la población proyectada por el INE.

**El dato lo produce FONASA** al validar la población para el per cápita, pero FONASA no lo
publica como archivo: su portal de datos abiertos es un WordPress con un plugin de gráficos,
sin API ni índice descargable. SINIM (SUBDERE) sí lo expone, declarando a FONASA como fuente.
Por eso el `source_id` dice FONASA y el dominio dice SINIM.

Trampas de esta fuente, todas verificadas sobre el archivo completo:

1. **Se sirve como `.xls` pero es SpreadsheetML 2003**, es decir XML. `xlrd` no lo abre y
   `pandas.read_excel` tampoco. Además el cuerpo empieza con un salto de línea *antes* del
   prólogo XML, lo que hace fallar a cualquier parser estricto: hay que hacer `lstrip()`.
2. **El código de comuna viene declarado `ss:Type="Number"` pero con el cero a la izquierda
   intacto** en el texto (`01402`). Se lee el texto del nodo y nunca el tipo declarado:
   creerle al `ss:Type` es exactamente cómo `01402` se convierte en `1402`.
3. **Cuatro valores no son números y ninguno es cero ni faltante al azar:**
   `Costo Fijo` (comuna financiada por costo fijo, no por per cápita), `Sin Servicio` (la
   APS no la administra el municipio sino el Servicio de Salud), `No Recepcionado` (el dato
   no llegó; **todo 2023** viene así en las 345 comunas) y `No Aplica` (la comuna no existía
   aún). Se conservan en `motivo_sin_dato`. Un centinela nuevo es `SchemaDriftError`: si
   SINIM inventa una marca, hay que decidir qué significa antes de contarla.
4. **Desde ~2019 SINIM escribe `0` donde antes escribía `Sin Servicio`.** Ese cero NO es
   cero inscritos. Acá se conserva tal cual —el ingestor no infiere nada entre filas— y se
   resuelve en `transform/silver.py`, que sí ve la serie completa. Ver A-013.
5. **SpreadsheetML omite las celdas vacías** y numera la siguiente con `ss:Index`. El
   archivo de hoy no las trae, pero el formato las permite: leer las celdas en orden sin
   honrar `ss:Index` correría todos los años de una comuna en silencio.

Lo que este módulo **no** hace: resolver territorio, decidir qué significa un cero, ni
calcular cobertura. Bronze es una traducción fiel del archivo, con los centinelas intactos.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from .base import Ingestor

log = logging.getLogger(__name__)

#: Espacio de nombres de SpreadsheetML 2003.
NS_SS = "urn:schemas-microsoft-com:office:spreadsheet"
NS = {"s": NS_SS}
#: `ss:Index` y `ss:Type` con el prefijo expandido, que es como los devuelve ElementTree.
ATTR_INDEX = f"{{{NS_SS}}}Index"

#: Encabezado de la primera columna. Se busca la fila que lo contiene en vez de asumir
#: que es la tercera: SINIM antepone una línea de glosa que puede cambiar de largo.
ENCABEZADO_CODIGO = "CODIGO"
ENCABEZADO_MUNICIPIO = "MUNICIPIO"

#: Un año de la cabecera. Las columnas de datos son exactamente estas.
PATRON_ANIO = re.compile(r"^(19|20)\d{2}$")

#: El código de la variable, primer token de la fila que va sobre la cabecera:
#: `HPISM (N°) Población Inscrita Validada…` → `HPISM`. Un pedido de varias variables
#: devuelve bloques de años consecutivos, uno por variable, y el año por sí solo deja de
#: identificar la columna: 2025 aparece cuatro veces.
PATRON_CODIGO_VARIABLE = re.compile(r"^([A-Z][A-Z0-9]{2,15})\b")

#: Las marcas no numéricas de la fuente, normalizadas a minúsculas sin espacios extra.
#: El valor es el motivo canónico que viaja a bronze.
MOTIVOS_SIN_DATO = {
    "costo fijo": "costo_fijo",
    "sin servicio": "sin_servicio_municipal",
    "no recepcionado": "no_recepcionado",
    "no aplica": "no_aplica",
}


def _texto(nodo: ET.Element | None) -> str:
    return " ".join((nodo.text or "").split()) if nodo is not None else ""


def _celdas(fila: ET.Element) -> list[str]:
    """Devuelve los valores de una fila **respetando `ss:Index`**.

    En SpreadsheetML una celda vacía no se escribe: se omite y la siguiente declara su
    posición real con `ss:Index` (1-based). Leer los `<Cell>` en orden es correcto solo
    mientras no falte ninguno, y deja de serlo sin avisar en cuanto falta uno.
    """
    valores: list[str] = []
    for celda in fila.findall("s:Cell", NS):
        indice = celda.get(ATTR_INDEX)
        if indice is not None:
            destino = int(indice) - 1
            while len(valores) < destino:
                valores.append("")
        valores.append(_texto(celda.find("s:Data", NS)))
    return valores


class FonasaInscritos(Ingestor):
    source_id = "fonasa_inscritos"
    columnas_requeridas = (
        "comuna_cut_fuente",
        "anio",
        "variable_codigo",
        "valor_crudo",
        "poblacion_inscrita",
        "motivo_sin_dato",
    )
    columnas_opcionales = ("comuna_nombre",)

    def _leer(self, ruta: Path) -> pd.DataFrame:
        # lstrip(): el cuerpo que sirve SINIM trae un \n antes del prólogo XML y sin esto
        # ElementTree falla con «XML or text declaration not at start of entity».
        raiz = ET.fromstring(Path(ruta).read_bytes().lstrip())
        filas = [_celdas(f) for f in raiz.findall(".//s:Row", NS)]
        if not filas:
            raise SchemaDriftError(
                f"[{self.source_id}] el archivo no tiene ninguna fila <Row>. "
                f"¿SINIM dejó de exportar SpreadsheetML, o la consulta devolvió un error?"
            )

        i_cab, columnas = self._cabecera(filas)
        registros = []
        for fila in filas[i_cab + 1 :]:
            if len(fila) < 2 or not fila[0].strip():
                continue
            for pos, (variable, anio) in columnas.items():
                crudo = fila[pos] if pos < len(fila) else ""
                registros.append(
                    {
                        "comuna_cut_fuente": fila[0].strip(),
                        "comuna_nombre": fila[1].strip(),
                        "variable_codigo": variable,
                        "anio": anio,
                        "valor_crudo": crudo,
                    }
                )
        if not registros:
            raise SchemaDriftError(
                f"[{self.source_id}] la cabecera se encontró en la fila {i_cab} pero no hay "
                f"ninguna fila de datos debajo."
            )
        return self._clasificar(pd.DataFrame(registros))

    # -- ayudas de lectura ---------------------------------------------------------------

    def _cabecera(self, filas: list[list[str]]) -> tuple[int, dict[int, tuple[str, str]]]:
        """Ubica la fila `CODIGO | MUNICIPIO | 2025 | ...` y mapea {posición: (variable, año)}.

        Se busca por contenido y no por número de fila: SINIM antepone una glosa
        («Valores en miles de peso», que además no aplica a esta variable) y el nombre de
        la variable, y ese preámbulo no tiene por qué mantener su largo entre versiones.

        La variable sale de la fila inmediatamente superior. **El año solo no identifica la
        columna**: pedir cuatro variables devuelve cuatro bloques de años consecutivos y
        2025 aparece cuatro veces. Sin el código de variable, los cuatro valores caerían
        sobre la misma llave y quedaría el último, en silencio.
        """
        for i, fila in enumerate(filas):
            if len(fila) < 3:
                continue
            if fila[0].strip().upper() != ENCABEZADO_CODIGO:
                continue
            if fila[1].strip().upper() != ENCABEZADO_MUNICIPIO:
                continue
            variables = self._variables_por_columna(filas[i - 1] if i else [], len(fila))
            columnas = {
                pos: (variables[pos], v.strip())
                for pos, v in enumerate(fila)
                if pos >= 2 and PATRON_ANIO.match(v.strip())
            }
            if not columnas:
                raise SchemaDriftError(
                    f"[{self.source_id}] la fila de cabecera no declara ningún año: "
                    f"{fila[:8]}. Sin años no hay columnas de datos que leer."
                )
            return i, columnas
        raise SchemaDriftError(
            f"[{self.source_id}] no se encontró la fila de cabecera "
            f"{ENCABEZADO_CODIGO!r}/{ENCABEZADO_MUNICIPIO!r}. Primeras filas: "
            f"{[f[:3] for f in filas[:5]]}. Revisar la exportación de SINIM antes de "
            f"relajar la búsqueda."
        )

    def _variables_por_columna(self, fila_nombres: list[str], ancho: int) -> list[str]:
        """Código de variable para cada columna, arrastrando hacia la derecha.

        Cuando se pide una sola variable, SINIM escribe su nombre una vez y deja el resto
        de la fila vacío; cuando se piden varias, lo repite en cada columna. El arrastre
        cubre los dos casos sin distinguirlos.
        """
        salida: list[str] = []
        actual = ""
        for pos in range(ancho):
            bruto = fila_nombres[pos].strip() if pos < len(fila_nombres) else ""
            if m := PATRON_CODIGO_VARIABLE.match(bruto):
                actual = m.group(1)
            salida.append(actual)
        return salida

    def _clasificar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Separa el número del centinela. Un centinela desconocido detiene la ingesta."""
        out = df.copy()
        crudo = out["valor_crudo"].fillna("").astype(str).str.strip()
        numero = pd.to_numeric(crudo, errors="coerce")

        clave = crudo.str.lower()
        out["motivo_sin_dato"] = clave.map(MOTIVOS_SIN_DATO).fillna("")
        out["poblacion_inscrita"] = numero

        # No numérico, no vacío y no reconocido: la fuente inventó una marca.
        sin_clasificar = numero.isna() & (out["motivo_sin_dato"] == "") & (crudo != "")
        desconocidos = sorted(set(crudo[sin_clasificar]))
        if desconocidos:
            raise SchemaDriftError(
                f"[{self.source_id}] valores no numéricos no reconocidos: {desconocidos[:6]}. "
                f"Los conocidos son {sorted(MOTIVOS_SIN_DATO)}. Una marca nueva significa algo "
                f"—no es cero ni faltante— y hay que decidir qué antes de contarla."
            )
        return out

    # -- posproceso ----------------------------------------------------------------------

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["anio"] = pd.to_numeric(out["anio"], errors="coerce").astype("Int64")
        out["poblacion_inscrita"] = out["poblacion_inscrita"].astype("Int64")
        # El CUT se deja como string sin rellenar: resolver territorio es trabajo de silver.
        out["comuna_cut_fuente"] = out["comuna_cut_fuente"].fillna("").astype(str).str.strip()

        n_cent = int((out["motivo_sin_dato"] != "").sum())
        if n_cent:
            reparto = out.loc[out["motivo_sin_dato"] != "", "motivo_sin_dato"].value_counts()
            log.info(
                "[%s] %d celdas sin dato numérico: %s",
                self.source_id,
                n_cent,
                reparto.to_dict(),
            )
        return out
