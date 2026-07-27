# ADR 0004 — Licencias: MIT para el código, CC BY 4.0 para los datos, normas aparte

- Fecha: 2026-07-26
- Estado: **parcialmente superada** por [ADR 0005](0005-licencia-datos-sharealike.md)
  el 2026-07-27.

> **Qué cambió.** Los datos derivados ya no se publican bajo CC BY 4.0 sino bajo
> **CC BY-SA 4.0**, porque el INE —fuente del denominador de toda tasa— publica bajo
> CC BY-SA 4.0 y su cláusula ShareAlike obliga al derivado. Esta ADR razonó sobre lo que el
> proyecto quería permitir, sin considerar lo que las fuentes obligan; en su momento ninguna
> estaba verificada.
>
> **Qué sigue vigente:** el código bajo MIT, la decisión de no agregar cláusulas de uso a la
> licencia, y la separación entre licencia y `USO-ACEPTABLE.md`. El punto 2 de la
> justificación —rechazar CC BY-NC— también sigue en pie: CC BY-SA permite uso comercial.

## Contexto

El proyecto rechaza usos concretos de sus datos (puntuación de riesgo individual,
focalización comercial, rankings de comunas por suicidio). La tentación natural es
incorporarlos como condiciones de la licencia de datos.

## Decisión

Código bajo MIT. Datos derivados bajo CC BY 4.0 **sin cláusulas añadidas**. Los usos
rechazados viven en `USO-ACEPTABLE.md` como norma del proyecto.

## Justificación

1. Una licencia Creative Commons con restricciones agregadas deja de ser CC, y el resultado
   es un texto ambiguo que ningún repositorio de datos abiertos acepta y que nadie sabe
   cumplir con certeza.
2. CC BY-NC bloquearía usos legítimos (prensa, consultoría en política pública, docencia
   pagada) y dejaría al dataset fuera de los estándares de datos abiertos que el proyecto le
   reclama al Estado. Sería incoherente.
3. La protección real contra el uso más peligroso —riesgo individual— es que el dato
   publicado es agregado y suprimido, no una cláusula que nadie fiscalizaría.
4. Donde la restricción importa de verdad (detalle por método de suicidio) el mecanismo es
   contractual: acceso controlado con acuerdo de uso, que sí es exigible.

## Alternativa descartada

Licencia bespoke con restricciones de uso. Habría dado una falsa sensación de control a
cambio de perder interoperabilidad, indexación en catálogos de datos abiertos y capacidad de
reutilización académica.

## Consecuencia aceptada

Alguien puede usar los datos de una forma que el proyecto rechaza y estar dentro de la
licencia. La respuesta es pública y técnica, no legal.
