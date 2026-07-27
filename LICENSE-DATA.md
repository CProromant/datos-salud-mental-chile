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

## DECISIÓN ABIERTA — ShareAlike del INE (bloquea la primera publicación)

Detectado el 2026-07-27 al verificar `ine_proyecciones`. **No está resuelto y bloquea la
publicación de cualquier tasa.**

Los [términos de datos abiertos del INE](https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos)
son **CC BY-SA 4.0**. La buena noticia es que permiten uso comercial de forma explícita
—«para cualquier finalidad, incluso comercial»—, así que la preocupación anterior sobre una
cláusula NC era, para esta fuente, infundada. El problema es otro: **ShareAlike**. Quien
modifica el material «deberá difundir sus contribuciones bajo la misma licencia que el
original».

Las proyecciones de población del INE son el denominador de **toda** tasa del proyecto. Si el
`gold` derivado cuenta como obra adaptada, debe salir bajo CC BY-SA 4.0, y publicarlo bajo
CC BY 4.0 —como declara este documento— incumpliría la licencia de la fuente.

Que sea o no «obra adaptada» no es evidente y no se resuelve leyendo la licencia:

- Los hechos y datos no son objeto de derecho de autor, y Chile no tiene un derecho *sui
  generis* de bases de datos como el europeo. Una tasa calculada a partir de una población
  es un hecho nuevo, no una adaptación del cuadro del INE.
- Pero si se redistribuye la tabla de población —aunque sea reordenada a formato largo— eso
  sí es distribuir el material, y ahí SA aplica sin discusión.

Opciones, con recomendación:

1. **Publicar `gold` bajo CC BY-SA 4.0.** Es la salida limpia: compatible con el INE, mantiene
   el uso comercial y sigue siendo una licencia abierta estándar. Costo: la SA se contagia a
   quien reutilice, lo que algunos reutilizadores evitan. **Recomendada.**
2. Mantener CC BY 4.0 y no redistribuir nunca la tabla de población, publicando solo
   indicadores calculados. Más frágil: depende de sostener que la tasa no es obra derivada.
3. Licencia mixta: documentación y código bajo sus licencias actuales, datasets bajo
   CC BY-SA 4.0.

Mientras no se decida, **no publicar datasets `gold` que usen `ine_proyecciones` como
denominador**. La decisión es del proyecto, no técnica, y conviene tomarla antes de la
primera publicación: cambiar la licencia después de que alguien reutilizó el dato es mucho
más caro que elegirla ahora.

Pendiente relacionado: `ine_vitales_anuario` está registrado como CC BY-NC 2.0, lo que
contradice los términos generales CC BY-SA 4.0 del mismo organismo. No se pudo determinar
cuál rige para ese PDF. El riesgo práctico es bajo —de ahí solo se usan dos cifras como
ancla de verificación y no se redistribuye el documento—, pero conviene aclararlo con el INE.

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
