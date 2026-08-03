"""Ingestor de egresos hospitalarios DEIS.

Estado: **verificado contra la fuente real** el 2026-08-02, sobre los archivos anuales
`EGRESOS_<anio>.zip` de `repositoriodeis.minsal.cl`. Se abrieron y contaron por completo
2001, 2010, 2015, 2019, 2021, 2023 y 2024; los años 2001–2024 responden en el servidor.

La URL no está enlazada en el índice de `deis.minsal.cl` de forma raspable: ese índice es
un Ninja Tables que se arma por AJAX. El patrón se recuperó del índice CDX de Wayback y
**después** se comprobó contra el servidor real, uno por uno.

Un egreso **no es una persona**: los reingresos cuentan varias veces. No sirve como
prevalencia y `transform/` no debe tratarlo como tal.

Trampas de esta fuente, todas verificadas sobre los archivos completos:

1. **La lesión autoinfligida NO está en `DIAG1`, está en `DIAG2`.** Es exactamente la
   misma trampa que en `deis_defunciones` (A-004), y se repite acá sin cambios. En 2023,
   sobre 1.612.267 egresos: X60–X84 aparece **0 veces** en `DIAG1` y **7.683** en `DIAG2`;
   los códigos F00–F99 aparecen **37.773** veces en `DIAG1` y **0** en `DIAG2`. Un
   agrupador aplicado solo a `DIAG1` devuelve cero intentos suicidas sin lanzar error.
   Por eso `causa_cie10` se **deriva**: manda la causa externa cuando existe y el
   diagnóstico principal cuando no. Verificado que ambos universos son **disjuntos** en
   2023 —ninguna de las 37.773 filas con F en `DIAG1` trae `DIAG2`—, así que la derivación
   no esconde egresos psiquiátricos. `origen_causa_cie10` deja el rastro para auditarlo.
2. **`*` es supresión aplicada por el propio DEIS, no un dato faltante.** En 2023 son
   128.108 filas (7,9 %) con **doce** columnas enmascaradas a la vez; el subconjunto
   cambia entre entregas (trampa 8). Lo único que sobrevive siempre es el núcleo clínico:
   `DIAG1`, `DIAG2` y `DIAS_ESTADA`. Consecuencias: desde 2023 los totales comunales **no
   suman** el total nacional, y —peor— **`ANO_EGRESO` también viene enmascarado**, en los
   seis años que tienen supresión. Sin eso, un `groupby("anio")` descarta el 8 % de 2023
   en silencio. Como cada archivo es de un solo año el año se imputa, pero declarándolo en
   `anio_imputado`; con más de un año en el archivo se deja nulo. Ver A-022.
3. **El esquema cambia de año en año: 15, 16 o 18 columnas.** 2001–2019 traen 18
   (con `INTERV_Q` y `PROCED`), 2021 trae 15 (sin `ETNIA`), 2023–2024 traen 16. Además el
   nombre de la primera columna viene **truncado** desde 2019: `..._SALU`, sin la D. Por
   eso las columnas que varían son opcionales y no requeridas: la ingesta de un año no
   puede fallar porque otro año tenga una columna más.
4. **2021 está publicado con otro codebook completo.** `SEXO` viene numérico (`1`,`2`,
   `3`,`9`) en vez de texto, y `GRUPO_EDAD` trae **22 tramos quinquenales**
   (`1 A 4 AÑOS`, `85 A MAS`) contra los **12 decenales** (`1 a 9`, `90 y más`) de todos
   los demás años. No es cosmético: **una serie por tramo etario que incluya 2021 está
   comparando cortes distintos.** El tope tampoco calza —quinquenal cierra en `85 y más`
   y decenal en `90 y más`—, así que ni siquiera colapsando se recuperan los dos tramos
   superiores. El ingestor clasifica el esquema en `esquema_grupo_edad` y deja la decisión
   a `transform/`. Ver A-023.
5. **El archivo 2024 viene con los acentos destruidos en origen.** Es UTF-8 válido, pero
   contiene 1.199.605 caracteres U+FFFD: DEIS lo convirtió desde latin-1 con reemplazo y
   la información se perdió. `Ñuñoa` llega como `�u�oa` y `Concepción` como
   `Concepci�n`. **No se puede reparar**: no hay forma de saber qué letra había.
   No es un problema de detección de encoding y no debe «arreglarse» probando codecs.
   Solo afecta glosas; `COMUNA_RESIDENCIA` (`08101`) está intacto, que es exactamente por
   lo que la llave territorial del proyecto es el CUT y nunca el nombre. Ver A-021.
6. **`DIAS_ESTADA` se llama `DIAS_ESTAD` en el diccionario** que viene dentro del mismo
   ZIP. Igual que en defunciones, el diccionario sirve para la semántica y no para mapear
   nombres. Se toleran las dos grafías.
7. **`COMUNA_RESIDENCIA` sí trae el cero a la izquierda** (`01101`), a diferencia de
   `deis_defunciones`. Se pasa igual por `territorio.formatear_cut_comuna` en `transform/`:
   depender de que un año siga trayéndolo es cómo se rompe el join el año que no lo traiga.
8. **Qué columnas enmascara el `*` cambió en el camino:** 13 en 2001, 10 entre 2010 y
   2019, 12 desde 2023. Hasta 2019 **deja la comuna intacta** y enmascara la región, que
   es supresión inefectiva: los dos primeros dígitos del CUT comunal *son* la región, así
   que el campo oculto se reconstruye trivialmente desde uno visible. El proyecto no lo
   explota, solo lo registra. El ingestor no puede exigir un conjunto fijo sin dejar
   afuera media serie, así que declara **el complemento** —las tres columnas que nunca se
   enmascaran— y exige **coherencia interna**: un solo patrón por archivo.
9. **Hay tres centinelas de territorio y significan cosas distintas.** Además del `*` de
   supresión están `99999` / `Ignorada` —residencia desconocida, 4.830 a 18.257 filas según
   el año— y `88888` / `Extranjero` —la persona no reside en Chile, 661 filas en 2023—.
   Los tres van a nulo, pero se marcan **por separado** (`suprimido_en_origen`,
   `residencia_ignorada`, `residencia_extranjero`): agregarlos produce comunas «99999» y
   «88888» que no existen, y mezclarlos entre sí borra que un egreso de extranjero **sí**
   tiene residencia conocida, solo que fuera del país. Sumados explican exactamente las
   141.033 filas sin territorio de 2023.
10. **El archivo de 2015 ya trae región 16 (Ñuble)**, creada en 2018: DEIS re-codificó
    hacia atrás. Es lo contrario de lo que advierte CLAUDE.md §5 para series históricas,
    donde esas comunas aparecen bajo 08. No se parcha acá: el join va por CUT comunal, que
    es estable, y `territorio.py` resuelve las vigencias.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..errors import SchemaDriftError
from ..io import detectar_separador, leer_primera_linea
from .base import Ingestor, renombrar_columnas

log = logging.getLogger(__name__)

#: Mapeo {nombre_en_la_fuente: nombre_canonico}. La coincidencia es laxa (sin tildes ni
#: mayúsculas), así que basta una grafía por variante real. Los marcados «real» se leyeron
#: de archivos publicados; se indica en qué años aparece cada uno.
MAPA_COLUMNAS = {
    # La D final se cae desde 2019. Ambas grafías son reales.
    "PERTENENCIA_ESTABLECIMIENTO_SALUD": "pertenencia_snss",  # real 2001-2015, 2021
    "PERTENENCIA_ESTABLECIMIENTO_SALU": "pertenencia_snss",  # real 2019, 2023, 2024
    "SEXO": "sexo_fuente",  # real; `_posproceso` deriva `sexo`
    "GRUPO_EDAD": "grupo_edad",  # real
    "ETNIA": "etnia",  # real salvo 2021
    "GLOSA_PAIS_ORIGEN": "pais_origen",  # real
    "COMUNA_RESIDENCIA": "comuna_cut_fuente",  # real: es comuna de RESIDENCIA
    "GLOSA_COMUNA_RESIDENCIA": "comuna_nombre",  # real
    "REGION_RESIDENCIA": "region_cut_fuente",  # real
    "GLOSA_REGION_RESIDENCIA": "region_nombre",  # real
    "PREVISION": "prevision_codigo",  # real
    "GLOSA_PREVISION": "prevision",  # real
    "ANO_EGRESO": "anio",  # real
    "AÑO_EGRESO": "anio",  # variante tolerada
    "DIAG1": "diagnostico_principal",  # real: diagnóstico principal (acá viven los F)
    "DIAG2": "causa_externa",  # real: causa externa (acá vive la lesión autoinfligida)
    "DIAS_ESTADA": "dias_estada",  # real
    "DIAS_ESTAD": "dias_estada",  # así lo llama el diccionario del propio ZIP
    "CONDICION_EGRESO": "condicion_egreso_codigo",  # real
    "INTERV_Q": "intervencion_quirurgica",  # real 2001-2019, ausente después
    "PROCED": "procedencia",  # real 2001-2019, ausente después
}

#: Centinela con el que DEIS enmascara la demografía de una fila completa. **No es un
#: dato faltante**: es supresión de origen, y viaja marcada en `suprimido_en_origen`.
CENTINELA_SUPRIMIDO = "*"

#: Columnas que el centinela **nunca** enmascara, verificado en los siete años: el núcleo
#: clínico del egreso. Todo lo demás sí puede caer, y qué exactamente cambia entre entregas
#: (trampa 8), así que el patrón lo define el archivo y no esta lista. Declarar el
#: complemento —lo que se conserva— es más estable que enumerar lo que se pierde: es la
#: parte que DEIS mantiene precisamente porque es la razón de ser del registro.
COLUMNAS_NUNCA_ENMASCARADAS = (
    "diagnostico_principal",
    "causa_externa",
    "dias_estada",
)

#: Código de residencia desconocida, glosado `Ignorada`. **No es supresión**: DEIS no sabe
#: dónde vive la persona. Presente en los seis años revisados, entre 4.830 y 18.257 filas.
#: Dejarlo pasar crea una comuna «99999» en cualquier agregación territorial.
COMUNA_IGNORADA = "99999"
REGION_IGNORADA = "99"

#: Residencia en el extranjero, glosada `Extranjero`. **Es un tercer significado distinto**
#: de los otros dos: no es que DEIS lo ocultara ni que no se sepa, es que la persona no
#: reside en Chile. 661 filas en 2023. Contarla en cualquier comuna chilena es un error, y
#: mezclarla con «ignorada» borra que el egreso sí tiene un dato de residencia conocido.
COMUNA_EXTRANJERO = "88888"
REGION_EXTRANJERO = "88"

#: `CONDICION_EGRESO` según el diccionario que viene dentro del ZIP: «1=Vivo 2=Fallecido».
CONDICION_EGRESO = {"1": "vivo", "2": "fallecido"}

#: Valores textuales reales de `SEXO` (2001-2019, 2023, 2024). El `(INDETERMINDADO)` con
#: la errata está tal cual en el archivo de 2015; se respeta la fuente.
MAPA_SEXO_TEXTO = {
    "HOMBRE": "hombre",
    "MUJER": "mujer",
    "DESCONOCIDO": "desconocido",
    "INTERSEX (INDETERMINDADO)": "intersex",
    "INTERSEX (INDETERMINADO)": "intersex",
}

#: Valores numéricos reales de `SEXO`, presentes **solo en 2021**. `1` y `2` siguen la
#: codificación estándar de DEIS, la misma que `deis_defunciones`. `3` (49 filas) y `9`
#: (4 filas) NO tienen codebook publicado para egresos: por la coincidencia con las
#: categorías textuales de 2015 se **sospecha** intersex y desconocido, pero eso no está
#: verificado y CLAUDE.md §2.1 prohíbe inventar códigos. Van a `no_especificado` y el
#: valor crudo se conserva íntegro en `sexo_fuente`.
MAPA_SEXO_NUMERICO = {"1": "hombre", "2": "mujer", "3": "no_especificado", "9": "no_especificado"}

_RE_ENTEROS = re.compile(r"\d+")


def normalizar_grupo_edad(texto: object) -> str:
    """Devuelve un token canónico del tramo etario, o `""` si está suprimido.

    Se apoya en los **números** del texto y en la palabra `menor`, nunca en las letras
    acentuadas: el archivo de 2024 llega con los acentos ya destruidos por DEIS
    (`90 y m�s`, `menor de un a�o`) y ningún codec los recupera. `menor`, `y`
    y los dígitos no llevan tilde, así que sobreviven intactos.

    >>> normalizar_grupo_edad("1 a 9")
    '1_a_9'
    >>> normalizar_grupo_edad("90 y m�s")
    '90_y_mas'
    >>> normalizar_grupo_edad("menor de un a�o")
    'menor_de_1_anio'
    >>> normalizar_grupo_edad("85 A MAS")
    '85_y_mas'
    """
    # `normalizar_texto` quita las tildes: sin eso, "dia" no es subcadena de "días"
    # —d-í-a-s no contiene d-i-a— y el tramo "menor a 7 días" se clasificaría como
    # un tramo abierto "7 y más". Las palabras clave que quedan (`menor`, `dia`, `mes`)
    # no llevan tilde, así que también sobreviven al daño del archivo de 2024.
    from ..territorio import normalizar_texto

    s = normalizar_texto(str(texto))
    if not s or s in (CENTINELA_SUPRIMIDO, "nan"):
        return ""

    n = [int(x) for x in _RE_ENTEROS.findall(s)]
    menor, dias, meses = "menor" in s, "dia" in s, "mes" in s

    if menor:
        # "menor de un año" (decenal, sin números) y "menor a 7 días" (quinquenal).
        token = f"menor_a_{n[0]}_dias" if dias and n else "menor_de_1_anio"
    elif len(n) == 2:
        a, b = n
        if dias and meses:
            token = f"{a}_dias_a_{b}_meses"  # "28 DIAS A 2 MES"
        elif dias:
            token = f"{a}_a_{b}_dias"  # "7 A 27 DIAS"
        elif meses:
            token = f"{a}_meses_a_{b}_anio"  # "2 MESES A MENOS DE 1 AÑO"
        else:
            token = f"{a}_a_{b}"  # "1 a 9", "1 A 4 AÑOS"
    elif len(n) == 1:
        # Un solo número es siempre el tramo superior abierto: "90 y más", "85 A MAS".
        token = f"{n[0]}_y_mas"
    else:
        token = ""
    return token


#: Los 12 tramos decenales (2001-2019, 2023, 2024) y los 22 quinquenales (solo 2021),
#: ya en forma canónica. Sirven para clasificar el esquema del archivo, no para colapsarlo:
#: colapsar es decisión de `transform/`, y arriba de 79 años **no se puede** colapsar sin
#: perder los dos tramos superiores.
#: Ojo con el primero: el tramo decenal inferior es `1 a 9`, no `1 a 10`, y desde ahí
#: los cortes van de 10 en 10 (`10 a 19` … `80 a 89`).
TRAMOS_DECENALES = frozenset(
    {"menor_de_1_anio", "1_a_9", "90_y_mas"} | {f"{i}_a_{i + 9}" for i in range(10, 90, 10)}
)
TRAMOS_QUINQUENALES = frozenset(
    {
        "menor_a_7_dias",
        "7_a_27_dias",
        "28_dias_a_2_meses",
        "2_meses_a_1_anio",
        "1_a_4",
        "85_y_mas",
    }
    | {f"{i}_a_{i + 4}" for i in range(5, 85, 5)}
)


def clasificar_esquema_edad(tramos: set[str]) -> str:
    """Devuelve 'decenal', 'quinquenal' o 'mixto' según los tramos presentes.

    Un archivo `mixto` es un cambio de esquema real y no una curiosidad: significa que
    dos cortes etarios incompatibles conviven en la misma entrega.
    """
    presentes = {t for t in tramos if t}
    if not presentes:
        return "desconocido"
    en_dec = presentes <= TRAMOS_DECENALES
    en_qui = presentes <= TRAMOS_QUINQUENALES
    if en_dec and not en_qui:
        return "decenal"
    if en_qui and not en_dec:
        return "quinquenal"
    if en_dec and en_qui:
        # Los dos conjuntos comparten "1_a_9"/"5_a_9"; con un solo tramo puede pasar.
        return "decenal" if presentes <= TRAMOS_DECENALES else "quinquenal"
    return "mixto"


def _limpiar_codigo(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip().str.upper().str.replace(".", "", regex=False)


class DeisEgresos(Ingestor):
    source_id = "deis_egresos"
    columnas_requeridas = (
        "anio",
        "sexo_fuente",
        "grupo_edad",
        "comuna_cut_fuente",
        "diagnostico_principal",
        "dias_estada",
        "condicion_egreso_codigo",
    )
    # Varían entre 15, 16 y 18 columnas según el año (trampa 3 del docstring). Su ausencia
    # se registra y no falla: si fueran requeridas, 2021 no se podría ingerir.
    columnas_opcionales = (
        "causa_externa",
        "comuna_nombre",
        "etnia",
        "intervencion_quirurgica",
        "pais_origen",
        "pertenencia_snss",
        "prevision",
        "prevision_codigo",
        "procedencia",
        "region_cut_fuente",
        "region_nombre",
    )

    def _leer(self, ruta: Path) -> pd.DataFrame:
        # Solo el encabezado: el CSV real pesa entre 220 y 290 MB y acá únicamente se
        # necesita la primera línea para decidir el separador.
        primera, encoding = leer_primera_linea(ruta)
        sep = detectar_separador(primera)
        df = pd.read_csv(ruta, sep=sep, encoding=encoding, dtype=str, low_memory=False)
        df.attrs["encoding"] = encoding
        df.attrs["separador"] = sep
        df = renombrar_columnas(df, MAPA_COLUMNAS)

        # Dos columnas de origen mapeadas al mismo destino producirían dos columnas
        # homónimas, y a partir de ahí `df["anio"]` devuelve un DataFrame en vez de una
        # Serie: el error aparecería mucho más tarde y en otro lugar.
        duplicadas = sorted({c for c in df.columns if list(df.columns).count(c) > 1})
        if duplicadas:
            raise SchemaDriftError(
                f"[{self.source_id}] el archivo trae varias columnas que mapean al mismo "
                f"destino: {duplicadas}. Revisar MAPA_COLUMNAS contra este archivo antes "
                f"de continuar; no elegir una en silencio."
            )
        return df

    def _posproceso(self, df: pd.DataFrame) -> pd.DataFrame:
        # El orden importa: la supresión se detecta antes de cualquier coerción (el `*` es
        # la única pista y un `to_numeric` la borra), y el año se imputa después, porque
        # depende de saber qué filas venían enmascaradas.
        out = df.copy()
        out = self._marcar_supresion(out)
        out = self._marcar_residencia_ignorada(out)
        out = self._normalizar_anio_y_estada(out)
        out = self._derivar_causa(out)
        out = self._normalizar_sexo(out)
        out = self._clasificar_tramo_etario(out)
        return self._normalizar_condicion_egreso(out)

    def _marcar_supresion(self, out: pd.DataFrame) -> pd.DataFrame:
        """Marca `suprimido_en_origen` y anula el centinela. Ver trampas 2 y 8."""
        # Solo columnas que vinieron de la fuente: son las únicas que pueden traer su
        # centinela. Recorrer `out.columns` entero arrasaba con `_es_fila_total`, que la
        # clase base agrega antes del posproceso: quedaba convertida al **string**
        # `"False"`, y `bool("False")` es `True`, así que `silver` descartaba las filas
        # creyéndolas totales y la tabla salía vacía sin un solo error.
        del_origen = dict.fromkeys(MAPA_COLUMNAS.values())
        presentes = [
            c for c in del_origen if c in out.columns and c not in COLUMNAS_NUNCA_ENMASCARADAS
        ]
        marcas = pd.DataFrame(
            {c: out[c].astype(str).str.strip() == CENTINELA_SUPRIMIDO for c in presentes},
            index=out.index,
        )
        afectadas = marcas.any(axis=1) if presentes else pd.Series(False, index=out.index)
        out["suprimido_en_origen"] = afectadas

        # El conjunto de columnas enmascaradas **cambia entre años** (trampa 8), así que no
        # se exige uno fijo. Lo que sí se exige es que dentro de un mismo archivo sea
        # siempre el mismo: si dos filas vienen enmascaradas de forma distinta, la
        # supresión dejó de ser describible con un booleano y hay que mirarla de nuevo.
        if afectadas.any():
            patrones = np.unique(marcas.to_numpy()[afectadas.to_numpy()], axis=0)
            if len(patrones) > 1:
                combinaciones = [
                    sorted(c for c, m in zip(presentes, p, strict=True) if m) for p in patrones
                ]
                raise SchemaDriftError(
                    f"[{self.source_id}] el centinela '{CENTINELA_SUPRIMIDO}' enmascara "
                    f"{len(patrones)} combinaciones distintas de columnas en el mismo "
                    f"archivo: {combinaciones[:4]}. Hasta ahora cada entrega usaba una "
                    f"sola; revisar el archivo antes de seguir, no marcar la fila a medias."
                )
            enmascaradas = sorted(c for c, m in zip(presentes, patrones[0], strict=True) if m)
            log.info(
                "[%s] %d filas suprimidas en origen; columnas enmascaradas: %s",
                self.source_id,
                int(afectadas.sum()),
                enmascaradas,
            )
            # El núcleo clínico tiene que sobrevivir: si dejara de hacerlo, la fila
            # suprimida ya no aporta ni siquiera al total nacional por diagnóstico, que es
            # lo único que hoy la mantiene utilizable.
            perdidas = [
                c
                for c in COLUMNAS_NUNCA_ENMASCARADAS
                if c in out.columns
                and (out.loc[afectadas, c].astype(str).str.strip() == CENTINELA_SUPRIMIDO).any()
            ]
            if perdidas:
                raise SchemaDriftError(
                    f"[{self.source_id}] la supresión alcanzó al núcleo clínico {perdidas}, "
                    f"que en los siete años verificados nunca se enmascara. Si la fuente "
                    f"empezó a suprimir el diagnóstico, las filas suprimidas dejan de servir "
                    f"incluso para el total país: revisar antes de seguir."
                )
        # El centinela pasa a nulo para que ninguna comuna `"*"` llegue al join territorial.
        for c in presentes:
            out[c] = out[c].astype(str).str.strip().replace(CENTINELA_SUPRIMIDO, pd.NA)
        return out

    def _marcar_residencia_ignorada(self, out: pd.DataFrame) -> pd.DataFrame:
        """Anula `99999` / `Ignorada`, que es un centinela distinto de la supresión.

        Significa que no se sabe dónde vive la persona, no que DEIS lo ocultara. Está en
        todos los años (4.830 a 18.257 filas). Sin esto aparece una comuna «99999» que no
        existe en cualquier agregación territorial. Ver trampa 9.
        """
        ignorada = pd.Series(False, index=out.index)
        extranjero = pd.Series(False, index=out.index)
        if "comuna_cut_fuente" in out.columns:
            cod = out["comuna_cut_fuente"].astype(str).str.strip()
            ignorada = cod == COMUNA_IGNORADA
            extranjero = cod == COMUNA_EXTRANJERO
            out.loc[ignorada | extranjero, "comuna_cut_fuente"] = pd.NA
        if "region_cut_fuente" in out.columns:
            reg = out["region_cut_fuente"].astype(str).str.strip()
            out.loc[reg.isin((REGION_IGNORADA, REGION_EXTRANJERO)), "region_cut_fuente"] = pd.NA
        out["residencia_ignorada"] = ignorada
        out["residencia_extranjero"] = extranjero
        return out

    def _normalizar_anio_y_estada(self, out: pd.DataFrame) -> pd.DataFrame:
        """Tipa año y días de estada, e imputa el año que la supresión se llevó.

        `ANO_EGRESO` viene enmascarado en las filas suprimidas de los seis años que tienen
        supresión, sin excepción: eso deja sin `anio` al 8 % de los egresos de 2023, y un
        `groupby("anio")` los descartaría en silencio. Como cada archivo publicado es de un
        solo año el dato es recuperable con certeza, pero se **imputa declarándolo** en
        `anio_imputado`, nunca como si viniera leído. Ver A-022.

        `dias_estada` no trae decimales en ninguno de los siete años revisados.
        """
        out["anio"] = pd.to_numeric(out["anio"], errors="coerce").astype("Int64")
        out["dias_estada"] = pd.to_numeric(out["dias_estada"], errors="coerce").astype("Int64")
        out["anio_imputado"] = False
        anios = set(out.loc[out["anio"].notna(), "anio"].unique())
        if out["anio"].isna().any():
            if len(anios) == 1:
                unico = next(iter(anios))
                faltantes = out["anio"].isna()
                out.loc[faltantes, "anio"] = unico
                out.loc[faltantes, "anio_imputado"] = True
                log.info(
                    "[%s] %d filas sin ANO_EGRESO (suprimido en origen); imputado %s, "
                    "el único año del archivo",
                    self.source_id,
                    int(faltantes.sum()),
                    unico,
                )
            else:
                # Con más de un año en el archivo la imputación sería una invención.
                log.warning(
                    "[%s] %d filas sin ANO_EGRESO y el archivo tiene %d años distintos "
                    "(%s): quedan nulas, porque imputar acá sería inventar el período",
                    self.source_id,
                    int(out["anio"].isna().sum()),
                    len(anios),
                    sorted(anios)[:5],
                )
        return out

    def _derivar_causa(self, out: pd.DataFrame) -> pd.DataFrame:
        """Deriva `causa_cie10`: la externa manda cuando existe. Ver trampa 1.

        El diagnóstico principal queda igual en su propia columna, así que no se pierde
        nada, y `origen_causa_cie10` deja el rastro para auditar la derivación.
        """
        out["diagnostico_principal"] = _limpiar_codigo(out["diagnostico_principal"])
        if "causa_externa" in out.columns:
            out["causa_externa"] = _limpiar_codigo(out["causa_externa"])
        else:
            out["causa_externa"] = ""
        externa = out["causa_externa"]
        out["causa_cie10"] = externa.where(externa != "", out["diagnostico_principal"])
        out["origen_causa_cie10"] = (externa != "").map({True: "externa", False: "principal"})
        return out

    def _normalizar_sexo(self, out: pd.DataFrame) -> pd.DataFrame:
        """Unifica el sexo: texto en casi todos los años, numérico solo en 2021 (trampa 4)."""
        crudo = out["sexo_fuente"].fillna("").astype(str).str.strip().str.upper()
        mapeado = crudo.map(MAPA_SEXO_TEXTO).fillna(crudo.map(MAPA_SEXO_NUMERICO))
        desconocidos = sorted(set(crudo[mapeado.isna() & crudo.ne("")]))
        if desconocidos:
            raise SchemaDriftError(
                f"[{self.source_id}] valores de SEXO no reconocidos: {desconocidos[:10]}. "
                f"Conocidos: {sorted(MAPA_SEXO_TEXTO)} y {sorted(MAPA_SEXO_NUMERICO)}. "
                f"Mapearlos a 'desconocido' en silencio inventa una categoría: verificar "
                f"contra el archivo y agregar el valor con su test."
            )
        # Las filas suprimidas quedan nulas, no "desconocido": `DESCONOCIDO` es una
        # categoría que la fuente sí usa (2015), y confundirlas mezclaría un dato que DEIS
        # no tiene con uno que tiene y decidió no publicar.
        out["sexo"] = mapeado
        return out

    def _clasificar_tramo_etario(self, out: pd.DataFrame) -> pd.DataFrame:
        """Clasifica el esquema etario del archivo. **No colapsa**: eso es de `transform/`,
        y arriba de 79 años ni siquiera es posible. Ver trampa 4 y A-023."""
        out["grupo_edad_norm"] = out["grupo_edad"].map(normalizar_grupo_edad)
        sin_norma = sorted(
            {
                str(v)
                for v, n in zip(out["grupo_edad"], out["grupo_edad_norm"], strict=True)
                if not n and pd.notna(v)
            }
        )
        if sin_norma:
            raise SchemaDriftError(
                f"[{self.source_id}] tramos de GRUPO_EDAD no reconocidos: {sin_norma[:10]}. "
                f"Un tramo nuevo cambia el corte etario de toda la serie: agregarlo a "
                f"TRAMOS_DECENALES o TRAMOS_QUINQUENALES con su test, no ignorarlo."
            )
        esquema = clasificar_esquema_edad(set(out["grupo_edad_norm"]))
        out["esquema_grupo_edad"] = esquema
        if esquema == "mixto":
            log.warning(
                "[%s] el archivo mezcla tramos decenales y quinquenales; una serie por "
                "edad sobre esta entrega compara cortes distintos",
                self.source_id,
            )
        return out

    def _normalizar_condicion_egreso(self, out: pd.DataFrame) -> pd.DataFrame:
        """Traduce la condición al egreso según el diccionario del propio ZIP.

        En 2001 esta columna también viene enmascarada, así que ahí queda nula:
        «suprimida» y «desconocida» no son lo mismo y no se colapsan en una categoría.
        """
        cod = out["condicion_egreso_codigo"].fillna("").astype(str).str.strip()
        out["condicion_egreso"] = cod.map(CONDICION_EGRESO)
        codigos_raros = sorted(set(cod[out["condicion_egreso"].isna() & cod.ne("")]))
        if codigos_raros:
            raise SchemaDriftError(
                f"[{self.source_id}] códigos de CONDICION_EGRESO no reconocidos: "
                f"{codigos_raros[:10]}. El diccionario del ZIP declara «1=Vivo 2=Fallecido»; "
                f"un tercer código cambia la definición de letalidad de toda la serie."
            )
        return out
