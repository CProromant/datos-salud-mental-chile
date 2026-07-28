# Dataset: tasa comunal de mortalidad por suicidio, Chile 2002–2023

Este documento acompaña a `suicidio_comunal.csv`. Léelo antes de usar el archivo.

- **Versión del dataset:** `2026.07.1` — el código que lo produjo es `v0.2.0`
- **Licencia:** CC BY-SA 4.0 — ver `LICENSE-DATA.md`. Permite uso comercial; exige atribución
  y que las obras derivadas se distribuyan bajo la misma licencia.
- **Cobertura:** 346 comunas × 22 años (2002–2023) = 7.612 filas.
- **Unidad de análisis:** comuna de **residencia** de la persona fallecida, no de ocurrencia.

## Qué contiene

Una fila por comuna y año, con el número de defunciones por suicidio y cuatro formas de
expresarlo como tasa. El detalle por método de suicidio **no se publica y no se publicará**
(ver «Lo que este dataset no trae»).

| Columna | Qué es |
|---|---|
| `comuna_cut` | Código Único Territorial, **5 dígitos como texto**. Léelo como string: `01101` no es `1101`. |
| `anio` | Año calendario. |
| `poblacion` | Población proyectada por el INE para esa comuna y año, base 2017. |
| `casos` | Defunciones por suicidio (CIE-10 X60–X84 más Y87.0). **Vacío si la celda fue suprimida.** |
| `tasa_cruda` | `casos / poblacion × 100.000`. |
| `tasa_estandarizada` | Tasa estandarizada por edad, método directo, población estándar OMS. |
| `ee_estandarizada` | Error estándar de la anterior. |
| `ic95_inferior`, `ic95_superior` | Intervalo de confianza 95 %. El límite inferior está truncado en 0. |
| `avpp` | Años de vida potencial perdidos: suma de `max(0, 80 − edad)` de cada defunción. |
| `tasa_suavizada_eb` | Tasa suavizada por Bayes empírico Poisson-Gamma. **A nivel comunal, es la variante principal.** |
| `peso_local_eb` | Cuánto pesa el dato propio de la comuna frente a la media nacional, entre 0 y 1. |
| `suprimido` | `True` si la celda fue suprimida por tener un conteo entre 1 y 9. |
| `preliminar` | `True` si el año es preliminar. En esta versión es `False` en todas: el archivo de origen es de cifras oficiales consolidadas. |
| `grupos_edad_descartados` | Grupos etarios que la estandarización no pudo usar. Debe ser 0. |
| `source_id`, `source_version`, `poblacion_version`, `pipeline_version`, `fecha_calculo` | Procedencia. Permiten reproducir exactamente esta salida. |

## Cómo leerlo sin equivocarse

**Usa `tasa_suavizada_eb`, no `tasa_cruda`, para comparar comunas.** El suicidio es un
evento raro: en una comuna de 8.000 habitantes, una muerte más o una menos mueve la tasa
cruda decenas de puntos. El suavizado bayesiano corrige eso encogiendo las estimaciones
inestables hacia la media nacional.

**Mira `peso_local_eb` antes de sacar conclusiones de una comuna.** Cerca de 0 significa que
la cifra de esa comuna es casi toda ruido y que el suavizado la reemplazó por la media. En
el 44,5 % de las celdas de este dataset ocurre eso.

**No hagas rankings.** Con eventos raros, un ranking ordena ruido y estigmatiza territorios.
Es un uso que el proyecto rechaza explícitamente (`USO-ACEPTABLE.md`).

**`casos` vacío no es cero.** Es una celda suprimida: había entre 1 y 9 defunciones y
publicar ese número podría identificar a personas en comunas pequeñas. Un cero explícito sí
significa que no hubo ninguna. Son **4.856 de 7.612 celdas** suprimidas: es mucho, y es la
consecuencia esperable de cruzar un evento raro con 346 territorios.

**`poblacion` en 0 da tasas vacías, no tasas cero.** Hay celdas comuna × año sin habitantes
de ningún grupo. No se puede dividir por cero, y un `0,0` se leería como «no hubo muertes».

## Lo que este dataset no trae, a propósito

- **Desagregación por método de suicidio.** Prohibida en `docs/06-ETICA-Y-DATOS.md`,
  siguiendo las recomendaciones internacionales de publicación segura sobre suicidio. No es
  una limitación técnica: es una decisión que no se va a revisar.
- **Desagregación por sexo y grupo etario a nivel comunal.** La estructura etaria se usa
  internamente para estandarizar, pero publicarla por comuna dejaría celdas de uno o dos
  casos.
- **Años anteriores a 2002.** El denominador comunal del INE empieza ese año. Las
  defunciones existen desde 1990, pero hasta 1996 están codificadas en CIE-9, y entre 1997
  y 2001 no hay población comunal con la que dividir. Extrapolar habría sido inventar el
  denominador.

## De dónde salen los números

| | Fuente | Versión |
|---|---|---|
| Numerador | DEIS/MINSAL, defunciones con causa básica CIE-10 | `CIFRAS_OFICIALES 1990-2023` |
| Denominador | INE, estimaciones y proyecciones de población | base 2017, comunas 2002-2035 |
| Territorio | SUBDERE, Códigos Únicos Territoriales | `CUT_2018_v04` |

**Cambio de base poblacional.** El INE publicó en enero de 2026 nuevas proyecciones con base
Censo 2024. Cuando este dataset migre a esa base, **todas las tasas cambiarán
retroactivamente**, aunque las defunciones sean las mismas. Por eso `poblacion_version`
viaja en cada fila: dos versiones de esta serie pueden verse iguales y no serlo.

## Verificación

Estos números fueron contrastados contra fuentes externas, no contra la salida del propio
código:

| Contraste | Resultado |
|---|---|
| Defunciones totales 2023 | 122.218 — **exacto** contra el Anuario de Estadísticas Vitales del INE |
| Defunciones totales 2020 | 126.169 — **exacto** contra la misma fuente |
| Población nacional 2020 y 2023 | **exacto** contra las proyecciones del INE |
| Tasa nacional de suicidio 2015–2023 | 8,0–10,6 por 100.000 (rango publicado para Chile ≈ 10) |
| AVPP por muerte | 38,8 años |

El pipeline **se niega a escribir** este archivo si alguna de esas cifras deja de cuadrar.

**Casos que no están en el archivo, declarados:** 6.080 defunciones por suicidio de 1997 a
2001 quedan fuera por no tener denominador comunal. El total 1997–2023 es 46.810, de los
cuales 40.730 caen dentro de la ventana publicada.

## Cómo citarlo

```
Datos de Salud Mental de Chile (2026). Tasa comunal de mortalidad por suicidio,
Chile 2002-2023, versión 2026.07.1. Licencia CC BY-SA 4.0.
Elaborado a partir de datos de DEIS/MINSAL y del Instituto Nacional de Estadísticas.
https://github.com/CProromant/datos-salud-mental-chile
```

Cita también a los organismos de origen. Este proyecto no genera datos primarios: los
limpia, los cruza y los documenta.

## Cómo reproducirlo

```bash
git clone https://github.com/CProromant/datos-salud-mental-chile.git
cd datos-salud-mental-chile
make setup
obsm run
```

Un comando descarga las fuentes, verifica sus hashes, normaliza, reconcilia y regenera este
archivo. Toma unos 20 minutos.

## Errores y contacto

Si un número no te cuadra, **repórtalo**: abre un issue en el repositorio con la comuna, el
año y con qué lo estás comparando. Un observatorio sin quien lo audite es un blog con
tablas, y las nueve anomalías documentadas en `docs/05-CALIDAD.md` salieron todas de mirar
con desconfianza un resultado que parecía correcto.
