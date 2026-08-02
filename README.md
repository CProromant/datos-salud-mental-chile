# Datos de Salud Mental de Chile (`obsm`)

[![ci](https://github.com/CProromant/datos-salud-mental-chile/actions/workflows/ci.yml/badge.svg)](https://github.com/CProromant/datos-salud-mental-chile/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-green)](LICENSE)
[![datos: CC BY-SA 4.0](https://img.shields.io/badge/datos-CC%20BY--SA%204.0-green)](LICENSE-DATA.md)

**Los datos de salud mental de Chile están publicados, pero repartidos en archivos que no
conversan entre sí.** Este proyecto los junta, los limpia, los verifica contra las cifras
oficiales y los deja descargables.

> Proyecto independiente. No representa ni cuenta con el respaldo de ningún organismo del
> Estado. Los datos primarios son de DEIS/MINSAL, INE y SUBDERE; acá se limpian, se cruzan
> y se documentan.

---

## Qué se puede averiguar con esto

Preguntas que hoy no tienen respuesta fácil y que estos datos contestan:

- **¿Cuánta gente está en tratamiento por depresión en mi comuna?**
  108.496 personas con depresión moderada a diciembre de 2025, en ~330 comunas — y la
  serie completa desde 2014.
- **¿Cómo se compara la tasa de suicidio de una comuna con el resto?**
  Serie 2002-2023 para las 346 comunas, ajustada por edad y suavizada.
- **¿Cuántos años de vida se pierden por suicidio?**
  38,8 por cada muerte — el suicidio concentra muerte joven.
- **¿Cuánta gente hay en el programa de salud mental de atención primaria?**
  1.048.618 personas a diciembre de 2025, contra 756.956 en 2014.
- **De los que se atienden en el sistema público, ¿a cuántos alcanza?**
  52 de cada mil inscritos en atención primaria están en control de salud mental
  (diciembre de 2025). Se puede calcular en 185 de las 345 comunas, y el dato dice
  explícitamente por qué en las otras no.

- **¿Cuánto se espera por una consulta de especialidad, y dónde más?**
  264 días de mediana a junio de 2025, sobre 2,7 millones de interconsultas. Entre
  Servicios de Salud va de 123 días (Aconcagua) a 437 (Metropolitano Norte).
- **¿Cuánta gente está esperando un psiquiatra?**
  **23.134 adultos y 12.585 niños y adolescentes** al 31 de marzo de 2026. Es la única
  fuente pública que lo aísla, y hay que sacarla de un PDF trimestral.

Y una que **no** contesta, a propósito: *¿qué comuna está peor?* En la mayoría de las
comunas la diferencia con la vecina es indistinguible del ruido. Los datos incluyen la
medida de esa incertidumbre justamente para que no se hagan rankings.

## Los datos

| Serie | Qué mide | Cobertura | Estado |
|---|---|---|---|
| **Mortalidad por suicidio** | muertes, tasas cruda / estandarizada / suavizada, años de vida perdidos | 346 comunas, 2002-2023, anual | [CSV](https://github.com/CProromant/datos-salud-mental-chile/releases/latest/download/suicidio_comunal.csv) · [ficha](docs/DATASET-suicidio-comunal.md) |
| **Población bajo control en salud mental** | personas en tratamiento por diagnóstico | 345 comunas, 2014-2025, semestral | [CSV](https://github.com/CProromant/datos-salud-mental-chile/releases/latest/download/poblacion_control_salud_mental.csv) · [ficha](docs/DATASET-poblacion-control-salud-mental.md) |
| **Cobertura en atención primaria** | personas en control por mil inscritos | 185 comunas, 2014-2025, semestral | [ficha lista](docs/DATASET-cobertura-salud-mental-aps.md), sin publicar |
| **Listas de espera** | registros, personas y días de espera | 29 Servicios de Salud, 2019-2025, trimestral | [ficha lista](docs/DATASET-listas-espera-servicio-salud.md), sin publicar |
| **Espera por especialidad** | registros en espera, incluida psiquiatría | nacional, 2025-2026, trimestral | [ficha lista](docs/DATASET-espera-por-especialidad.md), sin publicar |

La segunda es la importante para la mayoría de las preguntas: **la mortalidad no sirve para
medir depresión o ansiedad**, porque casi nadie muere de eso. En el archivo de defunciones
los trastornos del ánimo son once muertes al año en todo Chile; en el de atención primaria
son ciento ocho mil personas en tratamiento solo por depresión moderada.

Los enlaces `CSV` bajan el archivo de la **última versión publicada** directamente; el
[release completo](https://github.com/CProromant/datos-salud-mental-chile/releases/latest) trae además el ZIP con todo el conjunto y sus manifiestos.

**Las tres últimas todavía no están publicadas.** Se reproducen con `obsm`, cada una tiene
su ficha escrita y lo que falta es el release. Se anuncian acá porque cambian lo que el
proyecto puede responder, y porque ninguna se lee bien sin su ficha: la de cobertura tiene
**la mitad de sus filas sin valor a propósito**, la de listas de espera **no baja a comuna**,
y la de especialidad **no cruza con territorio** porque ninguna fuente pública lo hace.

## Empezar en dos minutos

```bash
git clone https://github.com/CProromant/datos-salud-mental-chile.git
cd datos-salud-mental-chile
make setup

python ejemplos/practica.py        # nueve secciones para entender la herramienta tocándola
```

El archivo de práctica corre entero con los datos de ejemplo del repositorio: **no hace
falta descargar nada**. La sección 9 son experimentos para romper cosas a propósito y ver
saltar cada resguardo.

### Reproducir las series completas

```bash
obsm run     # descarga, verifica, normaliza, reconcilia y escribe todo
```

Un comando. Toma unos 20 minutos y deja ~1,1 GB en `data/`. Se detiene en el primer error:
encadenar sobre una etapa fallida produce basura con buen aspecto.

## Cómo saber si estos números son confiables

Un dato vale lo que vale su verificación. Estos son los contrastes contra **fuentes
externas**, no contra la salida del propio código:

| Se comparó | Resultado |
|---|---|
| Defunciones totales 2023 | 122.218 — **exacto** contra el Anuario del INE |
| Defunciones totales 2020 | 126.169 — **exacto** contra la misma fuente |
| Población nacional 2020 y 2023 | **exacto** contra las proyecciones del INE |
| Tasa nacional de suicidio 2015-2023 | 8,0 a 10,6 por 100.000 (lo publicado para Chile ≈ 10) |
| Conservación de casos | 46.810 = 40.730 publicados + 6.080 declarados fuera |

**Y no es un informe, es un portero.** El pipeline corre esas comprobaciones *antes* de
calcular y **se niega a escribir** si alguna falla. Verificado alterando una cifra a
propósito: el archivo anterior quedó intacto y el proceso salió con error.

## Cómo leer estos datos sin equivocarse

Cada indicador tiene una sección **«qué NO significa»**, obligatoria por diseño: el modo
típico de fallo de un observatorio no es publicar una cifra errónea, sino publicar una
cifra correcta que se lee mal.

- **No permite rankear comunas.** En el 44,5 % de las celdas el suavizado estadístico
  domina al dato local — o sea, la diferencia entre esas comunas es ruido. El pipeline lo
  advierte solo.
- **La tasa de suicidio no mide la salud mental de un territorio.** Es un desenlace raro y
  multicausal; una comuna con buena tasa puede tener un sistema pésimo.
- **Los conteos de personas bajo control no son una cobertura, y dividirlos por la población
  comunal no la produce.** Eso incluiría a quien se atiende en el sistema privado y daría un
  número que parece cobertura sin serlo. El denominador correcto —la población inscrita en
  atención primaria— ya está en el pipeline, pero **solo sirve en 185 de las 345 comunas**:
  el REM cuenta toda la atención primaria pública y el padrón cuenta solo la municipal, así
  que donde la comuna se atiende en un hospital del Servicio de Salud la división no
  significa nada. Cada fila declara en qué situación está.
- **Ninguna celda pública tiene un conteo entre 1 y 9.** Se suprimen para que nadie sea
  identificable en una comuna chica, junto con todo lo que permita reconstruirlas.
- **No hay desagregación por método de suicidio, y no la habrá.** Está prohibida siguiendo
  las recomendaciones internacionales de publicación segura. La prohibición está en el
  código, no solo en la documentación.

## Cómo funciona por dentro

Los datos pasan por cuatro capas y cada una tiene permitido hacer cosas distintas. Esa
separación es lo que hace verificable el proyecto.

```
archivo público del Estado
    │  descarga, verifica el hash, detecta el encoding
    ▼
raw      el archivo tal como vino, nunca se toca
    │  renombra columnas y tipa. NO resuelve comunas ni calcula
    ▼
bronze   tabla legible
    │  normaliza territorio, edad y diagnósticos
    ▼
silver   grilla común: comuna × período × dimensiones
    │  une denominadores, calcula, reconcilia y suprime
    ▼
gold     lo publicable, con su procedencia y su reporte de calidad
```

Detalle en [`docs/02-ARQUITECTURA.md`](docs/02-ARQUITECTURA.md).

## Estado

**Fases 1 y 2 completas; Fase 3 con sus dos fuentes ingeridas** (2026-07-29).

| | |
|---|---|
| Tests | 556+ pasando |
| Lint y tipos | limpios |
| Fuentes verificadas con descarga real | 11 de 19 |
| Anclas de reconciliación automáticas | 5 de 5 cuadrando |
| Anomalías documentadas | 20 |

Una fuente está `verificada` solo cuando alguien **abrió el archivo y lo entendió** — no
cuando el servidor respondió 200.

## Las anomalías son parte del producto

[`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) registra dieciséis anomalías con su reproducción y
la decisión tomada. Varias eran defectos propios que **no lanzaban ningún error** y habrían
publicado números plausibles y falsos: cero suicidios en 27 años por leer la columna
equivocada, una comuna inventada, doce años futuros con tasa cero.

El patrón que más se repite es **un cero que significa otra cosa**: «no hubo muertes» contra
«no hay a quién dividir» contra «no se leyó la columna correcta».

**Una de ellas es un error de razonamiento, no de código, y está documentada como tal.** Al
construir el denominador de cobertura se concluyó que una fuente publicaba cifras corruptas.
La teoría encajaba casi perfecto: predecía un patrón nítido y la serie lo confirmaba con cero
excepciones en 4.863 celdas. Era falsa. Los números estaban bien; lo que estaba mal era
suponer que dos variables medían el mismo universo, y bastaba **leer su nombre completo** para
verlo. La comprobación no salió de razonar mejor sobre el intermediario sino de bajar la
fuente original. Queda escrito en [A-015](docs/05-CALIDAD.md#a-015) con el texto equivocado
conservado: un ajuste excelente contra los datos no valida la premisa.

Las anomalías no se borran. Muchas son reales —un CESFAM que dejó de reportar es un dato
sobre el sistema— y borrarlas falsifica el diagnóstico.

## Documentación

| | |
|---|---|
| [`PLAN.md`](PLAN.md) | fases, hitos y criterios de término |
| [`docs/00-PROBLEMA.md`](docs/00-PROBLEMA.md) | para qué existe y quién lo usa |
| [`docs/01-FUENTES.md`](docs/01-FUENTES.md) | cada fuente y sus trampas conocidas |
| [`docs/02-ARQUITECTURA.md`](docs/02-ARQUITECTURA.md) | las capas y qué puede hacer cada una |
| [`docs/03-DICCIONARIO.md`](docs/03-DICCIONARIO.md) | el esquema canónico: nombres, tipos y qué significa cada nulo |
| [`docs/04-INDICADORES.md`](docs/04-INDICADORES.md) | fórmulas, límites y qué NO significan |
| [`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) | anclas de reconciliación y anomalías |
| [`docs/06-ETICA-Y-DATOS.md`](docs/06-ETICA-Y-DATOS.md) | los límites que no se negocian |
| [`docs/07-PUBLICACION.md`](docs/07-PUBLICACION.md) | versionado, checklist de release y licencias |
| [`docs/08-RIESGOS.md`](docs/08-RIESGOS.md) | qué puede salir mal, con dueño y mitigación |
| [`docs/09-GOBERNANZA.md`](docs/09-GOBERNANZA.md) | quién decide qué, y quién puede vetar |
| [`CHANGELOG.md`](CHANGELOG.md) | qué cambió en cada versión y si afecta series ya publicadas |
| [`CLAUDE.md`](CLAUDE.md) | reglas operativas del repositorio: los siete no negociables |
| [`docs/adr/`](docs/adr/) | decisiones tomadas, con lo que se descartó y por qué |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | cómo contribuir |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | playbook de sesiones: una tarea con criterio de término verificable |

Si vas a tocar código: `docs/00`, `docs/02` y `docs/06`. El último no es negociable.

## Licencia

- **Código:** MIT ([`LICENSE`](LICENSE)).
- **Datos:** CC BY-SA 4.0 ([`LICENSE-DATA.md`](LICENSE-DATA.md)). **Permite uso comercial.**
  El «CompartirIgual» no es una preferencia del proyecto: el INE publica bajo esa licencia
  las proyecciones de población, que son el denominador de toda tasa, y su cláusula obliga
  al derivado ([ADR 0005](docs/adr/0005-licencia-datos-sharealike.md)).
- **Normas de uso:** [`USO-ACEPTABLE.md`](USO-ACEPTABLE.md) — normas del proyecto, no
  cláusulas legales, y el documento explica por qué esa distinción es deliberada.

Cita siempre también al organismo de origen. Este proyecto no genera datos primarios.

---

**Lo más útil que puedes hacer es usarlo y decir dónde el dato no cuadra.** Un observatorio
sin quien lo audite es un blog con tablas — las dieciséis anomalías salieron todas de mirar
con desconfianza un resultado que parecía correcto, incluidos los que parecían correctos
porque el razonamiento que los produjo encajaba demasiado bien.
