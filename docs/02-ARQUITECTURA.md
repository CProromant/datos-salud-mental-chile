# 02 — Arquitectura

## Principio

El pipeline separa **obtener** de **normalizar** de **calcular** de **publicar**, y cada
frontera tiene un contrato explícito. La razón no es purismo: es que cada capa se rompe por
motivos distintos y con frecuencias distintas. Los ingestores se rompen cuando la fuente
cambia (varias veces al año). La normalización se rompe cuando aparece una grafía nueva
(raro, pero silencioso). Los indicadores se rompen cuando alguien cambia una definición
(casi nunca, pero catastrófico). Mezclarlas hace que un cambio de formato de una planilla
obligue a revisar la definición de una tasa.

```
  fuente pública
        │  obsm ingest       (descarga, hash, manifiesto, contrato de esquema)
        ▼
  raw/     archivo tal como vino, inmutable, nunca versionado en git
        │
        ▼
  bronze/  tabla legible, columnas renombradas, tipos mínimos, marca de fila-total
        │  obsm build silver (territorio, edad, CIE-10)
        ▼
  silver/  grilla canónica: comuna_cut × período × dimensiones, multi-etiqueta CIE-10
        │  obsm build gold   (denominadores, tasas, suavizado, supresión, procedencia)
        ▼
  gold/    indicadores publicables + manifiesto + reporte de calidad
        │
        ▼
  publicación: parquet + csv + almacén DuckDB + sitio estático
```

## Qué puede y qué no puede hacer cada capa

| Capa | Puede | No puede |
|---|---|---|
| `ingest/` | descargar, leer, renombrar columnas, tipar, marcar filas de total | resolver comunas, clasificar CIE-10, calcular nada |
| `transform/silver` | normalizar territorio y edad, clasificar, descartar filas de total | tocar la red, decidir supresión, calcular tasas |
| `transform/gold` | unir denominadores, calcular tasas, suprimir, adjuntar procedencia | leer archivos crudos, inventar población faltante |
| `indicators/` | matemática pura sobre arrays | I/O de cualquier tipo |

La regla "sin I/O en `transform/` e `indicators/`" es lo que permite que la mayoría de los
tests corran en menos de un segundo y sin red.

## Contratos

**Contrato de ingesta.** Cada ingestor declara `columnas_requeridas`. Si faltan, lanza
`SchemaDriftError`. No hay fallback, no hay "intentar adivinar la columna parecida": una
fuente que cambió su esquema necesita revisión humana, no adaptación automática.

**Contrato de silver.** Toda tabla silver tiene, como mínimo: `comuna_cut` (5 dígitos,
string), `region_cut`, `anio` o `periodo`, y las columnas booleanas `es_<agrupador>`.

**Contrato de gold.** Toda tabla gold tiene `source_id`, `source_version`,
`poblacion_version`, `pipeline_version`, `fecha_calculo`, `preliminar` y `suprimido`.
`quality.verificar_politica_publicacion` corre antes de escribir.

## Almacén

Parquet como formato de archivo y DuckDB como motor de consulta sobre esos archivos. Por qué
no una base de datos servida: los volúmenes son modestos (millones de filas, no miles de
millones), el consumidor típico quiere un archivo descargable, y una base servida agrega
costo operacional permanente que un proyecto sin financiamiento asegurado no puede sostener.
La decisión está registrada en `docs/adr/0001-stack-minimo.md` junto con las condiciones que
la invalidarían.

## Idempotencia y reproducibilidad

- Un `raw` descargado no se sobreescribe: se identifica por hash. Si el hash cambia, es una
  nueva versión de la fuente y se guarda como tal.
- Correr el pipeline dos veces sobre el mismo `raw` produce el mismo `gold`, salvo el campo
  `fecha_calculo`. Hay un test de esto en la lista de pendientes de Fase 1.
- Las versiones de fuente y de denominador viajan en los datos, no en un README, para que un
  archivo suelto siga siendo interpretable dos años después.

## Ejecución programada

`refresh.yml` corre semanalmente en CI: verifica URLs, descarga lo que cambió, reconstruye y
compara contra el corte anterior. Si un indicador se mueve más allá de un umbral, abre un
issue. **Nunca publica automáticamente**: la última milla es humana por decisión, no por
falta de automatización.
