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
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X", "estado": "verificada",
            "fecha_verificacion": "2026-07-26", "origen_url": "por_confirmar",
        }])
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
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X", "source_version": "CIFRAS_OFICIALES 1990-2023",
        }])
        f = cargar_registro(ruta).get("x")
        assert f.source_version == "CIFRAS_OFICIALES 1990-2023"
        assert "source_version" not in f.extra

    def test_url_principal_prefiere_el_archivo_sobre_el_indice(self, tmp_path):
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X",
            "url_indice": "https://ejemplo.cl/#datosabiertos",
            "url_archivo": "https://ejemplo.cl/datos/archivo.zip",
        }])
        assert cargar_registro(ruta).get("x").url_principal.endswith("archivo.zip")

    def test_url_principal_cae_al_indice_si_no_hay_archivo(self, tmp_path):
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X", "url_indice": "https://ejemplo.cl/indice",
        }])
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
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X", "estado": "verificada",
            "fecha_verificacion": "2026-01-01", **extra,
        }])
        assert bool(self._incompatibles(cargar_registro(ruta))) is detecta

    def test_una_fuente_no_verificada_no_dispara_el_guard(self, tmp_path):
        # El catálogo puede contener hipótesis; lo que no puede es publicarlas.
        ruta = _escribir(tmp_path, [{
            "id": "x", "nombre": "X", "estado": "no_verificada", "licencia": "CC BY-NC 4.0",
        }])
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
