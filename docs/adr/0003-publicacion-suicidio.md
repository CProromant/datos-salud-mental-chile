# ADR 0003 — Publicación de datos de suicidio: agrupador sí, método nunca

- Fecha: 2026-07-26
- Estado: aceptada
- Relacionada con: docs/06-ETICA-Y-DATOS.md

## Contexto

La base de defunciones permite desagregar suicidio por subcódigo X60–X84, es decir, por
método. Analíticamente eso tiene valor: la restricción de medios es una de las
intervenciones preventivas con mejor evidencia, y diseñarla requiere saber qué métodos
predominan.

## Decisión

El detalle por método **no se publica**, en ningún nivel de agregación. Se calcula y se
conserva internamente, y se comparte solo bajo solicitud fundada de una institución con
mandato de prevención, con acuerdo de uso.

Implementado en código: `cie10.es_publicable(..., nivel_detalle="codigo")` devuelve `False`
y `quality.verificar_politica_publicacion` rechaza cualquier tabla que desglose el
agrupador por código.

## Justificación

La difusión detallada de métodos está asociada a efectos de imitación. El beneficio
analítico se conserva por la vía del acceso controlado; el riesgo se elimina por la vía de
no publicarlo abiertamente. La asimetría es clara: el costo de no publicar es que un
investigador tenga que pedirlo; el costo de publicar es potencialmente irreversible.

## Alternativas descartadas

- **Publicar con advertencia**: la advertencia no controla quién lo reutiliza ni cómo.
- **Publicar solo a nivel nacional**: sigue siendo un desglose de métodos difundido.
- **Publicar agrupando métodos en categorías amplias**: reduce el riesgo pero no lo elimina,
  y la ganancia analítica sobre el acceso controlado es marginal.

## Consecuencias

Un investigador que necesite el detalle debe solicitarlo. Es una fricción deliberada.
