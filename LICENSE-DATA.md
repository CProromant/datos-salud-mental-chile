# Licencia de los datos derivados

Los conjuntos de datos publicados por este proyecto (todo lo que sale de la capa `gold`:
archivos CSV y Parquet, manifiestos, tablas de quiebres y reportes de calidad) se
distribuyen bajo **Creative Commons Atribución-CompartirIgual 4.0 Internacional
(CC BY-SA 4.0)**.

Texto completo: https://creativecommons.org/licenses/by-sa/4.0/deed.es

No es la licencia elegida por preferencia sino por herencia: el INE publica las proyecciones
de población —denominador de toda tasa del proyecto— bajo CC BY-SA 4.0, y su cláusula
CompartirIgual obliga al derivado. Se adopta la misma licencia y versión de la fuente para
que no exista pregunta de compatibilidad. El razonamiento completo está en
[ADR 0005](docs/adr/0005-licencia-datos-sharealike.md).

**Permite uso comercial.** CompartirIgual no es «no comercial»: se puede usar en prensa,
consultoría, docencia pagada y productos comerciales. Lo que exige es que el derivado se
distribuya bajo la misma licencia.

**El código sigue bajo MIT** (ver `LICENSE`) y la documentación narrativa bajo CC BY 4.0. La
obligación de CompartirIgual nace de incorporar material del INE; la documentación no lo
incorpora.

## Qué se pide al reutilizar

**Atribución obligatoria** (requisito de la licencia): nombrar al proyecto, indicar la
versión del dataset y su DOI cuando exista, y señalar si se hicieron modificaciones.

```
Datos de Salud Mental de Chile (AAAA). <Nombre del dataset>, versión AAAA.MM.N.
DOI: 10.xxxx/zenodo.xxxxxxx. Licencia CC BY-SA 4.0.
Elaborado a partir de datos de <fuente primaria>.
```

**CompartirIgual** (requisito de la licencia): si modificas o construyes sobre estos datos y
distribuyes el resultado, debe ir bajo CC BY-SA 4.0. Usarlos internamente, citarlos o
graficarlos en un artículo no obliga a nada de esto: la cláusula se activa al distribuir un
material adaptado.

**Atribución a la fuente primaria** (requisito del proyecto, no de la licencia): toda
reutilización debe mencionar también el organismo de origen —DEIS/MINSAL, INE, DIPRES,
Superintendencia de Salud, según corresponda—. Este proyecto no genera datos primarios:
los limpia, los cruza y los documenta.

## Alcance y límites

- **Las fuentes primarias conservan sus propias condiciones.** La licencia CC BY-SA 4.0 se
  aplica al trabajo de normalización, agregación y documentación de este proyecto, no a los
  datos originales de terceros. Antes de redistribuir un derivado de una fuente específica,
  revisar los términos del portal correspondiente (tarea registrada en `docs/01-FUENTES.md`).
- **No se publican datos personales.** Todo lo distribuido es agregado y sometido a
  supresión estadística según `docs/06-ETICA-Y-DATOS.md`.
- **Sin garantías.** Los datos se entregan tal como están. Pese al proceso de validación y
  reconciliación descrito en `docs/05-CALIDAD.md`, pueden contener errores. Las decisiones
  que se tomen a partir de ellos son responsabilidad de quien las toma.

## De dónde viene el CompartirIgual

Resuelto el 2026-07-27 en [ADR 0005](docs/adr/0005-licencia-datos-sharealike.md). Resumen:

Al verificar `ine_proyecciones` se leyeron los
[términos de datos abiertos del INE](https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos).
Son CC BY-SA 4.0: permiten uso comercial de forma explícita —el temor previo a una cláusula
no comercial era infundado para esta fuente— pero exigen CompartirIgual.

Como las proyecciones de población son el denominador de **toda** tasa del proyecto,
publicar `gold` bajo CC BY 4.0 arriesgaba incumplir la licencia de origen. Se descartó
sostener que una tasa no es obra derivada: puede ser cierto —los hechos no son objeto de
derecho de autor y Chile no tiene un derecho *sui generis* de bases de datos— pero deja el
cumplimiento apostado a una interpretación no probada, que no es posición para un proyecto
cuyo argumento central es la trazabilidad.

Se adoptó la licencia idéntica a la de la fuente, en vez de otra con CompartirIgual como
ODbL, para que no haya que argumentar compatibilidad entre licencias distintas.

## Estado de las licencias de las fuentes (investigado el 2026-07-27)

| Fuente | Licencia | Estado |
|---|---|---|
| `ine_proyecciones` | CC BY-SA 4.0 | verificada; es la que obliga al CompartirIgual |
| `deis_establecimientos` | **CC0** | verificada 2026-07-29 en `datos.gob.cl`. Dominio público: sin restricción de uso ni obligación de atribución |
| `dipres_ejecucion` | **CC0 / CC BY** | verificada 2026-07-29. Varía por corte: 65 datasets CC0 y 135 CC BY. Ambas compatibles con CC BY-SA |
| `deis_defunciones` | **sin declarar** | investigada sin resultado |
| `rem_salud_mental` | **sin declarar** | mismo portal que `deis_defunciones`, misma ausencia |
| `subdere_cut` | **sin declarar** | investigada; el CC-NC de SUBDERE cubre su cartografía, no esta planilla |
| `fonasa_inscritos` | **sin declarar** | SINIM no publica términos de uso |
| `fonasa_padron_aps` | **sin declarar** | idem |
| `ine_vitales_anuario` | CC BY-NC 2.0 | contradice los términos generales del INE; no alimenta `gold` |

**`deis_establecimientos` en CC0 cambia el argumento, no la conclusión.** Es la primera
fuente del proyecto con licencia libre declarada, y prueba que el MINSAL sí sabe declarar
licencia cuando decide hacerlo: la ausencia en `deis_defunciones` y en el REM es una omisión,
no una imposibilidad institucional. Eso vuelve razonable pedirla por escrito en vez de seguir
infiriéndola. La solicitud por Ley de Transparencia sigue pendiente.

**DEIS no declara licencia en ninguna parte.** Ni en `deis.minsal.cl` ni en
`repositoriodeis.minsal.cl`. En `datos.gob.cl` la evidencia es contradictoria y sobre otros
artefactos: el MINSAL central publicó «Defunciones por Semana Epidemiológica» como CC Zero,
mientras 41 datasets marcados CC-NC resultaron ser tablas resumidas de Servicios de Salud
regionales, no la microdata de causas.

**Por qué el proyecto publica igual.** No redistribuye ninguna de las dos fuentes: publica
indicadores agregados, calculados y con supresión estadística. Los hechos no son objeto de
derecho de autor y Chile no tiene derecho *sui generis* de bases de datos. Aun así, la
respuesta definitiva sería que DEIS conteste, y eso queda pendiente. Si contestara que su
microdata es no comercial habría que reabrir ADR 0005: esa obligación y la del INE serían
incompatibles entre sí, y no habría licencia que satisfaga a ambas.

Pendiente menor: `ine_vitales_anuario` está registrado como CC BY-NC 2.0, lo que contradice
los términos generales CC BY-SA 4.0 del mismo organismo. De ahí solo se usan dos cifras como
ancla de verificación y no se redistribuye el documento, así que no condiciona nada, pero
conviene aclararlo.

## Por qué no una licencia con restricciones de uso

El proyecto rechaza ciertos usos (puntuación de riesgo individual, focalización comercial:
ver `USO-ACEPTABLE.md`). Esas restricciones **no están incorporadas a la licencia**, por
decisión consciente. Vale tanto para la CC BY 4.0 original como para la CC BY-SA 4.0 actual:
lo que cambió con ADR 0005 fue la obligación heredada del INE, no la postura sobre agregar
cláusulas propias.

1. Agregar cláusulas a una licencia Creative Commons produce una licencia que ya no es CC y
   no puede llamarse así; el resultado es un texto ambiguo, difícil de cumplir y que ningún
   repositorio de datos abiertos acepta.
2. Una restricción de uso no comercial (CC BY-NC) bloquearía usos legítimos —prensa,
   consultoría en política pública, docencia pagada— y dejaría el dataset fuera de los
   estándares de datos abiertos, que es justamente lo que el proyecto reclama del Estado.
3. Los datos publicados son agregados y suprimidos: **no habilitan** la puntuación de riesgo
   individual aunque alguien lo intente. La protección real es el diseño del dato, no una
   cláusula.

Donde sí hay teeth es en el **acceso controlado**: el detalle por método de suicidio no se
publica y se comparte solo bajo acuerdo de uso firmado (ver `docs/adr/0003`). Ahí la
restricción es contractual y exigible, que es donde importa.
