# ADR 0002 — Marco territorial vigente como marco principal

- Fecha: 2026-07-26
- Estado: aceptada

## Contexto

La creación de la región de Ñuble en 2018 traslada 21 comunas desde Biobío. Cualquier serie
regional larga cruza esa frontera. Hay dos marcos posibles: el histórico (cada año con la
división vigente entonces) y el actual (recodificar todo el pasado al mapa de hoy).

## Decisión

El marco **actual** es el principal: toda serie comunal y regional se publica bajo la
división vigente. Se conserva `region_vigente(comuna, anio)` para reconstruir el marco
histórico cuando haya que reconciliar contra publicaciones antiguas.

## Justificación

El uso dominante es comparar territorios en el tiempo para decidir dónde poner recursos hoy.
Bajo el marco histórico, Biobío exhibe un salto artificial en 2018 que ninguna nota al pie
logra evitar que se lea como cambio real.

## Consecuencias

Las cifras regionales anteriores a 2018 no coincidirán con las publicaciones oficiales de la
época. Esto se declara en la tabla de quiebres y en cada nota metodológica, y la función de
reconciliación permite demostrar la equivalencia.
