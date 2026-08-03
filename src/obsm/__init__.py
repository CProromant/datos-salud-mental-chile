"""obsm — Observatorio de Salud Mental de Chile.

Motor de datos: consolida, normaliza y publica indicadores de salud mental
a partir de fuentes públicas. No es una herramienta clínica.
"""

#: Versión del código. Debe coincidir con `pyproject.toml` y con la versión publicada más
#: reciente del CHANGELOG; `tests/test_version.py` lo verifica.
#:
#: Estaba en `0.2.0` cuando se etiquetó y publicó `v0.3.0`: se olvidó el incremento, así que
#: los archivos de ese release llevan `pipeline_version = "0.2.0"` y el número no distingue
#: qué código los produjo. No se reescriben —serían datos distintos de los descargados— y el
#: caso queda declarado en el CHANGELOG.
__version__ = "0.3.0"
PIPELINE_VERSION = "0.3.0"
