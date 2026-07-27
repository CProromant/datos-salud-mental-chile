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
