# Fixtures

**Todos los datos de esta carpeta son sintéticos.** No provienen de ninguna fuente real y
no deben citarse como si fueran cifras de Chile. Existen para probar el comportamiento del
código ante las estructuras y las patologías de formato que sí ocurren en las fuentes
reales: encoding Latin-1, separador `;`, filas de total mezcladas con el detalle, alias de
comuna, edades expresadas en meses, y comunas no resolubles.

Las poblaciones de `poblacion/poblacion_muestra.csv` son números plausibles inventados,
no proyecciones del INE.

Cuando se ingiera la fuente real, el fixture debe replicar su **estructura**, nunca sus
**registros**: las defunciones son datos individuales.
