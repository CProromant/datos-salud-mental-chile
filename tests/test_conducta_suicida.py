"""Tests de la tabla de ideación e intento suicida (I-05).

`docs/06` impone obligaciones a **toda** salida pública que incluya suicidio, y este es el
único módulo del proyecto que las hace cumplir por código en vez de por documentación.
Estos tests custodian esa puerta: si alguna vez pasan con los recursos de ayuda vacíos, la
regla dejó de existir.
"""

import pandas as pd
import pytest

from obsm.errors import SuppressionViolationError
from obsm.transform.gold import (
    PRIMER_PERIODO_CONDUCTA_SUICIDA,
    tabla_ideacion_intento,
)

AYUDA = ["Salud Responde — (pendiente de verificar en la fecha de publicación)"]


def _silver(filas):
    return pd.DataFrame(
        [
            {
                "comuna_cut": c,
                "periodo": p,
                "etiqueta_norm": e,
                "valor": v,
                "es_total_etario": True,
                "sexo": "ambos",
            }
            for c, p, e, v in filas
        ]
    )


class TestRecursosDeAyudaObligatorios:
    """La única regla de docs/06 que este proyecto hace cumplir en la firma de la función."""

    def test_sin_recursos_de_ayuda_no_produce_tabla(self):
        # No hay valor por defecto a propósito: un descuido no puede dejarlo pasar, y el
        # módulo no los inventa porque no le consta que estén vigentes hoy.
        with pytest.raises(SuppressionViolationError, match="recursos_ayuda"):
            tabla_ideacion_intento(
                _silver([("01101", "2025-12", "IDEACION", 100)]), recursos_ayuda=[]
            )

    def test_con_recursos_los_arrastra_al_metadato(self):
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "IDEACION", 100)]), recursos_ayuda=AYUDA, k=0
        )
        assert meta["recursos_ayuda"] == AYUDA

    def test_declara_la_revision_clinica_como_pendiente(self):
        # docs/06 la exige antes de publicar y ningún código puede sustituirla; lo que sí
        # puede es no dejar que se olvide.
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "IDEACION", 100)]), recursos_ayuda=AYUDA, k=0
        )
        assert "PENDIENTE" in meta["revision_clinica"]


class TestQuiebreDeSerie:
    """El REM no registraba estos conceptos antes de 2019-06."""

    def test_recorta_lo_anterior_al_quiebre(self):
        # Antes no son ceros: no existían en el formulario. Dejarlos publicaría un salto
        # de registro como si fuera un salto de conducta.
        g, meta = tabla_ideacion_intento(
            _silver(
                [
                    ("01101", "2018-12", "IDEACION", 0),
                    ("01101", "2019-06", "IDEACION", 40),
                    ("01101", "2025-12", "IDEACION", 100),
                ]
            ),
            recursos_ayuda=AYUDA,
            k=0,
        )
        assert g["periodo"].min() == PRIMER_PERIODO_CONDUCTA_SUICIDA
        assert meta["filas_anteriores_al_quiebre_descartadas"] == 1

    def test_el_quiebre_se_declara_en_las_advertencias(self):
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "IDEACION", 100)]), recursos_ayuda=AYUDA, k=0
        )
        assert any(PRIMER_PERIODO_CONDUCTA_SUICIDA in a for a in meta["advertencias"])


class TestLecturaSegura:
    """Las advertencias no son adorno: son el modo de fallo típico de este indicador."""

    def test_advierte_que_es_stock_y_no_eventos(self):
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "INTENTO", 50)]), recursos_ayuda=AYUDA, k=0
        )
        assert any("STOCK" in a for a in meta["advertencias"])

    def test_advierte_que_una_subida_no_es_mas_conducta_suicida(self):
        # Es la lectura equivocada más probable, y la que tiene consecuencias de política.
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "INTENTO", 50)]), recursos_ayuda=AYUDA, k=0
        )
        assert any("detección" in a for a in meta["advertencias"])

    def test_prohibe_rankear(self):
        _, meta = tabla_ideacion_intento(
            _silver([("01101", "2025-12", "INTENTO", 50)]), recursos_ayuda=AYUDA, k=0
        )
        assert any("rankear" in a for a in meta["advertencias"])


class TestSupresion:
    def test_suprime_bajo_k(self):
        g, _ = tabla_ideacion_intento(
            _silver(
                [
                    ("01101", "2025-12", "IDEACION", 3),
                    ("01107", "2025-12", "IDEACION", 40),
                    ("01401", "2025-12", "IDEACION", 900),
                ]
            ),
            recursos_ayuda=AYUDA,
            k=5,
        )
        por_comuna = g.set_index("comuna_cut")["personas"]
        assert pd.isna(por_comuna["01101"])
        assert por_comuna["01401"] == 900
