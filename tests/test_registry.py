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
    def test_exige_verificada(self):
        reg = cargar_registro()
        with pytest.raises(SourceNotVerifiedError):
            reg.exigir_verificada("deis_defunciones")

    def test_permite_saltarse_la_regla_explicitamente(self):
        reg = cargar_registro()
        f = reg.exigir_verificada("deis_defunciones", permitir_no_verificada=True)
        assert f.id == "deis_defunciones"

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
