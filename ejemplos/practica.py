"""Cancha de práctica de `obsm`. Para jugar, romper cosas y ver qué pasa.

Este archivo no es parte del pipeline: no escribe nada en `data/` y no se usa en
producción. Existe para entender la herramienta tocándola.

CÓMO SE USA
-----------
    python ejemplos/practica.py          # corre las ocho secciones seguidas
    python ejemplos/practica.py 3        # corre solo la sección 3
    python ejemplos/practica.py 3 5 7    # corre varias

Todo funciona con los fixtures de `tests/`, así que **no hace falta haber
descargado nada**. Si además tienes datos reales en `data/`, la sección 7 los
detecta y los usa; si no, lo dice y sigue.

CÓMO ESTÁ ORGANIZADO EL PROYECTO (lo mínimo para orientarse)
------------------------------------------------------------
Los datos recorren cuatro capas y cada una tiene permitido hacer cosas distintas.
Esa separación es lo que hace testeable el proyecto, y romperla es la forma más
común de meter un error difícil de encontrar:

    archivo público
        │   ingest/      descarga, lee, renombra columnas, tipa
        ▼               (NO resuelve comunas, NO clasifica, NO calcula)
    bronze              tabla legible, todavía cruda
        │   transform/silver   normaliza territorio, edad y CIE-10
        ▼
    silver              grilla canónica: comuna_cut x período x dimensiones
        │   transform/gold     une denominadores, calcula tasas, suprime
        ▼
    gold                indicadores publicables + procedencia

La regla que más se nota al usarlo: `transform/` e `indicators/` son **funciones
puras**. Entra un DataFrame, sale un DataFrame, sin tocar disco ni red. Por eso
casi todo lo de este archivo corre en menos de un segundo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "tests" / "fixtures"
MUESTRA_DEFUNCIONES = FIXTURES / "deis_defunciones" / "muestra_latin1.csv"
#: La estructura tal como la publica DEIS, con DIAG1/DIAG2 y COD_COMUNA.
MUESTRA_ESTRUCTURA_REAL = FIXTURES / "deis_defunciones" / "muestra_estructura_real.csv"
MUESTRA_POBLACION = FIXTURES / "ine_proyecciones" / "muestra_cadena.csv"


def titulo(n: int, texto: str) -> None:
    print(f"\n{'=' * 78}\n  {n}. {texto}\n{'=' * 78}")


def sub(texto: str) -> None:
    print(f"\n--- {texto}")


# =====================================================================================
# 1. TERRITORIO
# =====================================================================================

def seccion_1() -> None:
    """El corazón del proyecto. Casi todos los errores territoriales nacen acá.

    La llave canónica es `comuna_cut`: **cinco dígitos, string, con el cero a la
    izquierda**. Nunca el nombre, nunca un entero.
    """
    titulo(1, "Territorio: por qué el CUT es un string")

    from obsm.territorio import (
        aplicar_alias,
        cargar_dpa,
        formatear_cut_comuna,
        normalizar_comuna,
        normalizar_texto,
        region_de_comuna,
    )

    sub("El problema del cero a la izquierda")
    print("  Iquique es la comuna 01101. Si alguien la guarda como entero:")
    print(f"    int('01101')            = {int('01101')}   <- se perdió el cero")
    print(f"    formatear_cut_comuna(1101) = {formatear_cut_comuna(1101)!r}   <- recuperado")
    print("  Las fuentes chilenas publican el CUT sin el cero en las regiones 01-09.")
    print("  DEIS y el INE lo hacen los dos. Por eso todo se lee con dtype=str.")

    sub("La región sale del CUT, no de una columna aparte")
    for cut in ("01101", "13101", "16101"):
        print(f"    {cut} -> región {region_de_comuna(cut)}")

    sub("Nombres con más de una grafía oficial")
    print("  El sector público escribe la misma comuna de varias formas. Todas las")
    print("  variantes conocidas viven en `territorio.ALIAS`, nunca resueltas inline:")
    for nombre in ("Coihaique", "COYHAIQUE", "Til Til", "Llay-Llay", "Paiguano"):
        norm = aplicar_alias(normalizar_texto(nombre))
        print(f"    {nombre!r:14} -> normalizado {norm!r}")

    sub("La ambigüedad: la función se niega a adivinar")
    dpa = cargar_dpa()
    ambiguos = dpa.nombres_ambiguos()
    print(f"  Nombres exactamente repetidos en la DPA vigente: "
          f"{ambiguos if ambiguos else 'ninguno'}")
    print("  O sea que hoy el guarda no se dispara. Pero la trampa es real y aparece")
    print("  cuando una fuente escribe el nombre abreviado. Mira estas tres comunas:")
    for c in dpa.comunas:
        if normalizar_texto(c.nombre).startswith("san pedro"):
            print(f"    {c.cut}  {c.nombre}")
    print("\n  Un archivo que dice solo 'San Pedro' puede referirse a cualquiera de las")
    print("  tres. `normalizar_comuna` resolvería al match exacto (13505) y las otras")
    print("  dos quedarían mal asignadas en silencio. Por eso la regla del proyecto es")
    print("  usar SIEMPRE el código y nunca el nombre como llave.")

    sub("Con región, resuelve sin ambigüedad")
    print(f"    normalizar_comuna('Santiago', '13')            = "
          f"{normalizar_comuna('Santiago', '13')!r}")
    print(f"    normalizar_comuna('San Pedro de Atacama', '02') = "
          f"{normalizar_comuna('San Pedro de Atacama', '02')!r}")
    print("\n  Y si el nombre no existe, falla en vez de devolver algo parecido:")
    try:
        normalizar_comuna("Comuna Inventada")
    except Exception as exc:
        print(f"    {type(exc).__name__}: {str(exc)[:100]}")

    print(f"\n  La DPA cargada tiene {len(dpa)} comunas en 16 regiones.")
    print("  PRUEBA TÚ: cambia 'Santiago' por tu comuna. Prueba escribirla mal.")


# =====================================================================================
# 2. CIE-10
# =====================================================================================

def seccion_2() -> None:
    """Los agrupadores traducen códigos de diagnóstico a categorías con nombre."""
    titulo(2, "CIE-10: agrupadores y la trampa que costó un bug entero")

    from obsm.cie10 import AGRUPADORES, clasificar, es_publicable

    sub("Qué agrupadores existen")
    for nombre in AGRUPADORES:
        print(f"    {nombre}")

    sub("Clasificar un código")
    for codigo in ("X700", "F320", "F102", "I219", "Y870", "G300"):
        etiquetas = clasificar(codigo)
        print(f"    {codigo:6} -> {etiquetas if etiquetas else '(ninguno)'}")

    sub("LA TRAMPA (esto es real, se llama A-004 en docs/05-CALIDAD.md)")
    print("  El archivo de defunciones tiene DOS columnas de diagnóstico:")
    print("    DIAG1 = naturaleza de la lesión   -> T71X (asfixia), capítulo XIX")
    print("    DIAG2 = causa externa             -> X704 (suicidio),  capítulo XX")
    print()
    print("  El suicidio vive en DIAG2. En 27 años de datos, X60-X84 aparece:")
    print("       0 veces en DIAG1")
    print("    46.805 veces en DIAG2")
    print()
    print("  Un agrupador aplicado solo a DIAG1 devuelve CERO suicidios y no falla:")
    ag = AGRUPADORES["SUICIDIO"]
    print(f"    AGRUPADORES['SUICIDIO'].contiene('T71X') = {ag.contiene('T71X')}  <- la lesión")
    print(f"    AGRUPADORES['SUICIDIO'].contiene('X704') = {ag.contiene('X704')}  <- la causa")
    print()
    print("  Por eso `causa_cie10` se DERIVA: es la causa externa cuando existe, y")
    print("  la básica cuando no. Moraleja: un cero puede ser un bug silencioso.")

    sub("Política de publicación")
    print("  Publicar el desglose por método de suicidio está prohibido (docs/06).")
    print(f"    es_publicable('SUICIDIO', 'agrupador') = "
          f"{es_publicable('SUICIDIO', 'agrupador')}   <- el total del grupo, sí")
    print(f"    es_publicable('SUICIDIO', 'codigo')    = "
          f"{es_publicable('SUICIDIO', 'codigo')}  <- código a código, NO")
    print("\n  Y un nivel que no existe se DETIENE en vez de autorizar:")
    try:
        es_publicable("SUICIDIO", nivel_detalle="subcodigo")
    except ValueError as exc:
        print(f"    ValueError: {str(exc)[:95]}")
    print("  (este archivo de práctica encontró ese bug: antes devolvía True)")


# =====================================================================================
# 3. LEER ARCHIVOS DEL SECTOR PÚBLICO CHILENO
# =====================================================================================

def seccion_3() -> None:
    """Encoding y números: dos formas de arruinar un dataset antes de empezar."""
    titulo(3, "Leer archivos chilenos sin romperlos")

    from obsm.io import a_numero, detectar_encoding, detectar_separador, leer_primera_linea

    sub("El encoding se detecta, no se supone")
    enc = detectar_encoding(MUESTRA_DEFUNCIONES)
    print(f"    {MUESTRA_DEFUNCIONES.name} -> {enc}")
    print("  Los archivos públicos mezclan UTF-8, Latin-1 y CP1252. Si ves 'Ã±' o")
    print("  'Bio Bio' con caracteres rotos, es encoding, no un nombre distinto.")

    primera, enc = leer_primera_linea(MUESTRA_DEFUNCIONES)
    print(f"\n    separador detectado: {detectar_separador(primera)!r}")
    print(f"    encabezado: {primera[:70]}...")
    print("  `leer_primera_linea` existe porque el archivo real pesa 869 MB y para")
    print("  decidir el separador solo hace falta la primera línea.")

    sub("Números en formato chileno")
    print("  Coma decimal y punto de miles. `a_numero` resuelve la ambigüedad:")
    for texto in ("1.234,5", "1,234.5", "$ 1.500", "12,7%", "1.234.567", "0.005", "s/i"):
        print(f"    {texto!r:14} -> {a_numero(texto)}")
    print()
    print("  OJO con el caso ambiguo: '1.000' se lee como mil, no como uno coma cero.")
    print(f"    a_numero('1.000')             = {a_numero('1.000')}")
    print(f"    a_numero('1.000', decimal='.') = {a_numero('1.000', decimal='.')}")
    print("  Para columnas de tasas hay que pasar `decimal` explícito.")


# =====================================================================================
# 4. INGESTA
# =====================================================================================

def seccion_4() -> None:
    """Un ingestor lee, renombra y tipa. Nada más. Y falla ruidosamente."""
    titulo(4, "Ingesta: de archivo crudo a bronze")

    from obsm.errors import SchemaDriftError
    from obsm.ingest.deis_defunciones import DeisDefunciones

    sub("Leer el fixture")
    # Se usa el fixture con la estructura REAL de DEIS: es el que trae DIAG1/DIAG2.
    bronze = DeisDefunciones().preparar(MUESTRA_ESTRUCTURA_REAL)
    print(f"    {len(bronze)} filas, {len(bronze.columns)} columnas")
    print(f"    columnas: {list(bronze.columns)[:8]}...")

    sub("Lo que el ingestor SÍ hace")
    print(bronze[["anio", "sexo", "edad_anios", "causa_basica", "causa_externa",
                  "causa_cie10", "comuna_cut_fuente"]].head(4).to_string(index=False))
    print("\n  Fíjate en `causa_cie10`: es DERIVADA de las otras dos (ver sección 2).")
    print("  Y en `comuna_cut_fuente`: viene tal cual, SIN rellenar. Rellenarlo es")
    print("  'resolver comunas', que le toca a silver, no al ingestor.")

    sub("El contrato de esquema: si la fuente cambia, falla y no adivina")
    try:
        DeisDefunciones().validar_esquema(pd.DataFrame({"otra_cosa": [1]}))
    except SchemaDriftError as exc:
        print(f"    SchemaDriftError: {str(exc)[:150]}...")
    print("\n  Adaptarse en silencio a un cambio de esquema es cómo se publican")
    print("  series rotas. Preferimos que se caiga.")


# =====================================================================================
# 5. SILVER
# =====================================================================================

def seccion_5() -> None:
    """Acá y solo acá se aplican `territorio` y `cie10`."""
    titulo(5, "Silver: normalización a la grilla canónica")

    from obsm.ingest.deis_defunciones import DeisDefunciones
    from obsm.ingest.ine_proyecciones import IneProyecciones
    from obsm.transform.silver import normalizar_defunciones, normalizar_poblacion

    sub("Numerador: defunciones")
    bronze = DeisDefunciones().preparar(MUESTRA_DEFUNCIONES)
    defs, rep_d = normalizar_defunciones(bronze)
    print(defs[["comuna_cut", "region_cut", "anio", "sexo", "grupo_edad",
                "causa_cie10", "es_suicidio"]].head(6).to_string(index=False))
    print(f"\n  reporte: {rep_d}")
    print("\n  El reporte es parte de la salida, no un efecto secundario: la tasa de")
    print("  comunas no resueltas es un indicador de calidad que se publica con el dato.")

    sub("Fíjate en `cut_desconocidos`")
    print("  DEIS usa 99999 como centinela de 'comuna ignorada'. Tiene cinco dígitos,")
    print("  así que validar solo el FORMATO lo dejaba pasar como comuna real (A-007).")
    print("  Ahora se valida contra la DPA: existe o no existe.")

    sub("Denominador: población")
    pob, rep_p = normalizar_poblacion(IneProyecciones().preparar(MUESTRA_POBLACION))
    print(pob.head(5).to_string(index=False))
    print(f"\n  tope_edad numerador = {rep_d['tope_edad']}, denominador = {rep_p['tope_edad']}")
    print("  TIENEN que coincidir. Si divergen, la estandarización descarta los grupos")
    print("  que no calzan y la tasa sale calculada sin adultos mayores, sin dar error.")


# =====================================================================================
# 6. GOLD
# =====================================================================================

def seccion_6() -> None:
    """Tasas, suavizado y supresión estadística."""
    titulo(6, "Gold: tasas publicables")

    from obsm.ingest.deis_defunciones import DeisDefunciones
    from obsm.ingest.ine_proyecciones import IneProyecciones
    from obsm.transform.gold import tasas_comunales
    from obsm.transform.silver import (
        agregar_avpp,
        agregar_defunciones,
        normalizar_defunciones,
        normalizar_poblacion,
    )

    defs, _ = normalizar_defunciones(DeisDefunciones().preparar(MUESTRA_DEFUNCIONES))
    pob, _ = normalizar_poblacion(IneProyecciones().preparar(MUESTRA_POBLACION))
    agregado = agregar_defunciones(defs, "SUICIDIO",
                                   dimensiones=["comuna_cut", "anio", "grupo_edad"])
    avpp = agregar_avpp(defs, "SUICIDIO")

    sub("Con k=1 (sin supresión) para poder ver todo")
    gold, meta = tasas_comunales(agregado, pob, "SUICIDIO", avpp=avpp, k=1)
    cols = ["comuna_cut", "anio", "casos", "poblacion", "tasa_cruda",
            "tasa_estandarizada", "tasa_suavizada_eb", "peso_local_eb", "avpp"]
    print(gold.query("anio == 2022")[cols].to_string(index=False))

    sub("Qué significa cada columna")
    print("  tasa_cruda         casos / población x 100.000. Simple y engañosa: una")
    print("                     comuna envejecida tiene más muertes por demografía.")
    print("  tasa_estandarizada cuánto moriría si tuviera la estructura etaria del")
    print("                     estándar OMS. Es la que permite comparar territorios.")
    print("  tasa_suavizada_eb  Bayes empírico. Encoge la tasa de las comunas chicas")
    print("                     hacia la media, porque ahí el dato es mayormente ruido.")
    print("  peso_local_eb      cuánto pesa el dato propio frente a la media. Cerca de")
    print("                     0 = la cifra de esa comuna no dice casi nada.")
    print("  avpp               años de vida perdidos: suma de max(0, 80 - edad).")

    sub("Población cero no es tasa cero")
    ant = gold.query("comuna_cut == '12202'")
    if len(ant):
        print(f"    Antártica: población={int(ant['poblacion'].iloc[0])}, "
              f"tasa_cruda={ant['tasa_cruda'].iloc[0]}")
    print("  Un 0,0 se leería como 'no hubo muertes'. NaN dice 'no hay a quién dividir'.")
    print("  Son afirmaciones opuestas y confundirlas sesga cualquier comparación.")

    sub("Ahora con k=10, la supresión de verdad")
    gold_k, meta_k = tasas_comunales(agregado, pob, "SUICIDIO", avpp=avpp, k=10)
    n_sup = int(gold_k["suprimido"].sum())
    print(f"    {n_sup} de {len(gold_k)} celdas suprimidas "
          f"({meta_k['supresion']['porcentaje']:.0%})")
    print("\n  Ninguna celda pública puede tener un conteo entre 1 y 9. Se suprime la")
    print("  celda Y todo lo derivado de ella:")
    sup = gold_k[gold_k["suprimido"]]
    for col in ("casos", "tasa_cruda", "tasa_estandarizada", "avpp"):
        print(f"    {col:20} valores visibles en filas suprimidas: {int(sup[col].notna().sum())}")
    print("\n  El AVPP es el más sensible de todos: como el aporte es 80 - edad, un AVPP")
    print("  de 61 en una celda de UNA muerte dice que la persona tenía 19 años.")

    sub("Advertencias automáticas")
    for aviso in meta["advertencias"]:
        print(f"    - {aviso}")
    if not meta["advertencias"]:
        print("    (ninguna con este fixture)")


# =====================================================================================
# 7. RECONCILIACIÓN
# =====================================================================================

def seccion_7() -> None:
    """El portero: si un total no cuadra con la cifra oficial, no se publica."""
    titulo(7, "Reconciliación: por qué el pipeline puede negarse a publicar")

    from obsm.errors import ReconciliationError
    from obsm.reconciliacion import Ancla, cargar_anclas, reconciliar

    sub("Las anclas declaradas")
    anclas = cargar_anclas()
    for a in anclas:
        print(f"    {a.id:30} {a.valor:>13,.0f}  tol {a.tolerancia_relativa:.2%}")
        print(f"    {'':30} {a.referencia[:66]}")
    print("\n  Un ancla sin `referencia` y `fecha_verificacion` NO se carga. Un número")
    print("  sin origen comprobable no valida nada: solo traslada la fe de lugar.")

    sub("Contra datos reales, si los hay")
    tablas = {}
    for source_id in sorted({a.source_id for a in anclas}):
        candidatos = sorted((RAIZ / "data" / "silver" / source_id).glob("*.parquet"))
        if candidatos:
            tablas[source_id] = pd.read_parquet(candidatos[-1])
    if tablas:
        for r in reconciliar(tablas, anclas, estricto=False):
            if r["estado"] == "omitida":
                continue
            print(f"    {r['ancla']:30} {r['estado']:6} "
                  f"observado={r['observado']:>13,.0f} dif={r['diferencia_relativa']:.4%}")
    else:
        print("    (no hay silver en data/ — corre el pipeline si quieres verlo)")

    sub("Qué pasa cuando NO cuadra")
    falsa = Ancla(
        id="ejemplo_roto", descripcion="ancla inventada para la demo",
        source_id="demo", metrica={"tipo": "conteo_filas"}, valor=1000,
        referencia="ninguna, es una demo", fecha_verificacion="2026-01-01",
    )
    demo = pd.DataFrame({"x": range(900)})  # 900 filas contra un ancla de 1000: -10 %
    try:
        reconciliar({"demo": demo}, [falsa], estricto=True)
    except ReconciliationError as exc:
        print(f"    ReconciliationError: {exc}")
    print("\n  En `obsm build gold` esto ABORTA y no se escribe ningún archivo.")
    print("  Preferimos no publicar a publicar una serie rota con aspecto correcto.")


# =====================================================================================
# 8. EL REM: DONDE SÍ ESTÁN LA DEPRESIÓN Y LA ANSIEDAD
# =====================================================================================

def _mostrar_mapeo() -> None:
    """Imprime los conceptos de salud mental del último año mapeado."""
    import yaml

    ruta = RAIZ / "config" / "rem_secciones.yml"
    if not ruta.exists():
        print("  (no existe config/rem_secciones.yml; generar con `obsm rem mapear`)")
        return
    mapa = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    anios = sorted(mapa.get("anios", {}))
    print(f"  años mapeados: {anios[0]}-{anios[-1]} ({len(anios)} años)")
    conceptos = mapa["anios"][anios[-1]]["conceptos"]
    for cod, v in list(conceptos.items()):
        if any(k in (v["grupo"] + v["concepto"]).upper()
               for k in ("DEPRESI", "SUICID", "ANSIEDAD")):
            print(f"    {cod}  {(v['concepto'] or v['grupo'])[:44]}")
    print(f"  no legibles: {mapa.get('no_legibles', [])}")


def _mapeo_de_juguete() -> dict:
    """Mapeo mínimo con la forma del que genera `obsm rem mapear`, para el fixture."""
    return {
        "anios": {2023: {
            "diccionario": "demo",
            "conceptos": {
                "P6221600": {"grupo": "TRASTORNOS DEL HUMOR", "concepto": "DEPRESIÓN LEVE"},
                "P6227500": {"grupo": "TRASTORNOS DEL HUMOR", "concepto": "DEPRESIÓN MODERADA"},
                "P6230800": {"grupo": "SUICIDIO", "concepto": "IDEACIÓN"},
            },
            "columnas": {f"COL{i:02d}": {
                "grupo_edad": "" if i <= 3 else ("0 a 4 años" if i <= 5 else "5 a 9 años"),
                "sexo": ["ambos", "hombres", "mujeres"][(i - 1) % 3 if i <= 3 else (i % 2)],
            } for i in range(1, 8)},
        }},
    }


def seccion_8() -> None:
    """La segunda fuente, y la que contesta la mayoría de las preguntas."""
    titulo(8, "El REM: personas en tratamiento, no muertes")

    from obsm.transform.gold import tabla_rem
    from obsm.transform.silver import grupo_edad_rem, normalizar_rem

    sub("Por qué existe esta fuente")
    print("  La mortalidad no sirve para medir salud mental. En 22 años de defunciones:")
    print("     depresión (trastornos del ánimo)  252 muertes  =  11 al año en todo Chile")
    print("     ansiedad                           47 muertes  =   2 al año")
    print()
    print("  No es que sean raras: es que la gente no se muere de eso. Donde sí")
    print("  aparecen es en la atención primaria, como personas en tratamiento.")

    sub("La trampa de este archivo")
    print("  Las columnas del REM son GENÉRICAS: Col01 a Col38, sin nombre. Lo que")
    print("  cuenta cada una depende del `CodigoPrestacion` de la fila Y del año,")
    print("  porque el formulario se reordena. Un Col17=1 no significa nada solo.")
    print()
    print("  El significado vive en `config/rem_secciones.yml`, generado con")
    print("  `obsm rem mapear` desde los diccionarios que publica DEIS.")

    sub("Un vistazo al mapeo")
    _mostrar_mapeo()

    sub("Los grupos etarios calzan con los del resto del proyecto")
    for txt in ("0 a 4 años", "45 a 49 años", "80 y más años", "de 20 a 30"):
        print(f"    {txt!r:18} -> {grupo_edad_rem(txt)!r}")
    print("  Fue suerte, no diseño: el REM ya usaba quinquenios con abierto en 80,")
    print("  que es la misma grilla que impone el denominador del INE.")

    sub("La cadena, sobre el fixture")
    from obsm.ingest.rem_poblacion_control import RemPoblacionControl

    muestra = FIXTURES / "rem_salud_mental" / "muestra_serie_p.txt"
    bronze = RemPoblacionControl(mapeo=_mapeo_de_juguete()).preparar(muestra)
    silver, rep = normalizar_rem(bronze)
    gold, meta = tabla_rem(silver, k=1)
    print(gold[["comuna_cut", "periodo", "etiqueta", "personas"]].to_string(index=False))

    sub("Tres formas de contar a la misma persona dos veces")
    print("  1. El formulario trae una columna de TOTAL y 17 de detalle etario.")
    print("     Son la misma gente. `es_total_etario` obliga a elegir una.")
    print("  2. Trae «ambos sexos» junto a «hombres» y «mujeres»: la misma población")
    print("     partida. Se filtra a «ambos» cuando el sexo no es dimensión pedida.")
    print("  3. Los períodos son cortes de un STOCK, no flujos. Sumar junio con")
    print("     diciembre cuenta dos veces a quien siguió en tratamiento todo el año.")
    print()
    print(f"  período detectado en el fixture: {rep['periodos']}")
    print("  (semestral, no mensual: el plan asumía lo contrario y estaba equivocado)")

    sub("Por qué son conteos y no tasas")
    for a in meta["advertencias"]:
        print(f"    - {a}")


# =====================================================================================
# 9. EXPERIMENTOS
# =====================================================================================

def seccion_9() -> None:
    """Cosas para romper a propósito. Es la mejor forma de entender los guardas."""
    titulo(9, "Rompe esto y mira qué pasa")

    print("""
  Cada uno de estos experimentos hace fallar algo A PROPÓSITO. Los guardas del
  proyecto existen porque estos errores ya ocurrieron de verdad.

  (a) EL CERO A LA IZQUIERDA
      Lee el fixture de población forzando `Comuna` a entero y mira cuántas
      comunas sobreviven al cruce con la DPA:

          import pandas as pd
          from obsm.territorio import cargar_dpa
          df = pd.read_csv("tests/fixtures/ine_proyecciones/muestra_cadena.csv",
                           encoding="latin-1")          # sin dtype=str
          print(sorted(df["Comuna"].unique()))          # 1101, no "01101"
          print(set(df["Comuna"].astype(str)) & set(cargar_dpa().por_cut))

  (b) LA GRILLA ETARIA DESALINEADA
      Normaliza el numerador con tope 85 y el denominador con 80, y mira cómo
      la tasa estandarizada baja sin que nada dé error:

          normalizar_defunciones(bronze, tope_edad=85)
          normalizar_poblacion(bronze_pob, tope_edad=80)
      Después revisa `grupos_edad_descartados` en la salida de gold.

  (c) EL ANCLA QUE NO CUADRA
      Edita `config/anclas.yml`, cambia un `valor`, y corre:

          obsm build gold --source deis_defunciones --agrupador SUICIDIO

      Debe salir con código 1 y NO escribir nada. Comprueba que el CSV anterior
      quedó intacto. Después restaura el valor.

  (d) LA SUPRESIÓN
      Baja k a 1 en `tasas_comunales` y cuenta cuántas celdas quedan con
      conteos entre 1 y 9. Ese es exactamente el dato que no se publica, y
      por qué: con poblaciones chicas, un conteo de 2 puede identificar personas.

  (e) EL AGRUPADOR SOBRE LA COLUMNA EQUIVOCADA
      Clasifica `causa_basica` en vez de `causa_cie10` y cuenta suicidios:

          bronze["causa_basica"].map(AGRUPADORES["SUICIDIO"].contiene).sum()

      En el archivo real eso da CERO en 27 años. Es el bug A-004.

  (f) UN AÑO SIN DENOMINADOR
      Pasa `anios_cobertura=(1990, 2023)` a `tasas_comunales` y mira el metadato
      `casos_sin_denominador` y `casos_fuera_de_ventana`.

  DÓNDE SEGUIR LEYENDO
      docs/05-CALIDAD.md   las anomalías A-001 a A-009, cada una con su historia
      docs/02-ARQUITECTURA.md  qué puede y qué no puede hacer cada capa
      docs/06-ETICA-Y-DATOS.md los límites que no se negocian
      CLAUDE.md            las reglas operativas del repositorio
""")


SECCIONES = {
    1: seccion_1, 2: seccion_2, 3: seccion_3, 4: seccion_4, 5: seccion_5,
    6: seccion_6, 7: seccion_7, 8: seccion_8, 9: seccion_9,
}


def main(argv: list[str]) -> int:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 30)

    pedidas = []
    for arg in argv:
        if not arg.isdigit() or int(arg) not in SECCIONES:
            print(f"Sección desconocida: {arg!r}. Válidas: {sorted(SECCIONES)}")
            return 1
        pedidas.append(int(arg))

    for n in pedidas or sorted(SECCIONES):
        SECCIONES[n]()

    print(f"\n{'=' * 78}")
    print("  Listo. Corre `python ejemplos/practica.py 9` para los experimentos.")
    print(f"{'=' * 78}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
