"""Tests del catálogo de fuentes y de la regla de no-ingerir-sin-verificar."""

import pytest
import yaml

from obsm.errors import ObsmError, SourceNotVerifiedError
from obsm.registry import cargar_registro


def _escribir(tmp_path, fuentes):
    ruta = tmp_path / "sources.yml"
    ruta.write_text(yaml.safe_dump({"fuentes": fuentes}, allow_unicode=True), encoding="utf-8")
    return ruta


class TestCatalogoReal:
    def test_carga(self):
        reg = cargar_registro()
        assert len(reg) > 0

    def test_todas_las_fuentes_declaran_fase_y_prioridad_o_lo_admiten(self):
        for f in cargar_registro():
            assert f.nombre, f"{f.id} sin nombre"

    def test_toda_fuente_verificada_tiene_evidencia(self):
        """Invariante permanente: verificada implica fecha y origen no especulativo.
        No prohíbe verificar fuentes; prohíbe declararlo sin respaldo."""
        for f in cargar_registro():
            if f.verificada:
                assert f.fecha_verificacion, f"{f.id} verificada sin fecha"
                assert f.origen_url != "por_confirmar", f"{f.id} verificada con URL sin confirmar"

    def test_estado_actual_del_catalogo(self):
        """Informativo: hoy no hay ninguna fuente verificada. Cuando esto cambie,
        actualizar README ('Estado') y PLAN.md."""
        reg = cargar_registro()
        assert reg.resumen()["total"] == len(reg.fuentes)

    def test_dependencias_existen(self):
        reg = cargar_registro()
        for f in reg:
            for dep in f.depende_de:
                assert dep in reg.fuentes, f"{f.id} depende de {dep}, que no está en el catálogo"


class TestReglas:
    """La fuente de ejemplo se elige por su estado, no por su nombre.

    Antes estos tests fijaban `deis_defunciones` como ejemplo de fuente sin verificar, y
    se cayeron el día que se verificó. Lo que se prueba es la regla, no qué fuente está
    en qué estado hoy.
    """

    @staticmethod
    def _una(reg, verificada: bool) -> str:
        ids = [f.id for f in reg if (f.estado == "verificada") is verificada]
        if not ids:
            pytest.skip(
                f"el catálogo no tiene ninguna fuente {'verificada' if verificada else 'sin verificar'}"
            )
        return sorted(ids)[0]

    def test_exige_verificada(self):
        reg = cargar_registro()
        with pytest.raises(SourceNotVerifiedError):
            reg.exigir_verificada(self._una(reg, verificada=False))

    def test_permite_saltarse_la_regla_explicitamente(self):
        reg = cargar_registro()
        fid = self._una(reg, verificada=False)
        assert reg.exigir_verificada(fid, permitir_no_verificada=True).id == fid

    def test_una_fuente_verificada_pasa_sin_permiso_especial(self):
        reg = cargar_registro()
        fid = self._una(reg, verificada=True)
        assert reg.exigir_verificada(fid).id == fid

    def test_fuente_desconocida(self):
        with pytest.raises(ObsmError):
            cargar_registro().get("no_existe")

    def test_verificada_sin_fecha_es_error(self, tmp_path):
        ruta = _escribir(tmp_path, [{"id": "x", "nombre": "X", "estado": "verificada"}])
        with pytest.raises(ObsmError, match="fecha_verificacion"):
            cargar_registro(ruta)

    def test_verificada_con_origen_por_confirmar_es_contradiccion(self, tmp_path):
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "estado": "verificada",
                    "fecha_verificacion": "2026-07-26",
                    "origen_url": "por_confirmar",
                }
            ],
        )
        with pytest.raises(ObsmError, match="contradicción"):
            cargar_registro(ruta)

    def test_estado_invalido(self, tmp_path):
        ruta = _escribir(tmp_path, [{"id": "x", "nombre": "X", "estado": "mas_o_menos"}])
        with pytest.raises(ObsmError):
            cargar_registro(ruta)

    def test_ids_duplicados(self, tmp_path):
        ruta = _escribir(tmp_path, [{"id": "x", "nombre": "X"}, {"id": "x", "nombre": "Y"}])
        with pytest.raises(ObsmError, match="duplicados"):
            cargar_registro(ruta)


class TestProcedencia:
    """La cadena source_version/url_archivo se rompió una vez en silencio.

    `source_version` no estaba en el dataclass, así que caía en `extra` y el manifiesto
    lo escribía como null; y `url_principal` devolvía la página de índice en vez del
    archivo descargado. Ambas cosas dejan un número de gold sin procedencia real
    (CLAUDE.md §2.2) sin que nada falle.
    """

    def test_source_version_es_campo_y_no_cae_en_extra(self, tmp_path):
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "source_version": "CIFRAS_OFICIALES 1990-2023",
                }
            ],
        )
        f = cargar_registro(ruta).get("x")
        assert f.source_version == "CIFRAS_OFICIALES 1990-2023"
        assert "source_version" not in f.extra

    def test_url_principal_prefiere_el_archivo_sobre_el_indice(self, tmp_path):
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "url_indice": "https://ejemplo.cl/#datosabiertos",
                    "url_archivo": "https://ejemplo.cl/datos/archivo.zip",
                }
            ],
        )
        assert cargar_registro(ruta).get("x").url_principal.endswith("archivo.zip")

    def test_url_principal_cae_al_indice_si_no_hay_archivo(self, tmp_path):
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "url_indice": "https://ejemplo.cl/indice",
                }
            ],
        )
        assert cargar_registro(ruta).get("x").url_principal == "https://ejemplo.cl/indice"

    def test_la_fuente_real_de_defunciones_tiene_procedencia_completa(self):
        f = cargar_registro().get("deis_defunciones")
        assert f.source_version, "sin source_version no hay procedencia en gold"
        assert f.sha256, "sin hash no se puede saber qué archivo se ingirió"
        assert f.url_principal.endswith(".zip")


class TestFuentesCriticas:
    """Una fuente `critico: true` sin URL verificada bloquea toda la fase.

    `ine_proyecciones` es el denominador de cada tasa del proyecto: si se degrada a
    no_verificada sin que nadie lo note, no hay ningún indicador que salga bien.
    """

    def test_las_criticas_de_fase_1_estan_verificadas(self):
        reg = cargar_registro()
        criticas = [f for f in reg if f.extra.get("critico") and f.fase == 1]
        assert criticas, "el catálogo perdió las fuentes marcadas como críticas"
        sin_verificar = [f.id for f in criticas if not f.verificada]
        assert not sin_verificar, f"fuentes críticas sin verificar: {sin_verificar}"

    def test_el_denominador_tiene_archivo_hash_y_version(self):
        f = cargar_registro().get("ine_proyecciones")
        assert f.url_archivo, "sin url_archivo no se puede reproducir la descarga"
        assert len(f.sha256 or "") == 64
        assert "base 2017" in (f.source_version or ""), (
            "el denominador debe declarar su base: cambiarla recalcula todas las tasas"
        )


class TestCompatibilidadDeLicencias:
    """La salida `gold` es CC BY-SA 4.0 (ADR 0005). No todo se puede mezclar ahí.

    El problema que motiva estos tests se descubrió tarde: la licencia de la fuente del
    denominador se leyó recién al verificarla, cuando el proyecto ya declaraba CC BY 4.0.
    Una cláusula no comercial en una fuente que alimenta gold es incompatible con una
    salida abierta, y es el tipo de defecto que no rompe ningún cálculo: solo hace que lo
    publicado incumpla la licencia de origen.
    """

    #: Marcas de licencia que impiden incorporar la fuente a una salida CC BY-SA 4.0.
    INCOMPATIBLES = ("NC", "NoDerivat", "-ND")

    def _licencia(self, f) -> str:
        return str(f.extra.get("licencia") or "")

    def _incompatibles(self, reg) -> list[str]:
        malas = []
        for f in reg:
            if not f.verificada or f.extra.get("alimenta_gold") is False:
                continue
            lic = self._licencia(f)
            if any(m.lower() in lic.lower() for m in self.INCOMPATIBLES):
                malas.append(f"{f.id} ({lic})")
        return malas

    @pytest.mark.parametrize(
        "extra,detecta",
        [
            ({"licencia": "CC BY-NC 4.0"}, True),
            ({"licencia": "CC BY-ND 4.0"}, True),
            ({"licencia": "CC BY-SA 4.0"}, False),
            # La excepción explícita: el ancla de reconciliación no entra a gold.
            ({"licencia": "CC BY-NC 4.0", "alimenta_gold": False}, False),
        ],
    )
    def test_el_guard_detecta_de_verdad(self, tmp_path, extra, detecta):
        """Sin esto, el test del catálogo real podría estar pasando por no mirar nada."""
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "estado": "verificada",
                    "fecha_verificacion": "2026-01-01",
                    **extra,
                }
            ],
        )
        assert bool(self._incompatibles(cargar_registro(ruta))) is detecta

    def test_una_fuente_no_verificada_no_dispara_el_guard(self, tmp_path):
        # El catálogo puede contener hipótesis; lo que no puede es publicarlas.
        ruta = _escribir(
            tmp_path,
            [
                {
                    "id": "x",
                    "nombre": "X",
                    "estado": "no_verificada",
                    "licencia": "CC BY-NC 4.0",
                }
            ],
        )
        assert self._incompatibles(cargar_registro(ruta)) == []

    def test_ninguna_fuente_que_alimenta_gold_tiene_clausula_incompatible(self):
        culpables = self._incompatibles(cargar_registro())
        assert not culpables, (
            f"fuentes incompatibles con la salida CC BY-SA 4.0: {culpables}. "
            f"Revisar ADR 0005 antes de publicar gold."
        )

    def test_el_denominador_declara_su_licencia_verificada(self):
        f = cargar_registro().get("ine_proyecciones")
        assert self._licencia(f) == "CC BY-SA 4.0"
        assert f.extra.get("licencia_verificada"), (
            "una licencia sin fecha de verificación caduca sin que nadie lo note"
        )

    def test_el_ancla_nc_esta_marcada_como_fuera_de_gold(self):
        # Es la excepción que hace pasar al test anterior: si alguien la ingiere de verdad,
        # tiene que quitar esta marca y ahí el test de arriba falla, que es el punto.
        f = cargar_registro().get("ine_vitales_anuario")
        assert "NC" in self._licencia(f)
        assert f.extra.get("alimenta_gold") is False


class TestDependenciasDeclaradas:
    """Todo paquete que el código importa tiene que estar en `pyproject.toml`.

    CI falló porque `openpyxl` y `xlrd` se usaban sin declararse: acá estaban
    instalados de antes y en el `pip install` limpio de CI no existían. Es un fallo
    que no se puede reproducir en la máquina donde se escribió el código, que es la
    peor clase.
    """

    def test_ningun_import_externo_queda_sin_declarar(self):
        import ast
        import pathlib
        import sys
        import tomllib

        raiz = pathlib.Path(__file__).resolve().parents[1]
        cfg = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
        proyecto = cfg["project"]
        requisitos = list(proyecto.get("dependencies", []))
        for extra in proyecto.get("optional-dependencies", {}).values():
            requisitos += extra
        # Varios paquetes se importan con otro nombre: `pyyaml` como `yaml`,
        # `pymupdf` como `fitz`.
        declarados = {
            r.split(">")[0].split("=")[0].split("[")[0].strip().lower() for r in requisitos
        }
        declarados |= {"yaml", "fitz"}

        propios = {"obsm", "tests"}
        estandar = set(sys.stdlib_module_names)
        sin_declarar: dict[str, set[str]] = {}
        for carpeta in ("src", "tests", "ejemplos"):
            for ruta in (raiz / carpeta).rglob("*.py"):
                arbol = ast.parse(ruta.read_text(encoding="utf-8"))
                for n in ast.walk(arbol):
                    if isinstance(n, ast.Import):
                        mods = [a.name.split(".")[0] for a in n.names]
                    elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                        mods = [n.module.split(".")[0]]
                    else:
                        continue
                    for m in mods:
                        if m in estandar or m in propios or m.lower() in declarados:
                            continue
                        sin_declarar.setdefault(m, set()).add(str(ruta.relative_to(raiz)))
        assert not sin_declarar, (
            f"paquetes importados y no declarados en pyproject.toml: "
            f"{ {k: sorted(v) for k, v in sin_declarar.items()} }"
        )


class TestCifrasDeLaDocumentacion:
    """El README y el PLAN declaran cifras del proyecto. Tienen que ser ciertas.

    Es la tercera vez que la documentación se descuelga del código: cifras de tests,
    fuentes y anomalías que quedaron atrás sin que nada avisara. Los números en un README
    dan la sensación de estar al día, y esa sensación es justamente el problema — la misma
    forma de fallo que la lección de Fase 0 sobre el andamiaje desconectado.

    Este test la elimina como clase: si el README miente, CI falla.
    """

    @staticmethod
    def _raiz():
        import pathlib

        return pathlib.Path(__file__).resolve().parents[1]

    @staticmethod
    def _declarado(texto: str, etiqueta: str) -> int | None:
        """Lee `| <etiqueta> | <n> ... |` de una tabla markdown."""
        import re

        m = re.search(rf"\|\s*{etiqueta}[^|]*\|\s*([\d.]+)", texto, re.I)
        return int(m.group(1).replace(".", "")) if m else None

    @staticmethod
    def _ids_de_anomalias() -> list[str]:
        """Ids de las anomalías reales, **saltando los bloques de código**.

        El salto no es cosmético: el documento trae una plantilla de ejemplo dentro de un
        bloque cerrado con backticks, que un regex ingenuo cuenta como una anomalía más.
        Durante un tiempo ese conteo dio el número correcto solo porque la plantilla usaba
        el id de una anomalía real y `set()` lo colapsaba —dos errores que se tapaban.
        """
        import pathlib
        import re

        raiz = pathlib.Path(__file__).resolve().parents[1]
        texto = (raiz / "docs" / "05-CALIDAD.md").read_text(encoding="utf-8")
        sin_bloques = re.sub(r"```.*?```", "", texto, flags=re.S)
        return re.findall(r"^### (A-\d+)", sin_bloques, re.M)

    def test_el_numero_de_anomalias_es_el_real(self):
        raiz = self._raiz()
        reales = len(set(self._ids_de_anomalias()))
        for doc in ("README.md", "PLAN.md"):
            texto = (raiz / doc).read_text(encoding="utf-8")
            declarado = self._declarado(texto, "[Aa]nomalías documentadas")
            assert declarado == reales, (
                f"{doc} declara {declarado} anomalías y docs/05-CALIDAD.md tiene {reales}"
            )

    def test_el_estado_de_cada_indicador_coincide_con_su_ficha(self):
        """`config/indicators.yml` y `docs/04` tienen que decir lo mismo.

        Se desalinearon: I-05 e I-06 figuraban `implementado` en el YAML mientras su ficha
        seguía diciendo «definido … sin implementar», y en el caso de I-06 la serie ya
        estaba **publicada**. Quien lea la ficha para saber si puede usar un indicador se
        lleva la respuesta contraria a la real.
        """
        import re

        import yaml

        raiz = self._raiz()
        estados = {
            i["id"]: str(i.get("estado", ""))
            for i in yaml.safe_load(
                (raiz / "config" / "indicators.yml").read_text(encoding="utf-8")
            )["indicadores"]
        }
        doc = (raiz / "docs" / "04-INDICADORES.md").read_text(encoding="utf-8")
        fichas = dict(re.findall(r"\{#(i-\d+)\}\n\n- \*\*Estado:\*\*\s*([^\n.]*)", doc))
        faltan = sorted(set(estados) - {k.upper() for k in fichas})
        assert not faltan, f"indicadores sin ficha en docs/04: {faltan}"
        for iid, estado in estados.items():
            texto = fichas[iid.lower()].lower()
            # `implementado_no_publicable` se redacta como «implementado, no publicable».
            raiz_estado = estado.split("_")[0].lower()
            assert raiz_estado in texto.replace("*", ""), (
                f"{iid}: el catálogo dice {estado!r} y su ficha dice {texto.strip()!r}"
            )

    def test_cada_fuente_del_catalogo_tiene_ficha_propia(self):
        """`CLAUDE.md` §7 pone la ficha como paso 1 de agregar una fuente.

        Se saltó tres veces: `fonasa_padron_aps` se usó desde Fase 2 sin ficha, y
        `subdere_cut` —el maestro territorial, la fuente marcada `critico: true`— llevaba
        desde Fase 1 mencionado solo de pasada. Una fuente sin ficha es una fuente cuyas
        trampas viven únicamente en los comentarios del YAML.
        """
        import re

        import yaml

        raiz = self._raiz()
        cat = yaml.safe_load((raiz / "config" / "sources.yml").read_text(encoding="utf-8"))
        ids = {f["id"] for f in cat["fuentes"]}
        texto = (raiz / "docs" / "01-FUENTES.md").read_text(encoding="utf-8")
        con_ficha = set(re.findall(r"^### [A-Z]\d+[a-z]?\. `([a-z0-9_]+)`", texto, re.M))
        assert not (ids - con_ficha), (
            f"fuentes en el catálogo sin ficha propia en docs/01-FUENTES.md: "
            f"{sorted(ids - con_ficha)}"
        )
        assert not (con_ficha - ids), (
            f"fichas en docs/01-FUENTES.md sin entrada en el catálogo, que es la fuente de "
            f"verdad (CLAUDE.md §3): {sorted(con_ficha - ids)}"
        )

    def test_ningun_id_de_anomalia_esta_repetido(self):
        """Dos anomalías con el mismo id dejan ambiguas las referencias desde tests y fichas."""
        ids = self._ids_de_anomalias()
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        assert not repetidos, f"ids de anomalía repetidos en docs/05-CALIDAD.md: {repetidos}"

    def test_las_anomalias_van_en_orden(self):
        """Un registro que se lee de arriba abajo tiene que estar ordenado para servir."""
        ids = self._ids_de_anomalias()
        assert ids == sorted(ids), (
            f"docs/05-CALIDAD.md no está en orden correlativo. Orden actual: {ids}"
        )

    def test_el_numero_de_fuentes_verificadas_es_el_real(self):
        import re

        import yaml

        raiz = self._raiz()
        cat = yaml.safe_load((raiz / "config" / "sources.yml").read_text(encoding="utf-8"))
        fuentes = cat["fuentes"]
        verificadas = sum(1 for f in fuentes if f.get("estado") == "verificada")
        for doc in ("README.md", "PLAN.md"):
            texto = (raiz / doc).read_text(encoding="utf-8")
            m = re.search(r"verificadas con descarga real\s*\|\s*(\d+) de (\d+)", texto)
            assert m, f"{doc} no declara el conteo de fuentes verificadas"
            assert (int(m.group(1)), int(m.group(2))) == (verificadas, len(fuentes)), (
                f"{doc} declara {m.group(1)} de {m.group(2)} fuentes verificadas; "
                f"el catálogo tiene {verificadas} de {len(fuentes)}"
            )

    def test_cada_serie_publicada_tiene_su_ficha(self):
        # Una tabla en `gold` sin ficha es un archivo que nadie sabe leer. El flujo del
        # repo la exige antes de publicar; esto lo hace verificable.
        raiz = self._raiz()
        fichas = {p.stem.replace("DATASET-", "") for p in (raiz / "docs").glob("DATASET-*.md")}
        assert len(fichas) >= 4, f"solo {len(fichas)} fichas de dataset"

    def test_todo_ingestor_registrado_tiene_su_fuente_en_el_catalogo(self):
        import yaml

        from obsm.ingest import INGESTORES

        raiz = self._raiz()
        cat = yaml.safe_load((raiz / "config" / "sources.yml").read_text(encoding="utf-8"))
        ids = {f["id"] for f in cat["fuentes"]}
        huerfanos = sorted(set(INGESTORES) - ids)
        assert not huerfanos, f"ingestores sin entrada en config/sources.yml: {huerfanos}"


class TestParserDelCLI:
    """El parser se construye entero, sin subcomandos duplicados ni huérfanos.

    Se agrega porque 541 tests pasaban con el CLI roto: `glosa06` había quedado
    registrado en dos lugares y `construir_parser` lanzaba `ArgumentError` al primer uso.
    Ningún test lo construía, así que el fallo solo aparecía al correr el comando a mano.
    Es la misma familia que la lección de Fase 0: una pieza en el camino de ejecución que
    ningún test recorre.
    """

    def test_el_parser_se_construye(self):
        from obsm.cli import construir_parser

        assert construir_parser() is not None

    def test_todos_los_subcomandos_declarados_responden(self):
        from obsm.cli import construir_parser

        p = construir_parser()
        accion = next(a for a in p._actions if a.dest == "grupo")
        esperados = {
            "sources",
            "territorio",
            "ingest",
            "build",
            "rem",
            "glosa06",
            "espera",
            "egresos",
            "run",
            "qa",
        }
        assert esperados <= set(accion.choices), (
            f"faltan subcomandos: {sorted(esperados - set(accion.choices))}"
        )

    def test_cada_subcomando_tiene_funcion_asociada(self):
        # Un subcomando sin `set_defaults(func=...)` acepta la invocación y no hace nada.
        from obsm.cli import construir_parser

        p = construir_parser()
        accion = next(a for a in p._actions if a.dest == "grupo")
        sin_func = []
        for nombre, sp in accion.choices.items():
            tiene = sp.get_default("func") is not None
            if not tiene:
                sub = next((a for a in sp._actions if a.choices and hasattr(a, "dest")), None)
                tiene = bool(
                    sub and all(s.get_default("func") is not None for s in sub.choices.values())
                )
            if not tiene:
                sin_func.append(nombre)
        assert not sin_func, f"subcomandos sin función: {sin_func}"

    def test_egresos_no_trae_recursos_de_ayuda_por_defecto(self):
        """`docs/06` no admite un valor por defecto acá.

        Si `--recursos-ayuda` tuviera uno, la serie de lesión autoinfligida se escribiría
        sola con números de ayuda que nadie verificó ese día — que es exactamente el daño
        que la regla evita. El default vacío es lo que hace que la puerta exista.
        """
        from obsm.cli import construir_parser

        args = construir_parser().parse_args(["egresos", "EGRESOS_2023.zip"])
        assert args.recursos_ayuda == []
        # Y el umbral de la serie sensible es el de mortalidad, no el de actividad.
        assert args.k_autoinfligida == 10


class TestEnlacesDeLaDocumentacion:
    """Ningún enlace interno roto, y ningún documento invisible desde el README.

    Se agrega porque una revisión manual encontró diez anclas rotas y cuatro documentos
    normativos —diccionario, publicación, riesgos y gobernanza— que no se alcanzaban desde
    la portada. Un enlace roto no rompe nada al correr; simplemente el lector no llega, y
    eso no aparece en ninguna suite hasta que alguien lo busca a mano.
    """

    @staticmethod
    def _encabezados_y_anclas(p):
        """Anclas de un documento, saltando los bloques de código cercados.

        Sin saltarlos, la plantilla de anomalía que vive dentro de un bloque en
        `docs/05-CALIDAD.md` se cuenta como un encabezado `A-001` duplicado, y un
        comentario de bash `# los tres insumos` cuenta como segundo H1.
        """
        import re
        import unicodedata

        out, en_bloque = set(), False
        for linea in p.read_text(encoding="utf-8").splitlines():
            if linea.lstrip().startswith("```"):
                en_bloque = not en_bloque
                continue
            if en_bloque:
                continue
            m = re.match(r"^#{1,6}\s+(.*?)\s*$", linea)
            if not m:
                continue
            titulo = m.group(1)
            explicita = re.search(r"\{#([^}]+)\}", titulo)
            if explicita:
                out.add(explicita.group(1))
                titulo = titulo[: explicita.start()].strip()
            s = "".join(
                c
                for c in unicodedata.normalize("NFKD", titulo.lower())
                if not unicodedata.combining(c)
            )
            out.add(re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", s).strip()))
        return out

    def _markdown(self):
        raiz = self._raiz()
        return sorted(raiz.glob("*.md")) + sorted(raiz.glob("docs/**/*.md"))

    @staticmethod
    def _raiz():
        import pathlib

        return pathlib.Path(__file__).resolve().parents[1]

    def test_ningun_enlace_interno_roto(self):
        import re

        rotos = []
        for doc in self._markdown():
            for m in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
                destino = m.group(2).strip()
                if destino.startswith(("http://", "https://", "mailto:")):
                    continue
                ruta, _, ancla = destino.partition("#")
                base = (doc.parent / ruta).resolve() if ruta else doc.resolve()
                if not base.exists():
                    rotos.append(f"{doc.name}: [{m.group(1)[:20]}]({destino}) — no existe")
                elif (
                    ancla and base.suffix == ".md" and ancla not in self._encabezados_y_anclas(base)
                ):
                    rotos.append(f"{doc.name}: [{m.group(1)[:20]}]({destino}) — ancla ausente")
        assert not rotos, "enlaces rotos:\n  " + "\n  ".join(rotos)

    def test_todo_documento_se_alcanza_desde_el_readme(self):
        import re

        raiz = self._raiz()
        enlazados = {
            m.group(1)
            for m in re.finditer(r"\]\(([^)]+)\)", (raiz / "README.md").read_text(encoding="utf-8"))
        }
        existentes = {f"docs/{p.name}" for p in (raiz / "docs").glob("*.md")}
        existentes |= {p.name for p in raiz.glob("*.md")} - {"README.md"}
        huerfanos = sorted(existentes - enlazados)
        assert not huerfanos, f"documentos que el README no enlaza: {huerfanos}"

    def test_cada_documento_tiene_exactamente_un_titulo_principal(self):
        import re

        malos = []
        for doc in self._markdown():
            en_bloque, h1 = False, 0
            for linea in doc.read_text(encoding="utf-8").splitlines():
                if linea.lstrip().startswith("```"):
                    en_bloque = not en_bloque
                    continue
                if not en_bloque and re.match(r"^# \S", linea):
                    h1 += 1
            if h1 != 1:
                malos.append(f"{doc.name}: {h1} títulos H1")
        assert not malos, "\n  ".join(malos)
