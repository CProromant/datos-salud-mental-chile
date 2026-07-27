# PLAN

Plan de construcción por fases. Cada fase tiene un **criterio de término verificable**: si
no se puede comprobar con un comando o con un artefacto revisable, no es criterio de término.

Principio rector: **una fuente que funciona de punta a punta vale más que ocho a medias.**
El orden está elegido para que el proyecto sea útil (y por tanto adoptable) lo antes posible,
y para que los errores caros aparezcan temprano.

---

## Fase 0 — Andamiaje y contratos (semana 1)

Objetivo: que el repositorio imponga disciplina antes de que entre el primer dato real.

- [x] Estructura, `CLAUDE.md`, plan, documentación normativa.
- [x] `territorio.py` con normalización de comunas y vigencias regionales, con tests de
      regresión sobre los casos feos conocidos.
- [x] `cie10.py` con agrupadores y política de publicación embebida.
- [x] `quality.py` con supresión por umbral y detección de filas de total.
- [x] `indicators/tasas.py`: tasa cruda, estandarización directa, suavizado bayesiano
      empírico Poisson-Gamma, con tests de valores calculados a mano.
- [x] Catálogo `config/sources.yml` con estado de verificación explícito.
- [x] CI que corre tests y lint en cada push, y falla si hay datos versionados.

**Término:** `make test` pasa y `obsm sources list` muestra el catálogo con todas las
fuentes en estado `no_verificada`.

---

## Fase 1 — Primera fuente de punta a punta: mortalidad por suicidio (semanas 2–4)

Se parte por defunciones DEIS porque es la serie más limpia, la de mayor peso público y la
que obliga a resolver de una vez territorio, CIE-10, denominadores poblacionales y política
de publicación.

1. Verificar realmente las URLs del portal de datos abiertos DEIS y fijarlas en el catálogo.
2. Ingestor `deis_defunciones`: descarga, hash, detección de encoding, manifiesto.
3. Denominadores: proyecciones de población INE por comuna, sexo y edad simple.
4. `gold`: tasa cruda, tasa estandarizada por edad (población estándar OMS), tasa suavizada
   EB para comunas pequeñas, AVPP, todo por sexo y grupo etario.
5. Reconciliación: el total nacional por año debe cuadrar con la cifra oficial publicada
   dentro de ±0,5%. Si no cuadra, no se publica.
6. Aplicar supresión k y la prohibición de desagregar por método.

**Término:** un CSV comunal **2002**–último año oficial, reproducible con un comando, con
manifiesto de procedencia, que cuadra con el total oficial y pasa la revisión de `docs/06`.

> Corregido el 2026-07-27: decía 2000 y ese alcance no era alcanzable. Las proyecciones
> comunales del INE empiezan en 2002 (A-008) y las defunciones están en CIE-9 hasta 1996
> (A-002). Estirar la serie hacia atrás exigiría extrapolar población, que es justo lo que
> el riesgo principal de esta fase prohíbe. 1997-2001 queda disponible como conteos, no
> como tasas comunales.

**Riesgo principal:** el cambio de base poblacional tras el Censo 2024 desplaza todas las
tasas. Mitigación: el denominador es un dataset versionado aparte y las tasas se recalculan,
no se corrigen a mano.

---

## Fase 2 — Oferta y actividad: REM (semanas 5–9)

La parte fea del proyecto y la de mayor valor diferencial: nadie tiene el REM de salud
mental consolidado, limpio y comparable entre años.

1. Mapear las secciones de salud mental en los manuales REM año por año (cambian de número
   y de desglose). El mapeo vive en `config/`, no en código.
2. Ingestor por serie, con el contrato declarado y falla ruidosa ante cambio de esquema.
3. Silver: personas bajo control, ingresos, egresos por alta clínica, controles por
   profesional, todo con `comuna_cut` y `establecimiento_deis`.
4. Indicadores: cobertura sobre población inscrita, razón control/ingreso, abandono
   estimado, intensidad de tratamiento.

**Término:** serie mensual comunal 2018–presente para al menos: personas bajo control en
programa de salud mental por grupo etario, e ingresos por intento e ideación suicida.

**Riesgo principal:** discontinuidades por cambio de manual interpretadas como cambios
reales. Mitigación: marcar quiebres de serie explícitamente en una tabla de `quiebres` que
todo consumidor de la API recibe junto con los datos.

---

## Fase 3 — Espera y acceso: Glosa 06 y GES (semanas 10–12)

1. Scraper del listado de informes trimestrales + parser PDF con `pdfplumber`/`camelot`.
2. Extraer, para las especialidades de psiquiatría adulto e infanto-adolescente: casos en
   espera, mediana y percentil 90 de días, por Servicio de Salud.
3. Serie histórica desde el primer informe disponible en formato estable.
4. Indicador de garantías GES de salud mental retrasadas.

**Término:** serie trimestral por Servicio de Salud, con verificación manual de tres
trimestres al azar contra el PDF original.

**Riesgo principal:** el parser rompe con cada rediseño del informe. Mitigación: el test de
oro es un fixture por layout conocido; el parser declara qué layout detectó.

---

## Fase 4 — Recursos y gasto (semanas 13–16)

1. Registro Nacional de Prestadores Individuales: psiquiatras y psicólogos, con las
   advertencias del caso (el registro dice dónde está inscrito el prestador, no dónde
   atiende ni cuántas horas).
2. Ejecución presupuestaria DIPRES de la partida 16, con la desagregación que exista, más
   los informes de glosa que reportan gasto en salud mental.
3. Deflactor IPC del INE para pesos reales.
4. Indicador: gasto real per cápita en salud mental por Servicio de Salud, y su evolución.

**Término:** serie anual de gasto real per cápita por Servicio de Salud, con una nota
metodológica explícita sobre qué queda fuera (PPI no desagregable, aporte SENDA, gasto
municipal propio, gasto de bolsillo).

**Riesgo principal:** sobreinterpretar una cifra de gasto que el propio Estado no puede
desagregar. Mitigación: publicar rango, no punto, y decirlo en la ficha del indicador.

---

## Fase 5 — Síntesis, alertas y publicación (semanas 17–20)

1. Índice de brecha territorial: demanda esperada (prevalencia estimada × población) versus
   oferta observada, por comuna, con intervalo de incertidumbre.
2. Detección de desviaciones en series mensuales (CUSUM sobre residuos de un modelo
   estacional simple). Alerta = issue automático, nunca publicación automática.
3. Release versionado, DOI vía Zenodo, ficha de citación.
4. Sitio estático con las series, sin lógica de servidor.

**Término:** primer release público `v1.0.0` con DOI, changelog y datos descargables.

---

## Fuera de alcance (explícito)

- Cualquier dato individual de pacientes, incluso anonimizado.
- Predicción de riesgo individual. Es la aplicación más tentadora y la más peligrosa de esta
  base: quedaría fuera aunque hubiera datos, por diseño.
- Contenido clínico, psicoeducación o intervención.
- Dashboard con login, usuarios, o infraestructura de servidor en las fases 0–5.

## Dependencias externas críticas

1. **Un dueño institucional** que use y defienda la herramienta (centro académico, sociedad
   científica, Defensoría de la Niñez, un Servicio de Salud). Sin esto el proyecto muere en
   el mes seis. Conseguirlo es tarea de la Fase 1, en paralelo al código.
2. **Un revisor con competencia epidemiológica** para las fichas de indicador.
3. **Un revisor con competencia en salud mental y prevención de suicidio** para todo lo que
   se publique sobre suicidio.

## Métricas del propio proyecto

- Nº de fuentes verificadas y corriendo sin intervención manual.
- Días de latencia entre publicación oficial y disponibilidad en el observatorio.
- Nº de indicadores con ficha completa y test de reconciliación.
- Uso: descargas, citas, consultas de la API.
- Fallos silenciosos detectados en producción: objetivo cero, y cada uno genera un test.
