"""CLI de obsm. Uso: `obsm <grupo> <accion> [...]` o `python -m obsm.cli ...`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .errors import ObsmError
from .registry import cargar_registro, verificar_urls
from .territorio import N_COMUNAS_ESPERADO, cargar_dpa, validar_dpa

log = logging.getLogger(__name__)


def _log(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


# -- sources ----------------------------------------------------------------------------

def cmd_sources_list(args) -> int:
    reg = cargar_registro(args.config)
    resumen = reg.resumen()
    print(f"{len(reg)} fuentes | verificadas={resumen['verificadas']} "
          f"no_verificadas={resumen['no_verificadas']} rotas={resumen['rotas']}\n")
    print(f"{'id':28} {'estado':16} {'origen_url':16} {'fase':>4} {'prio':>4}  organismo")
    print("-" * 100)
    for f in sorted(reg, key=lambda f: (f.fase or 99, f.prioridad or 99, f.id)):
        print(f"{f.id:28} {f.estado:16} {str(f.origen_url):16} "
              f"{str(f.fase or ''):>4} {str(f.prioridad or ''):>4}  {f.organismo or ''}")
    if resumen["verificadas"] == 0:
        print("\nNinguna fuente verificada todavía: el pipeline de producción está bloqueado "
              "por diseño. Correr `obsm sources verify` con red y actualizar sources.yml.")
    return 0


def cmd_sources_verify(args) -> int:
    reg = cargar_registro(args.config)
    resultados = verificar_urls(reg)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
    fallidos = [r for r in resultados if r.get("resultado") != "ok"]
    print(f"\n{len(resultados) - len(fallidos)}/{len(resultados)} URLs respondieron.")
    print("Recordatorio: responder 200 no es verificar. Hay que abrir el archivo, "
          "confirmar que es lo que dice ser y recién ahí editar `estado` a mano.")
    return 1 if fallidos else 0


def cmd_sources_show(args) -> int:
    reg = cargar_registro(args.config)
    f = reg.get(args.id)
    print(json.dumps(f.__dict__, ensure_ascii=False, indent=2, default=str))
    return 0


# -- territorio -------------------------------------------------------------------------

def cmd_territorio_validar(args) -> int:
    dpa = cargar_dpa(args.dpa)
    problemas = validar_dpa(dpa, estricto=False)
    print(f"Comunas cargadas: {len(dpa)} de {N_COMUNAS_ESPERADO} esperadas")
    ambiguos = dpa.nombres_ambiguos()
    if ambiguos:
        print(f"Nombres ambiguos (requieren región): {ambiguos}")
    if problemas:
        print("\nProblemas:")
        for p in problemas:
            print(f"  - {p}")
        print("\nVer config/territorio_comunas.README.md para completar la tabla.")
        return 1
    print("Tabla DPA válida.")
    return 0


def cmd_territorio_resolver(args) -> int:
    from .territorio import normalizar_comuna

    try:
        print(normalizar_comuna(args.nombre, args.region, estricto=True))
        return 0
    except ObsmError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


# -- qa ---------------------------------------------------------------------------------

def cmd_qa(args) -> int:
    """Comprobaciones que se pueden correr sin red ni datos descargados."""
    fallos = 0
    try:
        reg = cargar_registro(args.config)
        print(f"[ok] catálogo de fuentes válido ({len(reg)} fuentes)")
    except ObsmError as exc:
        print(f"[FALLA] catálogo: {exc}")
        fallos += 1
    try:
        dpa = cargar_dpa(args.dpa)
        problemas = validar_dpa(dpa, estricto=False)
        estado = "ok" if not problemas else "AVISO"
        print(f"[{estado}] DPA: {len(dpa)} comunas; {len(problemas)} problema(s)")
        if problemas:
            fallos += 1
    except ObsmError as exc:
        print(f"[FALLA] DPA: {exc}")
        fallos += 1

    fallos += _qa_reconciliacion()

    print("\nNota: `obsm qa` no reemplaza `make test`. Corre ambos antes de publicar.")
    return 1 if fallos else 0


def _qa_reconciliacion() -> int:
    """Reconcilia contra las anclas si hay silver en disco. Devuelve el número de fallas.

    En modo NO estricto a propósito: `obsm qa` es diagnóstico y conviene ver todas las
    anclas caídas de una, no solo la primera. El modo que bloquea vive en `build gold`.
    """
    import pandas as pd

    from .io import elegir_tabla
    from .reconciliacion import cargar_anclas, reconciliar

    try:
        anclas = cargar_anclas()
    except ObsmError as exc:
        print(f"[FALLA] catálogo de anclas: {exc}")
        return 1

    tablas = {}
    ambiguas = 0
    for source_id in sorted({a.source_id for a in anclas}):
        try:
            elegido = elegir_tabla("silver", source_id)
        except ObsmError as exc:
            # Un almacén ambiguo es un hallazgo de calidad, no un motivo para abortar el
            # diagnóstico: `qa` existe para enumerar problemas, y el que bloquea la
            # publicación es `build gold`. Se reporta y se sigue con las demás fuentes.
            print(f"[FALLA] almacén ambiguo en {source_id}: {exc}")
            ambiguas += 1
            continue
        if elegido is not None:
            tablas[source_id] = pd.read_parquet(elegido)

    if not tablas:
        print(f"[--] reconciliación: {len(anclas)} anclas declaradas, sin silver para "
              f"contrastar. Correr `obsm build silver` primero.")
        return ambiguas

    resultados = reconciliar(tablas, anclas, estricto=False)
    fallas = [r for r in resultados if r["estado"] == "FALLA"]
    omitidas = [r for r in resultados if r["estado"] == "omitida"]
    ok = len(resultados) - len(fallas) - len(omitidas)
    estado = "ok" if not fallas else "FALLA"
    print(f"[{estado}] reconciliación: {ok}/{len(resultados)} anclas cuadran"
          + (f", {len(omitidas)} sin datos" if omitidas else ""))
    for r in fallas:
        print(f"     - {r['ancla']}: calculado={r['observado']:,.0f} "
              f"oficial={r['oficial']:,.0f} dif={r['diferencia_relativa']:.2%}")
    return (1 if fallas else 0) + ambiguas


# -- ingest / build ---------------------------------------------------------------------

def cmd_ingest(args) -> int:
    from .ingest import INGESTORES

    reg = cargar_registro(args.config)
    fuente = reg.exigir_verificada(args.id, permitir_no_verificada=args.permitir_no_verificada)
    if args.id not in INGESTORES:
        print(f"ERROR: no hay ingestor implementado para {args.id!r}. "
              f"Disponibles: {sorted(INGESTORES)}", file=sys.stderr)
        return 1
    ruta = Path(args.archivo)
    if not ruta.exists():
        print(f"ERROR: no existe {ruta}. Descarga el archivo y pásalo con --archivo "
              f"(ver la receta de descarga en CLAUDE.md §4).", file=sys.stderr)
        return 1
    df, manifiesto = INGESTORES[args.id](fuente).ingerir(ruta)
    sha = manifiesto.sha256 or "sin-hash"
    print(f"bronze escrito: {len(df)} filas | sha256={sha[:12]}… "
          f"| encoding={manifiesto.encoding}")
    return 0


#: Orden del pipeline de Fase 1. El denominador va primero porque `build gold` lo necesita
#: y porque si falla, no tiene sentido gastar once minutos ingiriendo el numerador.
PIPELINE_FASE_1 = ["ine_proyecciones", "deis_defunciones"]


def _asegurar_raw(fuente, forzar: bool = False) -> Path:
    """Devuelve la ruta al archivo crudo, descargándolo y descomprimiéndolo si hace falta.

    Verifica el hash declarado en `config/sources.yml`. Una descarga que completó no es una
    descarga correcta: el servidor pudo servir una página de error con código 200.
    """
    import zipfile

    from .io import DIR_DATOS, descargar, sha256_archivo

    dir_raw = DIR_DATOS / "raw" / fuente.id
    dir_raw.mkdir(parents=True, exist_ok=True)

    # El nombre del miembro extraído manda: es lo que ingiere el pipeline. Si ya está,
    # no se vuelve a bajar el ZIP de 93 MB para sacar el mismo CSV.
    extraido = fuente.extra.get("archivo_extraido")
    if extraido and (dir_raw / extraido).exists() and not forzar:
        log.info("[%s] usando el archivo ya extraído: %s", fuente.id, extraido)
        return dir_raw / extraido

    url = fuente.url_archivo or fuente.url_principal
    if not url:
        raise ObsmError(f"[{fuente.id}] no hay url_archivo en el catálogo")
    # Cuando la fuente es un endpoint con query string, la ruta de la URL no es un nombre
    # de archivo: SINIM entrega la serie desde `obtener_datos_municipales.php`. Ese nombre
    # viajaría hasta el parquet de bronze y no diría nada de lo que contiene.
    destino = dir_raw / (fuente.extra.get("nombre_local") or Path(url.split("?")[0]).name)

    if destino.exists() and not forzar:
        log.info("[%s] usando el archivo en caché: %s", fuente.id, destino.name)
    else:
        log.info("[%s] descargando %s", fuente.id, url)
        descargar(url, destino, fuente.id, forzar=forzar, sha256_esperado=fuente.sha256)

    if not zipfile.is_zipfile(destino):
        return destino

    if not extraido:
        raise ObsmError(
            f"[{fuente.id}] el archivo es un ZIP pero el catálogo no declara "
            f"`archivo_extraido`. Sin eso no se sabe qué miembro ingerir."
        )
    with zipfile.ZipFile(destino) as z:
        miembros = z.namelist()
        if extraido not in miembros:
            raise ObsmError(
                f"[{fuente.id}] el ZIP no contiene {extraido!r}. Miembros: {miembros[:10]}. "
                f"La fuente cambió el nombre del archivo: revisar y actualizar el catálogo."
            )
        log.info("[%s] extrayendo %s", fuente.id, extraido)
        z.extract(extraido, dir_raw)

    csv = dir_raw / extraido
    esperado = fuente.extra.get("sha256_extraido")
    if esperado and sha256_archivo(csv) != esperado:
        raise ObsmError(
            f"[{fuente.id}] el archivo extraído no coincide con `sha256_extraido`. "
            f"El ZIP publicado cambió de contenido sin cambiar de URL."
        )
    return csv


def cmd_run(args) -> int:
    """Pipeline de Fase 1 completo, en un comando.

    Reutiliza los mismos `cmd_*` que se invocan por separado en vez de reimplementarlos:
    si mañana cambia la ingesta, este comando cambia con ella. Se detiene en el primer
    error, porque encadenar sobre una etapa fallida produce basura con buen aspecto.
    """
    from types import SimpleNamespace

    reg = cargar_registro(args.config)
    pasos: list[tuple[str, str]] = []

    def paso(nombre: str, fn, **kwargs) -> bool:
        print(f"\n>>> {nombre}")
        codigo = fn(SimpleNamespace(config=args.config, dpa=args.dpa, **kwargs))
        pasos.append((nombre, "ok" if codigo == 0 else "FALLA"))
        return codigo == 0

    for source_id in PIPELINE_FASE_1:
        fuente = reg.exigir_verificada(source_id)
        try:
            ruta = _asegurar_raw(fuente, forzar=args.forzar_descarga)
        except (ObsmError, Exception) as exc:  # noqa: BLE001
            print(f"ERROR obteniendo el archivo de {source_id}: {exc}", file=sys.stderr)
            return 1

        if not paso(f"ingest {source_id}", cmd_ingest,
                    id=source_id, archivo=str(ruta), permitir_no_verificada=False):
            return 1
        if not paso(f"build silver {source_id}", cmd_build_silver,
                    source=source_id, entrada=None):
            return 1

    if not paso(f"build gold ({args.agrupador})", cmd_build_gold,
                source="deis_defunciones", agrupador=args.agrupador,
                poblacion=None, k=args.k, sin_reconciliar=False):
        return 1

    print(f"\n{'=' * 70}\n  RESUMEN\n{'=' * 70}")
    for nombre, estado in pasos:
        print(f"  {estado:6} {nombre}")
    print("\nLa salida está en data/gold/ con su manifiesto y su reporte de calidad.")
    return 0


def cmd_rem_mapear(args) -> int:
    """Regenera `config/rem_secciones.yml` desde los diccionarios publicados por DEIS.

    El mapeo vive en `config/` y no en código (CLAUDE.md §7), pero tiene que ser
    **reproducible**: cuando DEIS publique el año siguiente, esto se corre de nuevo y el
    diff muestra exactamente qué conceptos cambiaron. Un mapeo escrito a mano una vez es
    un mapeo que nadie se atreve a actualizar.

    Lee solo los diccionarios de cada ZIP con peticiones de rango: son ~7 MB en total
    contra los 3,5 GB que pesan los archivos completos.
    """
    import re
    import tempfile

    import yaml

    from .ingest.rem_diccionario import leer_columnas, leer_conceptos
    from .io import extraer_de_zip_remoto, listar_zip_remoto

    reg = cargar_registro(args.config)
    fuente = reg.get("rem_salud_mental")
    patron = fuente.extra.get("patron_url_anual")
    if not patron:
        print("ERROR: la fuente no declara `patron_url_anual`.", file=sys.stderr)
        return 1

    salida: dict = {"seccion": args.hoja, "fuente": "rem_salud_mental", "anios": {}}
    ilegibles: list[str] = []

    for anio in range(args.desde, args.hasta + 1):
        url = patron.format(anio=anio)
        try:
            miembros = listar_zip_remoto(url)
        except Exception as exc:  # noqa: BLE001
            ilegibles.append(f"{anio}: no se pudo leer el ZIP ({type(exc).__name__})")
            continue

        dicc = [m for m in miembros
                if re.search(r"dicc", m.nombre, re.I)
                and re.search(r"SP[-_ ]?\d", m.nombre, re.I) and m.bytes_reales > 0]
        if not dicc:
            ilegibles.append(f"{anio}: sin diccionario de la Serie P en el ZIP")
            continue

        datos = extraer_de_zip_remoto(url, dicc[0])
        sufijo = Path(dicc[0].nombre).suffix or ".xls"
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as fh:
            fh.write(datos)
            tmp = Path(fh.name)
        try:
            conceptos = leer_conceptos(tmp, hoja=args.hoja)
            columnas = leer_columnas(tmp, hoja=args.hoja)
        except Exception as exc:  # noqa: BLE001
            ilegibles.append(f"{anio}: diccionario ilegible ({type(exc).__name__})")
            continue
        finally:
            tmp.unlink(missing_ok=True)

        if not conceptos:
            ilegibles.append(f"{anio}: sin conceptos en la hoja {args.hoja}")
            continue

        salida["anios"][anio] = {
            "diccionario": dicc[0].nombre.split("/")[-1],
            "conceptos": {c.codigo: {"grupo": c.grupo, "concepto": c.concepto}
                          for c in conceptos},
            "columnas": {c.nombre: {"grupo_edad": c.grupo_edad, "sexo": c.sexo}
                         for c in columnas},
        }
        print(f"  {anio}: {len(conceptos):>3} conceptos, {len(columnas):>3} columnas")

    if ilegibles:
        salida["no_legibles"] = ilegibles
        print("\nAños que no se pudieron mapear:")
        for x in ilegibles:
            print(f"  {x}")

    destino = Path(args.salida)
    cabecera = (
        "# Mapeo de las secciones del REM. GENERADO, no editar a mano.\n"
        "#\n"
        "# Regenerar con:  obsm rem mapear\n"
        "#\n"
        "# Existe porque los archivos del REM traen columnas genéricas (`Col01`..`Col38`)\n"
        "# cuyo significado depende del `CodigoPrestacion` de cada fila. Sin este mapeo,\n"
        "# un valor del archivo no se puede interpretar.\n"
        "#\n"
        "# El diff entre dos versiones de este archivo ES el registro de qué cambió el\n"
        "# formulario entre años, que es justo lo que un ingestor tiene que saber.\n"
        "# Ver docs/05-CALIDAD.md#quiebres-rem.\n"
    )
    destino.write_text(
        cabecera + yaml.safe_dump(salida, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\nescrito: {destino} ({len(salida['anios'])} años mapeados)")
    return 0


def _procesar_anio_rem(fuente, url, miembro, anio, dir_raw, destino, forzar):
    """Baja, ingiere y normaliza un año del REM. Devuelve las filas de silver."""
    import gc

    from .ingest.rem_poblacion_control import RemPoblacionControl
    from .io import extraer_de_zip_remoto
    from .transform.silver import normalizar_rem

    crudo = dir_raw / f"serie_p_{anio}{Path(miembro.nombre).suffix or '.txt'}"
    if not crudo.exists() or forzar:
        print(f"{anio}: bajando {miembro.nombre.split('/')[-1]} "
              f"({miembro.bytes_comprimidos / 1024 / 1024:.0f} MB)")
        crudo.write_bytes(extraer_de_zip_remoto(url, miembro))

    bronze = RemPoblacionControl(fuente).preparar(crudo)
    silver, rep = normalizar_rem(bronze)

    destino.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(destino, index=False)
    destino.with_suffix(".reporte.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"{anio}: {len(bronze):>9,} bronze -> {len(silver):>8,} silver "
          f"| periodos {rep['periodos']} | cut inválidos {rep['cut_invalidos']}")
    filas = len(silver)
    # Un año son ~2,6 millones de filas en bronze. Liberarlas antes de empezar el
    # siguiente evita que la memoria crezca con cada iteración.
    del bronze, silver
    gc.collect()
    return filas


def cmd_rem_ingerir(args) -> int:
    """Ingiere la Serie P del REM año por año, hasta silver.

    Descarga solo el miembro que interesa de cada ZIP con peticiones de rango: 152 MB en
    total contra los ~2.500 MB que pesan los archivos completos.

    Cada año se procesa entero y se guarda antes de pasar al siguiente. Con doce años y
    ~7 minutos por año, un fallo a mitad de camino no puede costar todo el trabajo previo.
    """
    import re

    from .io import DIR_DATOS, listar_zip_remoto, ruta_capa

    reg = cargar_registro(args.config)
    fuente = reg.exigir_verificada("rem_salud_mental")
    patron = fuente.extra.get("patron_url_anual")
    if not patron:
        print("ERROR: la fuente no declara `patron_url_anual`.", file=sys.stderr)
        return 1

    dir_raw = DIR_DATOS / "raw" / fuente.id
    dir_raw.mkdir(parents=True, exist_ok=True)
    resumen: list[tuple[int, str, int]] = []

    for anio in range(args.desde, args.hasta + 1):
        url = patron.format(anio=anio)
        destino_silver = ruta_capa("silver", fuente.id, f"serie_p_{anio}.parquet")
        if destino_silver.exists() and not args.forzar:
            print(f"{anio}: ya existe silver, se omite")
            resumen.append((anio, "en caché", 0))
            continue

        # El nombre del miembro cambia todos los años: SerieP2014.csv, SerieP.txt,
        # SerieP_2019.txt... Se busca por patrón, nunca por nombre exacto.
        try:
            miembros = listar_zip_remoto(url)
        except Exception as exc:  # noqa: BLE001
            print(f"{anio}: ZIP ilegible ({type(exc).__name__})", file=sys.stderr)
            resumen.append((anio, f"ZIP ilegible: {type(exc).__name__}", 0))
            continue

        sp = [m for m in miembros
              if re.search(r"serie\s*_?\s*p", m.nombre, re.I) and m.bytes_reales > 0]
        if not sp:
            print(f"{anio}: sin Serie P en el ZIP", file=sys.stderr)
            resumen.append((anio, "sin Serie P", 0))
            continue

        try:
            filas = _procesar_anio_rem(
                fuente, url, sp[0], anio, dir_raw, destino_silver, args.forzar
            )
        except Exception as exc:  # noqa: BLE001
            # A propósito se atrapa cualquier excepción y no solo ObsmError. Un año con un
            # defecto inesperado no puede costar el trabajo de los demás: la primera
            # corrida murió en 2014 con un TypeError y perdió los once años siguientes,
            # que era justamente lo que el guardado año por año quería evitar.
            print(f"{anio}: no se pudo procesar — {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            resumen.append((anio, f"error: {type(exc).__name__}", 0))
            continue
        resumen.append((anio, "ok", filas))

    print(f"\n{'=' * 62}\n  RESUMEN\n{'=' * 62}")
    for anio, estado, filas in resumen:
        print(f"  {anio}  {estado:22} {filas:>10,}" if filas else f"  {anio}  {estado}")
    return 0 if any(e == "ok" for _, e, _ in resumen) else 1


def cmd_build_silver(args) -> int:
    import pandas as pd

    from .io import elegir_tabla, ruta_capa
    from .transform.silver import (
        componer_aps_comunal,
        normalizar_defunciones,
        normalizar_inscritos,
        normalizar_poblacion,
    )

    # Cada fuente tiene su normalizador. Un dict y no un if: agregar una fuente no debe
    # obligar a editar el flujo de control, y una fuente sin normalizador tiene que
    # fallar diciendo eso, no caer por defecto en el de defunciones.
    normalizadores: dict[str, Callable[..., tuple[pd.DataFrame, dict]]] = {
        "deis_defunciones": normalizar_defunciones,
        "deis_establecimientos": componer_aps_comunal,
        "fonasa_inscritos": normalizar_inscritos,
        "ine_proyecciones": normalizar_poblacion,
    }
    if args.source not in normalizadores:
        print(f"ERROR: no hay normalizador para {args.source!r}. "
              f"Disponibles: {sorted(normalizadores)}", file=sys.stderr)
        return 1
    normalizar = normalizadores[args.source]

    entrada = Path(args.entrada) if args.entrada else None
    if entrada is None:
        entrada = elegir_tabla("bronze", args.source)
        if entrada is None:
            print(f"ERROR: no hay bronze para {args.source}. Corre `obsm ingest` primero.",
                  file=sys.stderr)
            return 1
    bronze = pd.read_parquet(entrada)
    silver, reporte = normalizar(bronze)
    destino = ruta_capa("silver", args.source, f"{entrada.stem}.parquet")
    destino.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(destino, index=False)
    destino.with_suffix(".reporte.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"silver escrito: {destino} ({len(silver)} filas)")
    print(json.dumps(reporte, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_build_gold(args) -> int:
    import pandas as pd

    from .errors import ReconciliationError
    from .io import elegir_tabla, ruta_capa
    from .reconciliacion import reconciliar
    from .transform.gold import tasas_comunales
    from .transform.silver import agregar_avpp, agregar_defunciones

    reg = cargar_registro(args.config)
    elegido = elegir_tabla("silver", args.source)
    if elegido is None:
        print(f"ERROR: no hay silver para {args.source}.", file=sys.stderr)
        return 1
    silver = pd.read_parquet(elegido)

    # El denominador sale del silver de población, no de un CSV suelto: así arrastra
    # el mismo territorio validado y el mismo tope etario que el numerador. Se admite
    # --poblacion para pruebas y para comparar contra otra base de proyección.
    if args.poblacion:
        poblacion = pd.read_csv(args.poblacion, dtype={"comuna_cut": str})
    else:
        elegida = elegir_tabla("silver", "ine_proyecciones")
        if elegida is None:
            print("ERROR: no hay silver de ine_proyecciones y no se pasó --poblacion. "
                  "Corre `obsm ingest ine_proyecciones` y luego "
                  "`obsm build silver --source ine_proyecciones`.", file=sys.stderr)
            return 1
        poblacion = pd.read_parquet(elegida)

    # Reconciliación ANTES de calcular nada. La regla de CLAUDE.md §7 es «si no cuadra, no
    # se publica», así que la comprobación tiene que estar en el camino de la publicación y
    # no en un script que alguien recuerde correr. En modo estricto una sola ancla fuera de
    # tolerancia aborta y no se escribe archivo: es preferible no publicar a publicar una
    # serie rota con aspecto correcto.
    if not args.sin_reconciliar:
        try:
            resultados = reconciliar(
                {args.source: silver, "ine_proyecciones": poblacion}, estricto=True
            )
        except ReconciliationError as exc:
            print(f"ERROR de reconciliación, no se publica nada:\n  {exc}", file=sys.stderr)
            print("\nSi la diferencia es esperable (cambio de base, revisión de la fuente), "
                  "actualiza `config/anclas.yml` con la nueva cifra y su procedencia. "
                  "No uses --sin-reconciliar para publicar.", file=sys.stderr)
            return 1
        ok = sum(1 for r in resultados if r["estado"] == "ok")
        omitidas = [r["ancla"] for r in resultados if r["estado"] == "omitida"]
        print(f"reconciliación: {ok}/{len(resultados)} anclas cuadran"
              + (f" ({len(omitidas)} omitidas: {omitidas})" if omitidas else ""))
    else:
        resultados = [{"estado": "omitida", "motivo": "--sin-reconciliar"}]
        print("AVISO: reconciliación desactivada. La salida NO es publicable.")

    # El agregado conserva `grupo_edad`: es lo que permite estandarizar. `tasas_comunales`
    # colapsa por su cuenta para la tasa cruda, así que pasarlo detallado no cambia esa
    # salida y habilita la otra.
    agregado = agregar_defunciones(
        silver, args.agrupador, dimensiones=["comuna_cut", "anio", "grupo_edad"]
    )
    avpp = agregar_avpp(silver, args.agrupador, dimensiones=["comuna_cut", "anio"])
    # La versión de CADA fuente viaja a cada fila. Sin esto, una tasa publicada no se puede
    # atribuir a una entrega concreta, y como un cambio de base poblacional mueve todas las
    # tasas a la vez, `poblacion_version` no es un adorno: es lo que distingue una serie de
    # otra que se ve igual. Iba en null en las 7.612 filas (CLAUDE.md §2.2).
    fuente_num = reg.get(args.source)
    fuente_pob = reg.get("ine_proyecciones")
    gold, meta = tasas_comunales(
        agregado, poblacion, args.agrupador, avpp=avpp,
        source_id=args.source, k=args.k,
        source_version=fuente_num.source_version,
        poblacion_version=fuente_pob.source_version,
    )
    meta["reconciliacion"] = resultados
    destino = ruta_capa("gold", args.source, f"{args.agrupador.lower()}_comunal.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    gold.to_csv(destino, index=False)
    destino.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"gold escrito: {destino} ({len(gold)} filas)")
    for aviso in meta["advertencias"]:
        print(f"  AVISO: {aviso}")
    return 0


def cmd_rem_gold(args) -> int:
    """Arma la tabla publicable del REM sobre todos los años que haya en silver.

    Une los archivos anuales en vez de exigir uno solo: la ingesta guarda año por año
    para poder reintentar barato, y esta es la otra mitad de esa decisión.
    """
    import pandas as pd

    from .io import ruta_capa
    from .transform.gold import tabla_rem

    reg = cargar_registro(args.config)
    fuente = reg.get("rem_salud_mental")

    dir_silver = ruta_capa("silver", fuente.id, "x").parent
    archivos = sorted(dir_silver.glob("serie_p_*.parquet"))
    if not archivos:
        print(f"ERROR: no hay silver del REM en {dir_silver}. "
              f"Correr `obsm rem ingerir` primero.", file=sys.stderr)
        return 1

    partes = [pd.read_parquet(a) for a in archivos]
    silver = pd.concat(partes, ignore_index=True)
    anios = sorted({p[:4] for p in silver["periodo"].dropna().unique()})
    print(f"{len(archivos)} años en silver ({anios[0]}-{anios[-1]}), "
          f"{len(silver):,} filas")

    # Se agrupa por la llave NORMALIZADA, no por la etiqueta cruda: el formulario
    # escribe el mismo concepto con distinta grafía según el año y agrupar por el texto
    # tal cual parte el total nacional en dos (A-012). `tabla_rem` devuelve igual una
    # etiqueta legible para publicar.
    dimensiones = ["comuna_cut", "periodo", "etiqueta_norm"]
    if args.por_edad:
        dimensiones += ["grupo_edad", "sexo"]

    gold, meta = tabla_rem(
        silver,
        dimensiones=dimensiones,
        usar_total_etario=not args.por_edad,
        k=args.k,
        source_id=fuente.id,
        source_version=fuente.source_version,
    )
    meta["anios"] = anios
    meta["archivos_silver"] = [a.name for a in archivos]

    sufijo = "_por_edad" if args.por_edad else ""
    destino = ruta_capa("gold", fuente.id, f"poblacion_control_salud_mental{sufijo}.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    gold.to_csv(destino, index=False)
    destino.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"gold escrito: {destino} ({len(gold):,} filas, "
          f"{meta['supresion']['porcentaje']:.1%} suprimidas)")
    for aviso in meta["advertencias"]:
        print(f"  AVISO: {aviso}")
    return 0


def _cargar_silver_unico(source_id: str, patron: str = "*.parquet"):
    """Devuelve el silver de una fuente, o None si no hay ninguno.

    Con más de un archivo y sin desempate explícito, `elegir_tabla` lanza en vez de elegir
    por orden alfabético (A-014).
    """
    import pandas as pd  # noqa: PLC0415

    from .io import elegir_tabla  # noqa: PLC0415

    elegido = elegir_tabla("silver", source_id, patron)
    return pd.read_parquet(elegido) if elegido is not None else None


def cmd_rem_cobertura(args) -> int:
    """Cruza el REM con la población inscrita y escribe la tabla de cobertura (I-03).

    Necesita cuatro capas silver y falla nombrando la que falte, en vez de producir una
    tabla parcial: sin `deis_establecimientos` no se puede saber en qué comunas la división
    es válida, y una cobertura calculada donde no corresponde se ve perfectamente creíble.
    """
    import pandas as pd

    from .io import elegir_tabla, ruta_capa
    from .quality import marcar_denominador_implausible, marcar_total_incoherente_con_tramos
    from .transform.gold import tabla_cobertura
    from .transform.silver import resolver_cut

    reg = cargar_registro(args.config)

    dir_rem = ruta_capa("silver", "rem_salud_mental", "x").parent
    archivos = sorted(dir_rem.glob("serie_p_*.parquet"))
    if not archivos:
        print(f"ERROR: no hay silver del REM en {dir_rem}. Correr `obsm rem ingerir`.",
              file=sys.stderr)
        return 1
    rem = pd.concat([pd.read_parquet(a) for a in archivos], ignore_index=True)

    faltan = []
    inscritos = _cargar_silver_unico("fonasa_inscritos")
    if inscritos is None:
        faltan.append("obsm ingest fonasa_inscritos && obsm build silver "
                      "--source fonasa_inscritos")
    aps = _cargar_silver_unico("deis_establecimientos")
    if aps is None:
        faltan.append("obsm ingest deis_establecimientos && obsm build silver "
                      "--source deis_establecimientos")
    poblacion = _cargar_silver_unico("ine_proyecciones")
    if poblacion is None:
        faltan.append("obsm ingest ine_proyecciones && obsm build silver "
                      "--source ine_proyecciones")
    if faltan:
        print("ERROR: faltan capas silver para calcular cobertura:", file=sys.stderr)
        for c in faltan:
            print(f"  {c}", file=sys.stderr)
        return 1

    # Las dos marcas de calidad del denominador se aplican acá y no en silver porque una
    # necesita el bronze completo (los tramos de beneficiarios) y la otra, la población.
    ruta_bronze = elegir_tabla("bronze", "fonasa_inscritos")
    if ruta_bronze is not None:
        bronze = pd.read_parquet(ruta_bronze)
        bronze["comuna_cut"], _ = resolver_cut(bronze["comuna_cut_fuente"])
        inscritos, rep_tramos = marcar_total_incoherente_con_tramos(inscritos, bronze)
        print(f"coherencia con tramos: {rep_tramos['celdas_incoherentes']} celdas marcadas "
              f"en {rep_tramos['comunas_incoherentes']} comunas")
    else:
        print("AVISO: no hay bronze de fonasa_inscritos; se omite la comprobación de "
              "coherencia con los tramos de beneficiarios.")
    inscritos, rep_impl = marcar_denominador_implausible(inscritos, poblacion)
    print(f"padrón minoritario: {rep_impl['celdas_implausibles']} celdas en "
          f"{rep_impl['comunas_implausibles']} comunas")

    f_rem = reg.get("rem_salud_mental")
    f_ins = reg.get("fonasa_inscritos")
    gold, meta = tabla_cobertura(
        rem, inscritos, aps, poblacion=poblacion, k=args.k,
        source_version=f_rem.source_version,
        version_inscritos=f_ins.source_version,
    )
    meta["archivos_silver_rem"] = [a.name for a in archivos]

    destino = ruta_capa("gold", "rem_salud_mental", "cobertura_salud_mental_aps.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    gold.to_csv(destino, index=False)
    destino.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\ngold escrito: {destino} ({len(gold):,} filas)")
    print(f"  denominador: {meta['celdas_por_denominador']}")
    print(f"  comunas con cobertura: {meta['comunas_con_cobertura']} de "
          f"{meta['comunas_en_el_numerador']}")
    for aviso in meta["advertencias"]:
        print(f"  AVISO: {aviso}")
    return 0


def _parser_rem(sub) -> None:
    """Subcomandos del REM. Aparte para que `construir_parser` no crezca sin control."""
    p_rem = sub.add_parser("rem", help="utilidades del REM")
    rem = p_rem.add_subparsers(dest="accion", required=True)

    rm = rem.add_parser("mapear", help="regenera config/rem_secciones.yml")
    rm.add_argument("--desde", type=int, default=2009)
    rm.add_argument("--hasta", type=int, default=2025)
    rm.add_argument("--hoja", default="P6", help="sección del REM (P6 = salud mental)")
    rm.add_argument("--salida", default="config/rem_secciones.yml")
    rm.set_defaults(func=cmd_rem_mapear)

    ri = rem.add_parser("ingerir", help="ingiere la Serie P año por año, hasta silver")
    ri.add_argument("--desde", type=int, default=2014)
    ri.add_argument("--hasta", type=int, default=2025)
    ri.add_argument("--forzar", action="store_true",
                    help="reprocesa años que ya tienen silver")
    ri.set_defaults(func=cmd_rem_ingerir)

    rg = rem.add_parser("gold", help="tabla publicable sobre todos los años")
    rg.add_argument("--k", type=int, default=5,
                    help="umbral de supresión (5 = actividad)")
    rg.add_argument("--por-edad", action="store_true",
                    help="desagrega por grupo etario y sexo; suprime mucho más")
    rg.set_defaults(func=cmd_rem_gold)

    rc = rem.add_parser(
        "cobertura",
        help="tabla de cobertura (I-03): personas en control por mil inscritos",
    )
    rc.add_argument("--k", type=int, default=5,
                    help="umbral de supresión del numerador (5 = actividad)")
    rc.set_defaults(func=cmd_rem_cobertura)


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="obsm", description="Observatorio de Salud Mental de Chile")
    p.add_argument("--version", action="version", version=f"obsm {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--config", default=None, help="ruta a sources.yml")
    p.add_argument("--dpa", default=None, help="ruta a territorio_comunas.csv")
    sub = p.add_subparsers(dest="grupo", required=True)

    s = sub.add_parser("sources", help="catálogo de fuentes").add_subparsers(
        dest="accion", required=True
    )
    s.add_parser("list").set_defaults(func=cmd_sources_list)
    s.add_parser("verify").set_defaults(func=cmd_sources_verify)
    sh = s.add_parser("show")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_sources_show)

    t = sub.add_parser("territorio", help="normalización territorial").add_subparsers(
        dest="accion", required=True
    )
    t.add_parser("validar").set_defaults(func=cmd_territorio_validar)
    tr = t.add_parser("resolver")
    tr.add_argument("nombre")
    tr.add_argument("--region", default=None)
    tr.set_defaults(func=cmd_territorio_resolver)

    i = sub.add_parser("ingest", help="ingerir una fuente a bronze")
    i.add_argument("id")
    i.add_argument("--archivo", required=True, help="ruta al archivo ya descargado")
    i.add_argument("--permitir-no-verificada", action="store_true",
                   help="solo desarrollo: ignora que la fuente no esté verificada")
    i.set_defaults(func=cmd_ingest)

    b = sub.add_parser("build", help="construir capas").add_subparsers(
        dest="capa", required=True
    )
    bs = b.add_parser("silver")
    bs.add_argument("--source", default="deis_defunciones")
    bs.add_argument("--entrada", default=None, help="parquet de bronze; por defecto, el último")
    bs.set_defaults(func=cmd_build_silver)
    bg = b.add_parser("gold")
    bg.add_argument("--source", default="deis_defunciones")
    bg.add_argument("--poblacion", default=None,
                    help="CSV de población. Por defecto usa el silver de ine_proyecciones.")
    bg.add_argument("--agrupador", default="SUICIDIO")
    bg.add_argument("--k", type=int, default=10)
    bg.add_argument("--sin-reconciliar", action="store_true",
                    help="Salta la reconciliación. Solo para depurar: la salida NO es "
                         "publicable y el metadato lo declara.")
    bg.set_defaults(func=cmd_build_gold)

    _parser_rem(sub)

    r = sub.add_parser("run", help="pipeline de Fase 1 completo, en un comando")
    r.add_argument("--agrupador", default="SUICIDIO")
    r.add_argument("--k", type=int, default=10)
    r.add_argument("--forzar-descarga", action="store_true",
                   help="vuelve a bajar los archivos aunque estén en caché")
    r.set_defaults(func=cmd_run)

    q = sub.add_parser("qa", help="comprobaciones sin red")
    q.set_defaults(func=cmd_qa)

    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _log(getattr(args, "verbose", False))
    try:
        return args.func(args)
    except ObsmError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
