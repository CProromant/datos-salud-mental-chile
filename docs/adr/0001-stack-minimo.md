# ADR 0001 — Stack mínimo: archivos, Parquet y DuckDB

- Fecha: 2026-07-26
- Estado: aceptada

## Contexto

El proyecto no tiene financiamiento asegurado ni equipo de operaciones. Los volúmenes son
del orden de millones de filas. El consumidor típico (asesor legislativo, investigador,
Servicio de Salud) quiere un archivo descargable y reproducible.

## Decisión

Parquet como formato, DuckDB como motor de consulta sobre esos archivos, publicación como
sitio estático. Sin base de datos servida, sin backend, sin autenticación.

## Consecuencias

Positivas: costo operacional cercano a cero, reproducibilidad trivial, el dato publicado es
el mismo objeto que se consulta, resistencia al abandono (los archivos sobreviven aunque el
proyecto se detenga).

Negativas: sin escritura concurrente, sin consultas en vivo sobre datos que cambian, sin
control de acceso por usuario.

## Cuándo revisar

Si aparece un consumidor que necesita consultas interactivas sobre decenas de millones de
filas, o si un organismo requiere control de acceso. Ninguna de las dos condiciones se
cumple hoy, y adelantarse a ellas es la forma más común de matar un proyecto pequeño.
