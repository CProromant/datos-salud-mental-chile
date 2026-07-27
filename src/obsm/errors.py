"""Errores de dominio. Nunca usar Exception genérica en el pipeline."""


class ObsmError(Exception):
    """Base de todos los errores del observatorio."""


class SourceUnavailableError(ObsmError):
    """La fuente no respondió, cambió de URL o devolvió un estado no esperado."""


class SourceNotVerifiedError(ObsmError):
    """Se intentó ingerir una fuente cuya URL no ha sido verificada. Ver CLAUDE.md §2.1."""


class SchemaDriftError(ObsmError):
    """El archivo descargado no cumple el contrato de esquema declarado.

    Se lanza a propósito en vez de adaptarse en silencio: adaptarse en silencio
    es como se publican series rotas.
    """


class ReconciliationError(ObsmError):
    """El total calculado no cuadra con el ancla oficial dentro de la tolerancia."""


class SuppressionViolationError(ObsmError):
    """Se intentó publicar una tabla que viola la política de supresión o de método."""


class TerritorioError(ObsmError):
    """No se pudo resolver una comuna o región a su código canónico."""
