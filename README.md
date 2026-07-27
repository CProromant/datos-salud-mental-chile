# Datos de Salud Mental de Chile (`obsm`)

[![ci](https://github.com/CProromant/datos-salud-mental-chile/actions/workflows/ci.yml/badge.svg)](https://github.com/CProromant/datos-salud-mental-chile/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-green)](LICENSE)
[![datos: CC BY-SA 4.0](https://img.shields.io/badge/datos-CC%20BY--SA%204.0-green)](LICENSE-DATA.md)

Motor de datos que consolida, normaliza y publica indicadores de salud mental de Chile a
nivel comunal, a partir de fuentes públicas hoy dispersas, inconsistentes entre años y en
buena parte atrapadas en PDF.

> **Proyecto independiente.** No representa ni cuenta con el respaldo de ningún organismo
> del Estado. Los datos primarios son de DEIS/MINSAL, INE, DIPRES y otros; este proyecto los
> limpia, los cruza y los documenta.

**El problema que ataca:** Chile no tiene una línea base utilizable de salud mental. Sin
ella no hay evaluación posible de política pública, y las decisiones de presupuesto,
brechas y priorización se toman con anécdota o con cifras de hace una década.
Ver [`docs/00-PROBLEMA.md`](docs/00-PROBLEMA.md).

**Lo que NO es:** no es una aplicación clínica, no hace triage, no procesa datos
identificables de pacientes, no entrega orientación clínica y no reemplaza el juicio
profesional. Estos límites son de diseño, no de alcance temporal.

---

## Estado

**Fase 1 completa salvo el comando único** (2026-07-27). El primer indicador existe, corre
de punta a punta sobre datos reales y está verificado contra referencias externas.

| Verificación | Estado |
|---|---|
| Tests (`pytest`) | 323 pasando |
| Lint y tipos (`ruff`, `mypy`) | limpios |
| Fuentes verificadas con descarga real | 4 de 17 |
| Anclas de reconciliación automáticas | 5 de 5 cuadrando |
| Indicadores activos con ficha y verificación externa | 2 (I-01, I-02) |
| Anomalías documentadas con reproducción y decisión | 9 |

Fase 2 (REM) no ha comenzado. El catálogo distingue explícitamente fuentes verificadas de
no verificadas, y el código **se niega a ingerir** una URL no verificada.

## El resultado, y cómo saber si es creíble

La primera serie publicable es la **tasa comunal de mortalidad por suicidio, 2002–2023**:
346 comunas × 22 años, con tasa cruda, estandarizada por edad, suavizada por Bayes empírico
y años de vida potencial perdidos.

Un número solo vale lo que vale su verificación. Estos son los contrastes contra fuentes
externas, no contra la salida del propio código:

| Contraste | Resultado | Referencia |
|---|---|---|
| Defunciones totales 2023 | 122.218 | **exacto** contra el Anuario de Estadísticas Vitales del INE |
| Defunciones totales 2020 | 126.169 | **exacto** contra la misma fuente |
| Población nacional 2020 | 19.458.310 | **exacto** contra las proyecciones INE |
| Tasa nacional de suicidio 2015–2023 | 8,0 – 10,6 por 100.000 | rango publicado para Chile ≈ 10 |
| Tasa estandarizada, celdas publicables | mediana 10,5 por 100.000 | ídem |
| AVPP por muerte | 38,8 años | coherente con que el suicidio concentra muerte joven |
| Conservación de casos | 46.810 = 40.730 + 6.080 | cierra exacto; el resto se declara |

La reconciliación **no es un informe, es un portero**: `obsm build gold` la corre antes de
calcular y aborta sin escribir nada si un ancla no cuadra. Verificado alterando un ancla a
propósito — el archivo anterior queda intacto y el proceso sale con código 1.

## Cómo funciona

Los datos recorren cuatro capas y cada una tiene permitido hacer cosas distintas. La
separación es lo que hace testeable el proyecto; romperla es la forma más común de meter un
error difícil de encontrar.

```
archivo público
    │  obsm ingest         descarga, hash, encoding, manifiesto
    ▼                      (NO resuelve comunas, NO clasifica, NO calcula)
raw/      archivo tal como vino, inmutable, nunca versionado en git
    │
bronze/   tabla legible: columnas renombradas, tipos mínimos
    │  obsm build silver   territorio, edad, CIE-10
    ▼
silver/   grilla canónica: comuna_cut × período × dimensiones
    │  obsm build gold     denominadores, tasas, reconciliación, supresión
    ▼
gold/     indicadores publicables + manifiesto de procedencia + reporte de calidad
```

Detalle en [`docs/02-ARQUITECTURA.md`](docs/02-ARQUITECTURA.md), incluida la tabla de qué
puede y qué no puede hacer cada capa.

## Instalación y uso

Requiere Python 3.11 o superior.

```bash
git clone https://github.com/CProromant/datos-salud-mental-chile.git
cd datos-salud-mental-chile
make setup
make test
```

### Explorar sin descargar nada

La forma más rápida de entender qué hace la herramienta es tocarla. El archivo de práctica
corre entero con los fixtures del repositorio:

```bash
python ejemplos/practica.py        # las ocho secciones
python ejemplos/practica.py 6      # solo «gold: tasas publicables»
python ejemplos/practica.py 8      # experimentos para romper cosas a propósito
```

### Reproducir la serie completa

```bash
obsm sources list                       # catálogo y estado de verificación
obsm sources verify                     # comprobar que las URLs siguen vivas

obsm ingest deis_defunciones --archivo <ruta al CSV de DEIS>
obsm ingest ine_proyecciones --archivo <ruta al CSV del INE>

obsm build silver --source deis_defunciones
obsm build silver --source ine_proyecciones
obsm build gold   --source deis_defunciones --agrupador SUICIDIO

obsm qa                                 # validaciones y reconciliación
```

Las URLs y los hashes SHA-256 de cada archivo están en
[`config/sources.yml`](config/sources.yml). Descargar desde dominios de gobierno de Chile
requiere `--ssl-no-revoke` y un user-agent de navegador; la receta exacta está en
[`CLAUDE.md`](CLAUDE.md) §4.

> La corrida completa toma unos 20 minutos y deja ~1,1 GB en `data/`, dominados por los
> 3,18 millones de registros de defunciones (940 MB en `raw/`, el resto en las capas
> derivadas). Unificar esto en un solo comando es lo único que falta para cerrar la Fase 1.

## Cómo leer estos datos sin equivocarse

Cada ficha de indicador tiene una sección **«qué NO significa»**, obligatoria por diseño: el
modo típico de fallo de un observatorio no es publicar una cifra errónea, sino publicar una
cifra correcta que se lee mal. Lo esencial:

- **No permite rankear comunas.** En la mayoría, la diferencia con la vecina es
  indistinguible del ruido. El pipeline lo dice solo: en el 44,5 % de las celdas el
  suavizado domina al dato local, y emite la advertencia automáticamente.
- **La tasa de suicidio no mide la salud mental de un territorio.** Es un desenlace raro y
  multicausal; una comuna con buena tasa puede tener un sistema pésimo.
- **No hay desagregación por método, y no la habrá.** Está prohibida en
  [`docs/06-ETICA-Y-DATOS.md`](docs/06-ETICA-Y-DATOS.md) siguiendo las recomendaciones de
  publicación segura sobre suicidio. La prohibición está embebida en el código, no solo en
  la documentación.
- **Ninguna celda pública tiene un conteo entre 1 y 9** (supresión con k=10). Se suprimen
  también todas las columnas derivadas, incluido el AVPP: con un solo caso revelaría la edad
  exacta de la persona fallecida.
- **Los últimos dos años son preliminares** y típicamente suben al consolidarse.
- **La ventana es 2002–2023**, no 1990–2023. El denominador comunal del INE empieza en 2002
  y las defunciones están en CIE-9 hasta 1996.

## Qué produce

| Salida | Formato | Estado |
|---|---|---|
| Datasets normalizados (comuna × período × indicador) | CSV + Parquet | en `data/gold/`, sin publicar aún |
| Manifiesto de procedencia por dataset | JSON | cada corrida |
| Reporte de calidad, cobertura y reconciliación | JSON | cada corrida |
| API de solo lectura sobre el almacén | DuckDB | planificado (Fase 5) |
| Alertas de desviación de series | issue automático | planificado (Fase 5) |

`data/` está fuera del control de versiones por completo. Los datos derivados aún no tienen
release público; ver [`docs/07-PUBLICACION.md`](docs/07-PUBLICACION.md).

## Documentación

| Documento | Contenido |
|---|---|
| [`PLAN.md`](PLAN.md) | Fases, hitos, criterios de término verificables |
| [`docs/00-PROBLEMA.md`](docs/00-PROBLEMA.md) | Teoría de cambio, usuarios, qué se decide con esto |
| [`docs/01-FUENTES.md`](docs/01-FUENTES.md) | Fichas de cada fuente y sus trampas conocidas |
| [`docs/02-ARQUITECTURA.md`](docs/02-ARQUITECTURA.md) | Capas, contratos, qué puede hacer cada una |
| [`docs/03-DICCIONARIO.md`](docs/03-DICCIONARIO.md) | Esquema canónico y diccionario de variables |
| [`docs/04-INDICADORES.md`](docs/04-INDICADORES.md) | Fichas de indicador y qué NO significan |
| [`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) | Anclas de reconciliación y las nueve anomalías |
| [`docs/06-ETICA-Y-DATOS.md`](docs/06-ETICA-Y-DATOS.md) | Ley 21.719, secreto estadístico, publicación segura |
| [`docs/07-PUBLICACION.md`](docs/07-PUBLICACION.md) | Versionado, releases, citación |
| [`docs/08-RIESGOS.md`](docs/08-RIESGOS.md) | Registro de riesgos con mitigación y dueño |
| [`docs/09-GOBERNANZA.md`](docs/09-GOBERNANZA.md) | Dueño institucional, comité, aprobación de cambios |
| [`docs/adr/`](docs/adr/) | Decisiones de arquitectura, con su justificación y lo que descartaron |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Cómo contribuir |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones operativas del repositorio |

Si vas a tocar código, lo mínimo es `docs/00`, `docs/02` y `docs/06`. El último no es
negociable.

## Anomalías: por qué hay nueve documentadas y eso es buena señal

[`docs/05-CALIDAD.md`](docs/05-CALIDAD.md) registra cada anomalía con su reproducción, su
verificación y la decisión tomada. Cinco eran defectos propios que **no lanzaban ninguna
excepción** y habrían publicado números plausibles y falsos: cero suicidios en 27 años por
leer la columna de diagnóstico equivocada, una comuna inventada por validar el formato del
código territorial y no su existencia, doce años futuros con tasa cero.

El patrón que se repite es **un cero que significa otra cosa**: «no hubo muertes» contra «no
hay a quién dividir» contra «no se leyó la columna correcta». De ahí la regla operativa del
proyecto: un indicador de calidad que sale perfecto a la primera se audita antes de
celebrarlo.

La política es no borrar anomalías. Muchas son reales —un CESFAM que dejó de reportar— y
borrarlas es falsificar el diagnóstico.

## Citación

El proyecto aún no tiene release ni DOI. Mientras tanto, citar el repositorio y el commit:

```
Datos de Salud Mental de Chile (obsm). https://github.com/CProromant/datos-salud-mental-chile
Commit <sha>. Elaborado a partir de datos de DEIS/MINSAL e INE.
```

Toda reutilización debe mencionar también al organismo de origen. Este proyecto no genera
datos primarios: los limpia, los cruza y los documenta.

## Licencia

- **Código:** MIT ([`LICENSE`](LICENSE)).
- **Datos derivados:** CC BY-SA 4.0 ([`LICENSE-DATA.md`](LICENSE-DATA.md)). El
  CompartirIgual es **heredado, no una preferencia**: el INE publica bajo esa licencia las
  proyecciones de población, que son el denominador de toda tasa del proyecto
  ([ADR 0005](docs/adr/0005-licencia-datos-sharealike.md)). **Permite uso comercial.**
- **Normas de uso:** [`USO-ACEPTABLE.md`](USO-ACEPTABLE.md). Son normas del proyecto, no
  cláusulas de licencia, y el documento explica por qué esa distinción es deliberada.
- Las fuentes primarias conservan sus propias condiciones. Las de DEIS y SUBDERE están sin
  confirmar y es un pendiente declarado.

---

Si este proyecto te sirve, lo más útil que puedes hacer es **usarlo y reportar dónde el dato
no cuadra**. Un observatorio sin quien lo audite es un blog con tablas.
