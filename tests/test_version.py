"""La versión del código tiene que ser la misma en los tres lugares que la declaran.

Existe por un defecto real: se etiquetó y publicó `v0.3.0` con el código todavía en
`0.2.0`, así que los trece archivos de ese release llevan `pipeline_version = "0.2.0"` —
el mismo valor que los de `v0.2.0`. Quien tenga uno de esos CSV en la mano **no puede
saber cuál de los dos releases lo produjo**, y eso contradice el no negociable de
`CLAUDE.md` §2.2 y la regla de `docs/07` de que `pipeline_version` viaja en cada fila
de `gold` para identificar el código.

El error no lo atrapó nada porque ningún test miraba la versión. Este sí.
"""

import re
import tomllib
from pathlib import Path

import obsm

RAIZ = Path(__file__).resolve().parents[1]


def _version_pyproject() -> str:
    with (RAIZ / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _versiones_publicadas() -> list[str]:
    """Versiones del CHANGELOG en orden de aparición, sin `[No publicado]`."""
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", texto, re.M)


def test_las_tres_declaraciones_coinciden():
    assert obsm.__version__ == obsm.PIPELINE_VERSION == _version_pyproject()


def test_la_version_del_codigo_es_la_ultima_publicada_del_changelog():
    """El CHANGELOG lista de más nueva a más antigua; la primera es la vigente.

    Si un release se etiqueta sin incrementar la versión, este test falla antes de que
    los datos salgan con un `pipeline_version` que no los identifica.
    """
    publicadas = _versiones_publicadas()
    assert publicadas, "el CHANGELOG no declara ninguna versión publicada"
    assert obsm.__version__ == publicadas[0], (
        f"el código dice {obsm.__version__} y la última versión publicada del CHANGELOG "
        f"es {publicadas[0]}. Incrementar la versión es parte de publicar, no un trámite "
        f"posterior: sin eso los datos salen con una procedencia que no los distingue."
    )


def test_el_changelog_va_de_mas_nueva_a_mas_antigua():
    def clave(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    publicadas = _versiones_publicadas()
    assert publicadas == sorted(publicadas, key=clave, reverse=True), (
        f"el CHANGELOG no está en orden descendente: {publicadas}"
    )


def test_no_hay_secciones_no_publicadas_bajo_una_publicada():
    """Una sección `[No publicado]` debajo de una versión publicada miente sobre qué salió.

    Pasó: el bloque «El denominador (cierre de Fase 2)» quedó marcado como no publicado
    estando debajo de `[0.3.0]`, cuando su contenido —`fonasa_inscritos`,
    `deis_establecimientos`, I-03— es exactamente lo que sostiene una de las series de
    ese release.
    """
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    encabezados = re.findall(r"^## \[([^\]]+)\]", texto, re.M)
    vistas_publicadas = False
    for h in encabezados:
        if re.fullmatch(r"\d+\.\d+\.\d+", h):
            vistas_publicadas = True
        elif vistas_publicadas:
            raise AssertionError(
                f"la sección [{h}] aparece después de una versión publicada. Lo no "
                f"publicado va arriba de todo; si ya salió, es parte de su release."
            )
