# Dataset: espera por especialidad médica, incluida psiquiatría

Este documento acompaña a `espera_por_especialidad.csv`. Léelo antes de usarlo: **la cifra
es nacional** y **la serie tiene solo los trimestres cuyo PDF se pudo conseguir**.

- **Versión del dataset:** `2026.07.4` — el código que lo produjo es `v0.2.0`
- **Licencia:** CC BY-SA 4.0 — ver `LICENSE-DATA.md`.
- **Cobertura:** 75 especialidades × 2 trimestres (2025-09 y 2026-03). 128 filas.
- **Fuente:** informe trimestral de la Glosa 06, Ley de Presupuestos, Partida 16.
  MINSAL, Subsecretaría de Redes Asistenciales.

## Qué contiene

**La única cifra pública que aísla cuánta gente espera por psiquiatría en Chile.**

| Trimestre | Psiquiatría adulta | Psiquiatría infanto-adolescente |
|---|---|---|
| al 30-09-2025 | **22.963** | **13.960** |
| al 31-03-2026 | **23.134** | **12.585** |

Más de 35.000 personas esperando un psiquiatra en el sistema público, y el dato solo existe
dentro de un PDF de 55 páginas que se publica cada tres meses.

| Columna | Qué es |
|---|---|
| `periodo` | Trimestre en ISO, con el **mes de cierre**: `2025-09` es el corte al 30 de septiembre. |
| `especialidad_fuente` | La especialidad tal como la escribe el informe. |
| `especialidad_norm` | Normalizada. **Úsala para filtrar y unir**, no la anterior. |
| `etiqueta` | Nombre canónico, solo para las de salud mental. |
| `es_salud_mental` | `True` en psiquiatría adulta e infanto-adolescente. |
| `registros` | Interconsultas en espera. **Vacío si fue suprimido.** |
| `unidad_territorial` | Siempre `nacional`. |
| `source_id`, `source_version`, `pipeline_version`, `fecha_calculo` | Procedencia. |

## Cómo leerlo sin equivocarse

### 1. La cifra es nacional, y no hay forma de bajarla a territorio

El informe **no cruza especialidad con Servicio de Salud**. Publica una tabla de días de
espera por Servicio con todas las especialidades sumadas, y otra de registros por
especialidad a nivel país. Las dos dimensiones nunca aparecen juntas.

**No se puede decir cuánto se espera por psiquiatría en una región.** Y no es que el dato
no exista: la letra b) de la propia Glosa 06 obliga a publicar «una tabla desglosada por
cada una de las especialidades, que incluya (…) el promedio y la mediana de días de
espera». El informe entrega solo los registros.

El complemento parcial es [`listas_espera_servicio_salud.csv`](DATASET-listas-espera-servicio-salud.md),
que sí tiene días por Servicio — pero de todas las especialidades juntas.

### 2. «Registros» no es «personas»

Una persona puede tener varias interconsultas en espera. El informe lo explicita y este
dataset lo repite: los 23.134 de psiquiatría adulta son interconsultas, no pacientes
distintos.

### 3. El reloj parte en la interconsulta

La espera se cuenta desde que un profesional emite la derivación, no desde que la persona
empezó a necesitar atención. Subestima la espera vivida.

### 4. No calcules participaciones con esta tabla

El informe del **primer trimestre de 2026 no suma su propio total declarado**: la tabla da
1.970.175 registros y el informe declara 1.981.653. Faltan 11.478, un 0,58 %.

Verificado línea por línea que el parser captura todo lo que hay en el texto; el hueco está
en el informe. El de 2025 sí cuadra exacto (2.051.482 = 2.051.482).

Consecuencia práctica: **un «psiquiatría es el X % de la lista de espera» calculado sobre
este denominador es un número inventado con aspecto de dato.** Los valores por especialidad
sirven; el denominador no. Ver [A-018](05-CALIDAD.md#a-018).

### 5. La serie es corta, y crece de a un trimestre

Solo hay dos informes descargables desde el índice del MINSAL. **Los nombres de archivo no
siguen patrón** —uno es `1764018133827_Glosa-06-LE-III-trimestre-2025.pdf` y el otro
`Glosa-06-letra-a-b-c-i-j-k-comun-a-la-partida-1er-trimestre-1.pdf`, que ni siquiera dice
el año— así que los históricos hay que conseguirlos uno a uno.

Publicar dos trimestres y decirlo es más útil que esperar a tener diez.

## Lo que este dataset NO es

**No mide necesidad.** Mide demanda que llegó a registrarse como interconsulta. Una
especialidad con lista corta puede tener buena capacidad o poca derivación.

**No es prevalencia.** 23.134 interconsultas de psiquiatría adulta no son 23.134 personas
con un trastorno: son las que un profesional derivó y siguen esperando.

**No incluye la lista GES.** Las garantías de oportunidad retrasadas son un universo
distinto y no se suman con estas.

## Cómo se construyó

El informe es un PDF de texto —producido desde Word, no escaneado— y el parser extrae la
tabla buscándola por contenido, nunca por número de página. **Es frágil por diseño**:
declara dónde encontró la tabla y falla si no la reconoce, en vez de adivinar.

Cuatro cosas cambiaron entre dos trimestres consecutivos, y ninguna es estable:

| | 2025-T3 | 2026-T1 |
|---|---|---|
| Etiqueta | `PSIQUIATRÍA ADULTO` | `Psiquiatría adulta` |
| Orden de la tabla | alfabético | por magnitud |
| Página | 26 | 29 |
| Período escrito | `III trimestre 2025` | `primer trimestre de 2026` |

El total que la propia tabla declara se usa como ancla, y resultó lo más útil del parser:
detectó primero una fila que el parser se inventaba —el pie de página emparejado con el
número de página, exactamente 27 registros— y después el defecto del informe de 2026.

## Cómo citarlo

```
Datos de Salud Mental de Chile (2026). Espera por especialidad médica,
Chile 2025-2026, versión 2026.07.4. Licencia CC BY-SA 4.0.
Elaborado a partir del informe trimestral de la Glosa 06 del Ministerio de
Salud de Chile, Subsecretaría de Redes Asistenciales.
https://github.com/CProromant/datos-salud-mental-chile
```

## Cómo reproducirlo

```bash
obsm glosa06 informe1.pdf informe2.pdf
```

Recibe los PDF a mano porque no hay URL estable. El índice del MINSAL está en
`https://www.minsal.cl/eje-tiempos-de-espera/` y solo enlaza los dos más recientes.

## Errores y contacto

Si un número no te cuadra, **repórtalo**: abre un issue con el trimestre, la especialidad y
con qué lo estás comparando.
