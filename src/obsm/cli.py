"""CLI de obsm. Uso: `obsm <grupo> <accion> [...]` o `python -m obsm.cli ...`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .errors import ObsmError
from .registry import cargar_registro, verificar_urls
from .territorio import N_COMUNAS_ESPERADO, cargar_dpa, validar_dpa


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
    print("\nNota: `obsm qa` no reemplaza `make test`. Corre ambos antes de publicar.")
    return 1 if fallos else 0


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
        print(f"ERROR: no existe {ruta}. En este entorno no hay red hacia dominios de "
              f"gobierno: descarga el archivo aparte y pásalo con --archivo.", file=sys.stderr)
        return 1
    df, manifiesto = INGESTORES[args.id](fuente).ingerir(ruta)
    print(f"bronze escrito: {len(df)} filas | sha256={manifiesto.sha256[:12]}… "
          f"| encoding={manifiesto.encoding}")
    return 0


def cmd_build_silver(args) -> int:
    import pandas as pd

    from .io import ruta_capa
    from .transform.silver import normalizar_defunciones

    entrada = Path(args.entrada) if args.entrada else None
    if entrada is None:
        dir_bronze = ruta_capa("bronze", args.source, "x").parent
        candidatos = sorted(dir_bronze.glob("*.parquet"))
        if not candidatos:
            print(f"ERROR: no hay bronze para {args.source}. Corre `obsm ingest` primero.",
                  file=sys.stderr)
            return 1
        entrada = candidatos[-1]
    bronze = pd.read_parquet(entrada)
    silver, reporte = normalizar_defunciones(bronze)
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

    from .io import ruta_capa
    from .transform.gold import tasas_comunales
    from .transform.silver import agregar_defunciones

    dir_silver = ruta_capa("silver", args.source, "x").parent
    candidatos = sorted(dir_silver.glob("*.parquet"))
    if not candidatos:
        print(f"ERROR: no hay silver para {args.source}.", file=sys.stderr)
        return 1
    silver = pd.read_parquet(candidatos[-1])
    poblacion = pd.read_csv(args.poblacion, dtype={"comuna_cut": str})
    agregado = agregar_defunciones(silver, args.agrupador, dimensiones=["comuna_cut", "anio"])
    gold, meta = tasas_comunales(
        agregado, poblacion, args.agrupador, source_id=args.source, k=args.k
    )
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
    bg.add_argument("--poblacion", required=True, help="CSV con comuna_cut, anio, poblacion")
    bg.add_argument("--agrupador", default="SUICIDIO")
    bg.add_argument("--k", type=int, default=10)
    bg.set_defaults(func=cmd_build_gold)

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
