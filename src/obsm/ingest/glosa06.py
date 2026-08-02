"""Parser de la tabla de especialidades del informe trimestral de la Glosa 06.

Es la **única** fuente pública que dice cuánta gente espera por psiquiatría en Chile:
22.963 adultos y 13.960 niños y adolescentes al 30 de septiembre de 2025. El visualizador
del MINSAL (`listaespera_minsal`) tiene los días de espera pero agrega todas las
especialidades; este PDF tiene la especialidad pero no los días. Ninguna fuente cruza las
dos cosas, aunque la letra b) de la propia glosa lo exija.

Estado: **verificado contra dos informes reales** el 2026-07-29 (III trim 2025 y I trim
2026). Son texto, no escaneo: 55-56 páginas producidas desde Word.

**El parser es frágil por diseño** (`CLAUDE.md` §8): declara qué formato reconoció y falla
si no reconoce ninguno, en vez de adivinar. Un informe rediseñado tiene que romperlo
ruidosamente; adaptarse solo es cómo se publica una serie rota.

El módulo separa leer el PDF de interpretar el texto a propósito. `extraer_paginas` hace
I/O y necesita PyMuPDF; `parsear_tabla_especialidades` es pura y se prueba con fixtures de
texto, que es donde está el riesgo real y donde el caso feo se ve en el diff.

Dos formatos observados en dos trimestres consecutivos, y ninguno es estable:

    2025-T3   PSIQUIATRÍA ADULTO                      orden ALFABÉTICO, MAYÚSCULAS
              PSIQUIATRÍA PEDIÁTRICA Y DE LA ...
    2026-T1   Psiquiatría adulta                      orden por MAGNITUD, Capitalizado
              Psiquiatría pediátrica y de la ...

Nótese «ADULTO» contra «adulta»: cambia la caja **y** el género. Agrupar por la cadena
cruda parte la serie en dos, que es exactamente A-012 en otra fuente.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd

from ..errors import SchemaDriftError
from ..quality import detectar_filas_total
from .base import Ingestor

log = logging.getLogger(__name__)

#: Encabezados que marcan el inicio de la tabla de especialidades. Se busca por contenido
#: normalizado y no por número de página: la tabla estaba en la 27 en 2025 y en la 29 en
#: 2026, y anclar en un número es la forma más común de leer mal un informe que se reordena.
ENCABEZADO_ESPECIALIDAD = "ESPECIALIDAD MEDICA"
ENCABEZADO_REGISTROS = "N DE REGISTROS"

#: Un número con punto de miles, tal como lo escribe el informe: `22.963`.
PATRON_REGISTROS = re.compile(r"^\d{1,3}(?:\.\d{3})*$")

#: Líneas de encabezado y pie que el extractor devuelve mezcladas con la tabla. Sin
#: excluirlas, el pie «Glosa 06 III trimestre 2025» se empareja con el número de página
#: siguiente y entra como una especialidad de 27 registros. Se detectó porque la suma del
#: detalle superaba en exactamente 27 al total que el informe declara: el ancla propia de
#: la fuente delató una fila inventada por el parser.
MOBILIARIO_DE_PAGINA = ("GLOSA", "MINISTERIO DE SALUD", "INFORME GLOSA", "TRIMESTRE")

#: Cuántas páginas puede abarcar la tabla. En 2025 el encabezado queda al pie de una página
#: y las especialidades siguen en la siguiente; parsear solo la página del encabezado daba
#: una tabla a medias que igual superaba el mínimo de filas y pasaba en silencio.
PAGINAS_QUE_PUEDE_CRUZAR = 4

#: Las dos especialidades de salud mental, por su llave normalizada. El valor es la
#: etiqueta canónica que se publica.
#:
#: `ADULTO` y `adulta` son el mismo concepto escrito distinto en dos trimestres
#: consecutivos. La llave normaliza caja, tildes y la terminación de género, para que la
#: serie no se parta en dos (A-012).
ESPECIALIDADES_SALUD_MENTAL = {
    "PSIQUIATRIA ADULT": "Psiquiatría adulta",
    "PSIQUIATRIA PEDIATRICA Y DE LA ADOLESCENCI": "Psiquiatría infanto-adolescente",
}


def normalizar_especialidad(texto: str) -> str:
    """Llave de comparación de una especialidad: sin tildes, mayúsculas, sin género final.

    Recorta la terminación de género —`ADULTO`/`ADULTA` a `ADULT`— porque el informe la
    cambia entre trimestres sin cambiar el concepto. No es cosmética: sin esto la serie de
    psiquiatría adulta aparece cortada en 2026 y una nueva empieza de cero.
    """
    s = " ".join(str(texto or "").split()).upper()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(s.split())


def _a_entero(texto: str) -> int | None:
    """`"22.963"` a `22963`. El punto es separador de miles, nunca decimal."""
    t = str(texto or "").strip()
    return int(t.replace(".", "")) if PATRON_REGISTROS.match(t) else None


def extraer_paginas(ruta: Path) -> list[str]:
    """Texto de cada página del PDF. Es el único punto de I/O del módulo.

    Falla con un mensaje que distingue las dos causas posibles —falta la dependencia o el
    PDF es un escaneo— porque llevan a acciones distintas y confundirlas cuesta una tarde.
    """
    try:
        import fitz  # noqa: PLC0415
    except ImportError as exc:
        raise SchemaDriftError(
            "[glosa06] falta PyMuPDF para leer el PDF. Instalar con `pip install "
            "'obsm[pdf]'`. No es un problema del informe."
        ) from exc

    with fitz.open(ruta) as doc:
        paginas = [p.get_text() for p in doc]
    caracteres = sum(len(p.strip()) for p in paginas)
    if caracteres < 2000:
        raise SchemaDriftError(
            f"[glosa06] {Path(ruta).name} tiene {len(paginas)} páginas y solo "
            f"{caracteres} caracteres extraíbles. Probablemente es un escaneo: los "
            f"informes de la Glosa 06 se producen desde Word y sí traen texto. "
            f"Extraerlo con OCR es una decisión distinta y no se toma sola."
        )
    return paginas


def parsear_tabla_especialidades(paginas: list[str]) -> tuple[pd.DataFrame, dict]:
    """Extrae la tabla de registros en espera por especialidad médica.

    Devuelve (tabla, reporte). El reporte declara **en qué página** se encontró la tabla y
    **cuántas especialidades** se leyeron, que es lo que permite notar que un rediseño la
    dejó a medias sin tener que abrir el PDF.

    La tabla en el texto extraído es una secuencia alternada de líneas: nombre de la
    especialidad, luego su número. No se asume el orden de las filas —alfabético en 2025,
    por magnitud en 2026— ni su posición: se recorre desde el encabezado y se toma cada par
    que calce.
    """
    for i, pagina in enumerate(paginas):
        # El encabezado se busca en **una** página, no en la ventana: si se buscara en la
        # ventana, la primera que la contuviera reportaría su propio número y el recorrido
        # empezaría páginas antes de la tabla.
        norm_pagina = [normalizar_especialidad(x) for x in pagina.splitlines() if x.strip()]
        if not any(
            n.startswith(ENCABEZADO_ESPECIALIDAD)
            and any(ENCABEZADO_REGISTROS in m for m in norm_pagina[j : j + 3])
            for j, n in enumerate(norm_pagina)
        ):
            continue

        # **La tabla cruza de página.** En el informe de 2025 el encabezado queda al pie de
        # una página y las especialidades siguen en la siguiente. Parsear solo la página del
        # encabezado devolvía una tabla a medias que igual superaba el mínimo de diez filas,
        # así que pasaba en silencio. Se extiende la ventana y el recorrido se detiene solo
        # al encontrar la fila de total.
        unidas = "\n".join(paginas[i : i + PAGINAS_QUE_PUEDE_CRUZAR])
        lineas = [x.strip() for x in unidas.splitlines() if x.strip()]
        norm = [normalizar_especialidad(x) for x in lineas]
        inicio = next(
            (
                j for j, n in enumerate(norm)
                if n.startswith(ENCABEZADO_ESPECIALIDAD)
                and any(ENCABEZADO_REGISTROS in m for m in norm[j : j + 3])
            ),
            None,
        )
        if inicio is None:
            continue

        filas = []
        j = inicio + 1
        while j < len(lineas) - 1:
            # La fila de total cierra la tabla: lo que viene después es otra cosa.
            if any(norm[j].startswith(p_) for p_ in ("TOTAL", "SUBTOTAL")):
                filas.append({"especialidad_fuente": lineas[j],
                              "registros": _a_entero(lineas[j + 1]) or 0})
                break
            valor = _a_entero(lineas[j + 1])
            nombre_norm = norm[j] if j < len(norm) else ""
            es_mobiliario = any(m in nombre_norm for m in MOBILIARIO_DE_PAGINA)
            if valor is not None and not _a_entero(lineas[j]) and not es_mobiliario:
                filas.append({"especialidad_fuente": lineas[j], "registros": valor})
                j += 2
            else:
                j += 1
        if len(filas) < 10:
            continue

        tabla = pd.DataFrame(filas)
        # La tabla trae su propio total mezclado con el detalle: «Total, CNE Médica»
        # 2.051.482 en el informe de 2025. Sumar sin sacarlo duplica el país entero, que
        # es la trampa de CLAUDE.md §8. Se usa el detector compartido y no un `if` local
        # porque es exactamente para esto que está centralizado.
        marca_total = detectar_filas_total(tabla[["especialidad_fuente"]])
        declarado = tabla.loc[marca_total, "registros"]
        total_declarado = int(declarado.max()) if len(declarado) else None
        tabla = tabla.loc[~marca_total].reset_index(drop=True)

        tabla["especialidad_norm"] = tabla["especialidad_fuente"].map(normalizar_especialidad)
        tabla["etiqueta"] = tabla["especialidad_norm"].map(
            lambda n: next(
                (v for k, v in ESPECIALIDADES_SALUD_MENTAL.items() if n.startswith(k)), ""
            )
        )
        tabla["es_salud_mental"] = tabla["etiqueta"] != ""

        suma_detalle = int(tabla["registros"].sum())
        reporte: dict = {
            "pagina": i + 1,
            "especialidades": len(tabla),
            "suma_detalle": suma_detalle,
            "total_declarado": total_declarado,
            "salud_mental": {
                r.etiqueta: int(r.registros)
                for r in tabla[tabla["es_salud_mental"]].itertuples()
            },
        }
        # El total que el propio informe declara es un ancla gratis: si la suma del
        # detalle no lo alcanza, faltan filas —la tabla cruza de página y solo se leyó
        # una— o sobran. Se reporta la diferencia en vez de esconderla.
        if total_declarado:
            reporte["diferencia_con_total"] = suma_detalle - total_declarado
            if abs(suma_detalle - total_declarado) > 0.005 * total_declarado:
                log.warning(
                    "[glosa06] la suma del detalle (%s) no cuadra con el total declarado "
                    "(%s). Suele significar que la tabla cruza de página y solo se leyó "
                    "una parte.", f"{suma_detalle:,}", f"{total_declarado:,}",
                )

        faltan = set(ESPECIALIDADES_SALUD_MENTAL.values()) - set(reporte["salud_mental"])
        if faltan:
            # No se aborta: la tabla puede ser útil igual y el informe podría haber
            # renombrado la especialidad. Pero tiene que verse, porque una serie de
            # psiquiatría que calla es peor que una que falta.
            log.warning(
                "[glosa06] la tabla de la página %d no trae %s. Si el informe renombró la "
                "especialidad, agregarla a ESPECIALIDADES_SALUD_MENTAL con su test.",
                i + 1, sorted(faltan),
            )
        reporte["salud_mental_faltante"] = sorted(faltan)
        return tabla, reporte

    raise SchemaDriftError(
        f"[glosa06] no se encontró la tabla de especialidades en las {len(paginas)} "
        f"páginas. Se busca un encabezado {ENCABEZADO_ESPECIALIDAD!r} seguido de "
        f"{ENCABEZADO_REGISTROS!r} y al menos diez pares especialidad/número.\n"
        f"El informe probablemente se rediseñó. Revisar el PDF y actualizar el parser con "
        f"un fixture del formato nuevo: NO relajar la búsqueda hasta que pase."
    )


#: El trimestre, escrito de las dos formas que usan los informes. El valor es el mes de
#: **cierre** del trimestre, porque el corte de la lista es el último día: «III trimestre
#: 2025» son los datos al 30 de septiembre.
TRIMESTRES = {
    "I": "03", "II": "06", "III": "09", "IV": "12",
    "PRIMER": "03", "SEGUNDO": "06", "TERCER": "09", "CUARTO": "12",
}

#: Las dos formas observadas en dos informes consecutivos: romanos («III trimestre 2025») y
#: ordinales en palabra («primer trimestre de 2026»). Ninguna es estable, así que se
#: aceptan ambas y un tercer formato tiene que fallar, no adivinarse.
PATRONES_PERIODO = (
    re.compile(r"\b(I{1,3}|IV)\s+trimestre\s+(?:de[l]?\s+)?(\d{4})\b", re.I),
    re.compile(r"\b(primer|segundo|tercer|cuarto)\s+trimestre\s+(?:de[l]?\s+)?(\d{4})\b", re.I),
)


def periodo_del_informe(paginas: list[str]) -> str:
    """Trimestre del informe en ISO, con el mes de cierre: `"2025-09"`.

    Se lee del contenido y no del nombre del archivo. Los nombres publicados son
    `1764018133827_Glosa-06-LE-III-trimestre-2025.pdf` y
    `Glosa-06-letra-a-b-c-i-j-k-comun-a-la-partida-1er-trimestre-1.pdf`: no comparten
    patrón, uno lleva prefijo de trece dígitos y el otro no dice el año. El contenido sí.
    """
    texto = " ".join(" ".join(p.split()) for p in paginas[:4])
    for patron in PATRONES_PERIODO:
        m = patron.search(texto)
        if m:
            mes = TRIMESTRES[m.group(1).upper()]
            return f"{m.group(2)}-{mes}"
    raise SchemaDriftError(
        "[glosa06] no se pudo leer el trimestre del informe. Se buscan las dos formas "
        "observadas —romanos («III trimestre 2025») y ordinales («primer trimestre de "
        "2026»)— en las primeras páginas. Un formato nuevo hay que agregarlo con su test: "
        "deducir el período del nombre del archivo no sirve, porque los nombres "
        "publicados no comparten patrón."
    )


class Glosa06(Ingestor):
    """Ingestor del informe trimestral. Una fila por especialidad, con su trimestre."""

    source_id = "glosa06"
    columnas_requeridas = ("periodo", "especialidad_fuente", "especialidad_norm", "registros")
    columnas_opcionales = ("etiqueta", "es_salud_mental")

    def _leer(self, ruta: Path) -> pd.DataFrame:
        paginas = extraer_paginas(Path(ruta))
        tabla, reporte = parsear_tabla_especialidades(paginas)
        tabla.insert(0, "periodo", periodo_del_informe(paginas))
        tabla.attrs["reporte_parseo"] = reporte
        return tabla

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["registros"] = pd.to_numeric(out["registros"], errors="coerce").astype("Int64")
        rep = df.attrs.get("reporte_parseo", {})
        dif = rep.get("diferencia_con_total")
        if dif:
            log.warning(
                "[%s] %s: el detalle difiere del total declarado en %+d registros (%.2f %%). "
                "Ver A-018.", self.source_id, out["periodo"].iloc[0], dif,
                100 * abs(dif) / max(rep.get("total_declarado") or 1, 1),
            )
        out.attrs["reporte_parseo"] = rep
        return out
