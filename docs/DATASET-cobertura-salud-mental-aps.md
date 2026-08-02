# Dataset: cobertura del programa de salud mental en APS, Chile 2014–2025

Este documento acompaña a `cobertura_salud_mental_aps.csv`. Léelo antes de usar el archivo:
**la mitad de sus filas no traen cobertura a propósito**, y saber por qué es la diferencia
entre usarlo bien y publicar un número sin sentido.

- **Versión del dataset:** `2026.07.2` — el código que lo produjo es `v0.2.0`
- **Licencia:** CC BY-SA 4.0 — ver `LICENSE-DATA.md`. Permite uso comercial.
- **Cobertura:** 345 comunas × 24 cortes semestrales (2014-06 a 2025-12) × 70 conceptos.
- **Fuentes:** REM Serie P sección P6 (DEIS/MINSAL) como numerador; población inscrita
  validada en salud municipal (FONASA, vía SINIM/SUBDERE) como denominador; maestro de
  establecimientos (DEIS, CC0) para decidir dónde la división es válida.

## Qué contiene

**De los inscritos en la atención primaria municipal de una comuna, cuántos por cada mil
están en control de salud mental.** Es lo que convierte «108.496 personas con depresión
moderada» en una cifra comparable entre una comuna de ocho mil habitantes y una de
doscientos mil.

Mediana nacional en diciembre de 2025: **51,7 por mil** — algo más de 5 % de la población
inscrita está en control de salud mental. Para depresión moderada sola: 5,8 por mil.

| Columna | Qué es |
|---|---|
| `comuna_cut` | Código Único Territorial, **5 dígitos como texto**. `01101` no es `1101`. |
| `periodo` | Corte semestral en ISO: `2023-06` o `2023-12`. |
| `etiqueta` / `etiqueta_norm` | El diagnóstico o concepto. **Filtra por `etiqueta_norm`.** |
| `personas` | Numerador: personas en control. Vacío si el conteo estaba entre 1 y 4. |
| `poblacion_inscrita` | Denominador: inscritos en APS **municipal**. |
| **`denominador`** | **`completo`, `parcial` o `ausente`. La columna que hay que mirar primero.** |
| `cobertura_por_mil` | Personas en control por mil inscritos. **Solo cuando `denominador = completo`.** |
| `padron_sobre_poblacion` | Qué fracción de los habitantes de la comuna está en el padrón. |
| `fraccion_municipal` | Qué fracción de la APS pública de la comuna administra el municipio. |
| `motivo_sin_dato` | Por qué falta el denominador, cuando falta. |
| `source_id`, `source_version`, `poblacion_version`, `pipeline_version`, `fecha_calculo` | Procedencia. |

## Cómo leerlo sin equivocarse

### 1. Mira `denominador` antes que `cobertura_por_mil`

Es la columna más importante del archivo. De las 228.572 filas:

| `denominador` | Celdas | Qué significa |
|---|---|---|
| `completo` | 107.361 | La APS de la comuna es toda municipal y el padrón cubre a la mayoría de sus habitantes. **La cobertura es interpretable.** |
| `parcial` | 51.479 | Comuna mixta, o padrón que cubre menos de la mitad de la comuna. La cobertura sobreestimaría. |
| `ausente` | 69.732 | Sin APS municipal, sin dato de inscritos, o denominador refutado. |

**Solo las filas `completo` traen valor en `cobertura_por_mil`.** Las otras van vacías, no
con una advertencia al lado: una advertencia no viaja cuando alguien copia la celda.

En diciembre de 2025 eso son **184 comunas con cobertura, 109 parciales y 46 ausentes**.

### 2. Por qué 160 comunas no tienen cobertura

No es dato faltante: es un **desajuste de universos**, y es la limitación central de este
dataset.

- El **REM** cuenta actividad de toda la atención primaria pública: la municipal **y** la
  que depende directamente del Servicio de Salud.
- El **padrón** cuenta solo la municipal.

Donde la comuna se atiende en un hospital comunitario, el numerador incluye a esa población
y el denominador no. Quirihue es el caso extremo: su único establecimiento municipal es una
posta rural con **once inscritos**, mientras el REM registra miles de personas en control.
Los once son correctos; lo que no tiene sentido es dividir por ellos.

Veinte comunas no tienen **ningún** establecimiento de APS municipal: Tocopilla, Andacollo,
Isla de Pascua, Llaillay, Hualaihué, Coyhaique, Aisén y otras. Para ellas no existe un
denominador comunal, y este dataset no lo inventa.

### 3. No hay dato para 2023

SINIM publica el denominador de ese año como «No Recepcionado» en las **345 comunas**. Los
dos cortes de 2023 están en el archivo con el numerador y sin cobertura. No se interpoló.

### 4. `personas` vacío no es cero

Es una celda suprimida: había entre 1 y 4 personas, y publicar ese número podría
identificarlas en una comuna chica. Son **51.079 de 228.572 celdas** (22,3 %).

### 5. Es un stock, no un flujo. No sumes los períodos.

«Personas en control» es una foto de quién estaba en tratamiento en ese momento. Sumar junio
con diciembre cuenta dos veces a quien siguió en tratamiento todo el año.

## Lo que este dataset NO es

**No es prevalencia ni necesidad.** Mide quién llegó al sistema público y quedó en control.
Una comuna con cobertura baja puede tener poca enfermedad o poca capacidad de atención, y
estos datos no distinguen entre las dos. Es la limitación que hace que **una cobertura baja
no sea automáticamente una mala noticia ni una alta una buena**.

**No permite rankear comunas.** Dos comunas con el mismo valor pueden estar midiendo
poblaciones distintas si su composición de APS difiere. Comparar sin mirar `denominador` y
`padron_sobre_poblacion` produce ordenamientos que no significan nada.

**No incluye al sector privado.** Nada de lo que ocurre fuera de la red pública aparece acá.

**No mide intensidad.** Una persona con un control al año y otra con doce cuentan igual.

## Una advertencia sobre la serie histórica

`fraccion_municipal` sale del maestro de establecimientos de DEIS, que es un **corte actual
sin vigencias**. Se aplica igual a 2014 que a 2025, así que atribuye al pasado la
organización de hoy: una comuna que municipalizó su APS en 2019 aparece como municipal
también antes.

**Consecuencia práctica:** la clasificación del denominador es más confiable en los años
recientes que en los antiguos. Para comparar 2014 con 2025 en una comuna concreta, conviene
verificar que su composición de APS no cambió en el intervalo. Reconstruir las vigencias con
`fecha_inicio` y `fecha_cierre` del maestro es trabajo pendiente, no resuelto acá.

## Serie nacional, para contrastar

Corte de diciembre, personas en control en el programa por mil inscritos, solo comunas con
denominador completo:

| Año | Comunas | Mediana | p10 | p90 |
|---|---|---|---|---|
| 2014 | 160 | 39,9 | 18 | 80 |
| 2018 | 165 | 52,3 | 36 | 82 |
| 2021 | 177 | 49,4 | 30 | 72 |
| 2025 | 184 | **51,7** | 40 | 77 |

Si tus cifras no se parecen a estas, algo se rompió en el camino. El aumento de comunas
entre 2014 y 2025 no es crecimiento de la red: es que SINIM fue publicando denominadores
donde antes escribía «Costo Fijo».

## Cómo se construyó

Tres comprobaciones independientes deciden si un denominador sirve, y ninguna borra ni imputa
un valor:

1. **Coherencia con los tramos de beneficiarios FONASA.** Señala comunas donde el padrón
   municipal no cubre a los beneficiarios del seguro.
2. **Refutación por el propio numerador.** Quien está en control está inscrito, así que
   `personas > inscritos` prueba que el denominador no describe a esa población. Sin umbral.
   El defecto se propaga a los años siguientes de esa comuna, nunca a los anteriores.
3. **Fracción del padrón sobre la población comunal.** Si la mayoría de los habitantes no
   está en el padrón, el padrón no es el denominador de esa comuna.

La tercera existe porque contar establecimientos resultó ser una garantía débil: Tiltil tiene
un solo CESFAM municipal —así que es «100 % municipal»— y ese padrón cubre al 12 % de sus
habitantes. Sin ese guard publicaba 397 personas en control por mil «inscritos».

Cuatro anomalías encontradas al construir esta serie están documentadas en
`docs/05-CALIDAD.md` como A-013 a A-016. **A-015 conserva el texto equivocado del primer
día**: se concluyó que una fuente publicaba cifras corruptas y estaban bien. Vale la pena
leerla antes de confiar en un ajuste que encaja demasiado bien.

## Cómo citarlo

```
Datos de Salud Mental de Chile (2026). Cobertura del programa de salud mental en
atención primaria, Chile 2014-2025, versión 2026.07.2. Licencia CC BY-SA 4.0.
Elaborado a partir del REM y del maestro de establecimientos del Departamento de
Estadísticas e Información de Salud (DEIS), Ministerio de Salud de Chile, y de la
población inscrita validada de FONASA publicada por SUBDERE en SINIM.
https://github.com/CProromant/datos-salud-mental-chile
```

## Cómo reproducirlo

```bash
# los tres insumos, si no están ya en silver
obsm ingest fonasa_inscritos      && obsm build silver --source fonasa_inscritos
obsm ingest deis_establecimientos && obsm build silver --source deis_establecimientos
obsm ingest ine_proyecciones      && obsm build silver --source ine_proyecciones
obsm rem ingerir                  # doce años del REM (~35 min)

obsm rem cobertura                # esta tabla
```

`obsm rem cobertura` se niega a correr si falta cualquiera de las cuatro capas silver, y
nombra el comando que falta. No produce una tabla parcial: sin `deis_establecimientos` no se
puede saber en qué comunas la división es válida, y una cobertura calculada donde no
corresponde se ve perfectamente creíble.

## Errores y contacto

Si un número no te cuadra, **repórtalo**: abre un issue con la comuna, el período y con qué
lo estás comparando. Las cuatro anomalías de esta serie salieron de mirar con desconfianza
resultados que parecían correctos — y una de ellas, de desconfiar de un razonamiento propio
que encajaba con los datos casi a la perfección.
