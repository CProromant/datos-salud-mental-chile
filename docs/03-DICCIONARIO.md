# 03 — Diccionario de datos

Esquema canónico. Cualquier tabla que no lo respete no entra a `silver`.

## Llaves territoriales

| Variable | Tipo | Formato | Notas |
|---|---|---|---|
| `comuna_cut` | string | 5 dígitos con ceros a la izquierda (`"05101"`) | Llave territorial única. **Nunca entero.** `99999` = desconocida/extranjero |
| `region_cut` | string | 2 dígitos (`"05"`) | Derivado de `comuna_cut[:2]`. Ver `region_vigente()` para series pre-2018 |
| `establecimiento_deis` | string | código DEIS | Solo en tablas de actividad; requiere maestro con vigencias |
| `servicio_salud` | string | nombre normalizado | 29 Servicios de Salud; unidad de la Glosa 06 |

## Llaves temporales

| Variable | Tipo | Formato | Notas |
|---|---|---|---|
| `anio` | Int64 | `2022` | Nullable a propósito: una fila con año ilegible no se descarta en silencio |
| `periodo` | string | `"2022-03"` mensual, `"2022"` anual, `"2022-T1"` trimestral | ISO o extensión declarada. Nunca `"mar-22"` |
| `preliminar` | bool | | `True` si el año está sujeto a revisión por la fuente |

## Dimensiones de persona

| Variable | Valores | Notas |
|---|---|---|
| `sexo` | `hombre`, `mujer`, `desconocido` | Se conserva el valor original de la fuente en bronze. Las fuentes administrativas registran sexo registral, no identidad de género: limitación declarada, no corregible desde el dato |
| `edad_anios` | entero ≥ 0 | Años cumplidos. Edades en meses/días/horas se convierten a 0 |
| `edad_unidad_original` | `anios`, `meses`, `dias`, `horas`, `ausente` | Auditoría de la conversión anterior |
| `grupo_edad` | `00-04` … `80-84`, `85+`, `desconocido` | Grupos quinquenales compatibles con la población estándar OMS |

## Clasificación clínica

| Variable | Tipo | Notas |
|---|---|---|
| `causa_cie10` | string | Código sin punto, mayúsculas (`X700`). Solo en bronze/silver; **nunca en gold** para agrupadores sensibles |
| `es_<agrupador>` | bool | Una columna por agrupador. Multi-etiqueta a propósito: `F03` es demencia y trastorno mental a la vez |
| `agrupador` | string | En tablas agregadas: id del agrupador que originó el conteo |

## Métricas

| Variable | Unidad | Notas |
|---|---|---|
| `casos` | conteo | `NA` cuando fue suprimido; `0` es un valor legítimo y distinto de `NA` |
| `poblacion` | personas | Denominador; siempre acompañado de `poblacion_version` |
| `tasa_cruda` | por 100.000 | Se suprime junto con `casos` |
| `tasa_estandarizada` | por 100.000 | Estandarización directa, población estándar OMS |
| `tasa_suavizada_eb` | por 100.000 | Bayes empírico Poisson-Gamma; publicable aunque `casos` esté suprimido |
| `peso_local_eb` | 0–1 | Cuánto pesa el dato local frente a la media global. Bajo = no interpretar diferencias |
| `monto_nominal` | CLP | Siempre se guarda el nominal |
| `monto_real` | CLP de un año base | Derivado; declara año base y versión del deflactor |

## Procedencia (obligatoria en `gold`)

| Variable | Notas |
|---|---|
| `source_id` | id en `config/sources.yml` |
| `source_version` | identificador del corte de la fuente (fecha de publicación o hash) |
| `poblacion_version` | versión de la proyección INE usada como denominador |
| `pipeline_version` | versión del código que produjo la cifra |
| `fecha_calculo` | ISO 8601 UTC |
| `suprimido` | bool |

## Convenciones que no son negociables

1. Códigos territoriales como texto, siempre.
2. `0` y `NA` significan cosas distintas y nunca se rellenan el uno con el otro.
3. Ningún valor derivado sin su versión de fuente.
4. Nombres de columna en `snake_case`, en español, sin tildes.
