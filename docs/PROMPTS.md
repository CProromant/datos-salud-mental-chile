# Playbook de sesiones con Claude Code

Prompts probados para las tareas recurrentes del proyecto. La forma importa: cada uno
declara el objetivo, las restricciones que ya están en `CLAUDE.md` (para que no se pierdan
en sesiones largas) y el criterio de término.

Regla general: **una sesión, una tarea con criterio de término verificable.** Las sesiones
que abarcan "avanza en el proyecto" producen cinco cosas a medias.

---

## 1. Verificar y promover una fuente (Fase 1, lo primero de todo)

```
Lee CLAUDE.md y docs/01-FUENTES.md.

Tarea: verificar la fuente `deis_defunciones`.
1. Descarga la página índice y encuentra los archivos reales de defunciones.
2. Descarga UN año, reporta: tamaño, encoding detectado, separador, columnas exactas,
   número de filas y un ejemplo de fila (con los campos sensibles ofuscados).
3. Compara las columnas reales contra MAPA_COLUMNAS en ingest/deis_defunciones.py y
   dime exactamente qué está mal en mi hipótesis.
4. NO edites sources.yml todavía: primero muéstrame la evidencia.

Restricción: no inventes URLs. Si no encuentras el archivo, dilo y muéstrame qué
intentaste.
```

## 2. Completar la tabla DPA

```
Lee config/territorio_comunas.README.md.

Tarea: completar config/territorio_comunas.csv con las 346 comunas desde la DPA oficial.
- Descarga la fuente oficial (INE o SUBDERE) y conviértela al esquema del CSV.
- No transcribas nada de memoria: si un dato no viene en el archivo descargado, no va.
- Al terminar corre `obsm territorio validar` y `make test`.
- Reporta: cuántas comunas, qué fuente exacta usaste, su fecha, y si algún nombre
  requiere un alias nuevo.

Criterio de término: `obsm territorio validar` termina en 0 y los tests de territorio
siguen pasando sin modificarlos.
```

## 3. Escribir un ingestor nuevo

```
Lee CLAUDE.md §7 (flujo "Agregar una fuente") y src/obsm/ingest/base.py.

Tarea: ingestor para <fuente>.
Sigue los 7 pasos del flujo en orden. Empieza por el fixture sintético que incluya
los casos feos: <lista los que ya conoces>.
No escribas el ingestor antes del fixture y del test.

Criterio de término: `make test` pasa, el ingestor falla con SchemaDriftError si le
quito una columna requerida, y docs/01-FUENTES.md tiene la ficha actualizada.
```

## 4. Parser de PDF de la Glosa 06

```
Lee docs/01-FUENTES.md, sección C1.

Tarea: extraer de <PDF> la tabla de lista de espera por especialidad.
- Usa pdfplumber. Si el layout no coincide con ninguno conocido, FALLA con un error
  claro en vez de devolver una tabla incompleta.
- Declara explícitamente qué layout detectaste.
- Reconcilia contra los totales impresos en el propio PDF (tolerancia 0,1%).
- Guarda el PDF como fixture solo si su licencia lo permite; si no, guarda una versión
  sintética con el mismo layout.

Criterio de término: los totales cuadran y hay un test que falla si cambia el layout.
```

## 5. Agregar un indicador

```
Lee docs/04-INDICADORES.md y CLAUDE.md §7.

Tarea: implementar <indicador>.
Antes de codificar, escribe la ficha completa, incluyendo la sección "qué NO significa".
Si no puedes escribir esa sección, el indicador no está bien definido todavía: dímelo
en vez de improvisarla.
El test debe usar un valor calculado a mano, no el output del propio código.
```

## 6. Depurar una serie que "se ve rara"

```
Lee CLAUDE.md §7 ("Arreglar un dato que se ve raro").

Observación: <describe la anomalía>.
NO la corrijas. Quiero, en este orden:
1. Reproducción mínima.
2. Tres hipótesis alternativas, incluyendo "el dato es correcto y el sistema
   efectivamente cambió".
3. Qué evidencia distinguiría entre ellas.
4. Una entrada propuesta para docs/05-CALIDAD.md#anomalias.
Recién después de eso decidimos si se toca algo.
```

## 7. Revisión previa a publicar

```
Lee docs/06-ETICA-Y-DATOS.md, sección 6.

Tarea: auditar <dataset> contra el checklist previo a publicar, punto por punto.
Para cada punto: cumple / no cumple / no aplica, con la evidencia (comando o celda).
No arregles nada: quiero el diagnóstico completo primero.
Si encuentras un incumplimiento del punto 3 (desglose por método), deténte y avísame
antes de seguir con el resto.
```

## 8. Auditoría de deuda del propio andamiaje

```
Lee docs/05-CALIDAD.md, "Pendientes de verificación heredados del andamiaje".

Tarea: tomar el pendiente <n>, verificarlo contra la fuente oficial y corregir el
código si corresponde. Reporta qué estaba bien y qué estaba mal en el supuesto
original, sin suavizarlo.
```

---

## Antipatrones observados

- **"Hazme el observatorio completo"** → produce quince archivos plausibles y ninguno
  verificado. El proyecto ya tiene el andamiaje; lo que falta es verificación contra
  fuentes reales, que es trabajo de a una.
- **"Arregla el test para que pase"** → los tests de territorio, CIE-10 y supresión son
  contratos. Si uno falla, el bug está en el código o en un supuesto, no en el test.
- **"Rellena los datos faltantes"** → nunca. Un hueco declarado es información; un hueco
  imputado en silencio es un error futuro.
- **"Agrega un dashboard bonito"** → está fuera de alcance hasta la Fase 5, y el alcance
  se discute antes de implementarse.
