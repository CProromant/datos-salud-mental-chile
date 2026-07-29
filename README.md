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

Y una que **no** contesta, a propósito: *¿qué comuna está peor?* En la mayoría de las
comunas la diferencia con la vecina es indistinguible del ruido. Los datos incluyen la
medida de esa incertidumbre justamente para que no se hagan rankings.

## Los datos

| Serie | Qué mide | Cobertura | Estado |
|---|---|---|---|
| **Mortalidad por suicidio** | muertes, tasas cruda / estandarizada / suavizada, años de vida perdidos | 346 comunas, 2002-2023, anual | [descargable](https://github.com/CProromant/datos-salud-mental-chile/releases/latest) |
| **Población bajo control en salud mental** | personas en tratamiento por diagnóstico | 345 comunas, 2014-2025, semestral | [descargable](https://github.com/CProromant/datos-salud-mental-chile/releases/latest) |

La segunda es la importante para la mayoría de las preguntas: **la mortalidad no sirve para
medir depresión o ansiedad**, porque casi nadie muere de eso. En el archivo de defunciones
los trastornos del ánimo son once muertes al año en todo Chile; en el de atención primaria
son ciento diecisiete mil personas en tratamiento.

## Empezar en dos minutos

```bash
git clone https://github.com/CProromant/datos-salud-mental-chile.git
cd datos-salud-mental-chile
make setup

python ejemplos/practica.py        # ocho secciones para entender la herramienta tocándola
```

El archivo de práctica corre entero con los datos de ejemplo del repositorio: **no hace
falta descargar nada**. La sección 8 son experimentos para romper cosas a propósito y ver
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
- **Las personas bajo control no son una cobertura.** Son conteos. Calcular un porcentaje
  contra la población comunal incluiría a quien se atiende en el sistema privado, y daría
  un número que parece cobertura y no lo es.
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

**Fases 1 y 2 completas** (2026-07-27): dos fuentes funcionando de punta a punta.

| | |
|---|---|
| Tests | 398 pasando |
| Lint y tipos | limpios |
| Fuentes verificadas con descarga real | 5 de 17 |
| Anclas de reconciliación automáticas | 5 de 5 cuadrando |
| Anomalías documentadas | 12 |

Una fuente está `verificada` solo cuando alguien **abrió el archivo y lo entendió** — no
cuando el servidor respondió 200.

## Las anomalías son parte del producto

[`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) registra nueve anomalías con su reproducción y la
decisión tomada. Cinco eran defectos propios que **no lanzaban ningún error** y habrían
publicado números plausibles y falsos: cero suicidios en 27 años por leer la columna
equivocada, una comuna inventada, doce años futuros con tasa cero.

El patrón que se repite es **un cero que significa otra cosa**: «no hubo muertes» contra
«no hay a quién dividir» contra «no se leyó la columna correcta».

Las anomalías no se borran. Muchas son reales —un CESFAM que dejó de reportar es un dato
sobre el sistema— y borrarlas falsifica el diagnóstico.

## Documentación

| | |
|---|---|
| [`PLAN.md`](PLAN.md) | fases, hitos y criterios de término |
| [`docs/00-PROBLEMA.md`](docs/00-PROBLEMA.md) | para qué existe y quién lo usa |
| [`docs/01-FUENTES.md`](docs/01-FUENTES.md) | cada fuente y sus trampas conocidas |
| [`docs/02-ARQUITECTURA.md`](docs/02-ARQUITECTURA.md) | las capas y qué puede hacer cada una |
| [`docs/04-INDICADORES.md`](docs/04-INDICADORES.md) | fórmulas, límites y qué NO significan |
| [`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) | anclas de reconciliación y anomalías |
| [`docs/06-ETICA-Y-DATOS.md`](docs/06-ETICA-Y-DATOS.md) | los límites que no se negocian |
| [`docs/adr/`](docs/adr/) | decisiones tomadas, con lo que se descartó y por qué |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | cómo contribuir |

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
sin quien lo audite es un blog con tablas — las nueve anomalías salieron todas de mirar con
desconfianza un resultado que parecía correcto.
