# Licencia de los datos derivados

Los conjuntos de datos publicados por este proyecto (todo lo que sale de la capa `gold`:
archivos CSV y Parquet, manifiestos, tablas de quiebres y reportes de calidad) se
distribuyen bajo **Creative Commons Atribución 4.0 Internacional (CC BY 4.0)**.

Texto completo: https://creativecommons.org/licenses/by/4.0/deed.es

## Qué se pide al reutilizar

**Atribución obligatoria** (requisito de la licencia): nombrar al proyecto, indicar la
versión del dataset y su DOI cuando exista, y señalar si se hicieron modificaciones.

```
Datos de Salud Mental de Chile (AAAA). <Nombre del dataset>, versión AAAA.MM.N.
DOI: 10.xxxx/zenodo.xxxxxxx. Licencia CC BY 4.0.
Elaborado a partir de datos de <fuente primaria>.
```

**Atribución a la fuente primaria** (requisito del proyecto, no de la licencia): toda
reutilización debe mencionar también el organismo de origen —DEIS/MINSAL, INE, DIPRES,
Superintendencia de Salud, según corresponda—. Este proyecto no genera datos primarios:
los limpia, los cruza y los documenta.

## Alcance y límites

- **Las fuentes primarias conservan sus propias condiciones.** La licencia CC BY 4.0 se
  aplica al trabajo de normalización, agregación y documentación de este proyecto, no a los
  datos originales de terceros. Antes de redistribuir un derivado de una fuente específica,
  revisar los términos del portal correspondiente (tarea registrada en `docs/01-FUENTES.md`).
- **No se publican datos personales.** Todo lo distribuido es agregado y sometido a
  supresión estadística según `docs/06-ETICA-Y-DATOS.md`.
- **Sin garantías.** Los datos se entregan tal como están. Pese al proceso de validación y
  reconciliación descrito en `docs/05-CALIDAD.md`, pueden contener errores. Las decisiones
  que se tomen a partir de ellos son responsabilidad de quien las toma.

## Por qué CC BY y no una licencia con restricciones

El proyecto rechaza ciertos usos (puntuación de riesgo individual, focalización comercial:
ver `USO-ACEPTABLE.md`). Esas restricciones **no están incorporadas a la licencia**, por
decisión consciente:

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
