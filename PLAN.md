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

> **Lección retroactiva (2026-07-27).** Los siete puntos de arriba estaban marcados como
> hechos y sus tests pasaban, pero varias de esas funciones **no las llamaba nadie**:
> `verificar_reconciliacion`, `validar_sin_duplicados` y `validar_cobertura_territorial`
> vivían escritas y probadas, fuera del camino de ejecución. Un andamiaje que existe pero
> no está conectado da la sensación de protección sin la protección.
>
> El criterio de término de una fase de andamiaje debería incluir **quién invoca cada
> pieza**, no solo que exista y pase sus tests. Se corrigió en Fase 1 al cablear la
> reconciliación; `validar_sin_duplicados` y `validar_cobertura_territorial` siguen
> huérfanas, aunque las anclas hoy cubren buena parte de lo que detectarían.

---

## Fase 1 — Primera fuente de punta a punta: mortalidad por suicidio (semanas 2–4)

Se parte por defunciones DEIS porque es la serie más limpia, la de mayor peso público y la
que obliga a resolver de una vez territorio, CIE-10, denominadores poblacionales y política
de publicación.

- [x] **1. Verificar realmente las URLs** del portal DEIS y fijarlas en el catálogo.
      4 de 17 fuentes verificadas con descarga real, no con un 200 de `HEAD`.
- [x] **2. Ingestor `deis_defunciones`**: descarga, hash, encoding, manifiesto.
      3.182.446 filas ingeridas; procedencia encadenada del ZIP publicado al CSV extraído
      y de ahí a bronze.
- [x] **3. Denominadores** INE por comuna, sexo y edad simple. 1.905.768 filas; el cruce
      contra la DPA da 346 comunas y cero diferencias en ambas direcciones.
- [x] **4. `gold`**: tasa cruda, estandarizada por edad (OMS colapsado a `80+`) con IC 95 %,
      suavizada EB y AVPP. Todo lo derivado del conteo se suprime junto con él.
- [x] **5. Reconciliación** contra cifra oficial. Cinco anclas declaradas en
      `config/anclas.yml`, evaluadas **automáticamente** antes de publicar: si una no
      cuadra, `obsm build gold` aborta y no escribe nada.
- [x] **6. Supresión k** y prohibición de desagregar por método. 63,8 % de celdas
      suprimidas con k=10 y cero celdas visibles con conteo 1..9.
- [ ] **7. Un solo comando.** Hoy son cinco pasos encadenados a mano. Es lo único que falta
      para cumplir el criterio de término tal como está escrito.

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

> **Estado al 2026-07-27.** La primera tasa existe y está verificada contra referencias
> externas: 8,0–10,6 por 100.000 entre 2015 y 2023, dentro del rango publicado para Chile,
> con 38,8 años de vida perdidos por muerte. La conservación de casos cierra exacto
> (46.810 = 40.730 en ventana + 6.080 fuera). Falta solo el comando único.
>
> **Lo que la fase costó de más, y por qué valió la pena.** Nueve anomalías documentadas
> (A-001 a A-009). Cinco eran defectos propios que no rompían nada visible:
>
> | | qué habría publicado |
> |---|---|
> | A-004 | cero suicidios en 27 años, leyendo `DIAG1` en vez de `DIAG2` |
> | A-007 | una comuna inventada, por validar el formato del CUT y no su existencia |
> | A-008/A-009 | tasas sobre años sin denominador y celdas con población cero |
> | ventana de años | doce años futuros con «cero suicidios» y tasa 0,0 |
> | `es_publicable` | el desglose por método, que `docs/06` prohíbe, autorizado por un typo |
>
> Ninguno lanzaba excepción. El patrón que se repite es un **cero que significa otra cosa**:
> «no hubo muertes» contra «no hay a quién dividir» contra «no se leyó la columna correcta».
> De ahí salió la regla operativa de esta fase: un indicador de calidad que sale perfecto a
> la primera se audita antes de celebrarlo.
>
> **Lo que se construyó y no estaba en el plan:** la reconciliación automática. Las funciones
> de comparación existían desde Fase 0 pero **nadie las llamaba**, así que la regla «si no
> cuadra, no se publica» dependía de que una persona se acordara. Ahora es parte del camino
> de publicación y está verificado que bloquea. También `ejemplos/practica.py`, que fue lo
> que destapó el fallo de `es_publicable`.

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
4. **Las licencias de las fuentes.** Resuelto para el INE el 2026-07-27: publica bajo
   CC BY-SA 4.0, y como sus proyecciones son el denominador de toda tasa, su cláusula
   CompartirIgual obliga al derivado. El proyecto adoptó CC BY-SA 4.0 para `gold`
   (ADR 0005). **Siguen sin confirmar DEIS y SUBDERE**: una fuente bajo CC BY o dominio
   público no da problema, pero una con cláusula no comercial obligaría a reabrir la
   decisión antes de publicar. Es una dependencia externa porque no se resuelve
   programando, se resuelve leyendo o preguntando al organismo.

## Métricas del propio proyecto

- Nº de fuentes verificadas y corriendo sin intervención manual.
- Días de latencia entre publicación oficial y disponibilidad en el observatorio.
- Nº de indicadores con ficha completa y test de reconciliación.
- Uso: descargas, citas, consultas de la API.
- Fallos silenciosos detectados en producción: objetivo cero, y cada uno genera un test.

**Marcador al 2026-07-27** (fin de Fase 1, salvo el comando único):

| métrica | valor |
|---|---|
| fuentes verificadas con descarga real | 4 de 17 |
| indicadores activos con ficha y verificación externa | 2 (I-01, I-02) |
| anclas de reconciliación automáticas | 5, todas cuadrando |
| anomalías documentadas con reproducción y decisión | 9 |
| tests | 323 |
| fallos silenciosos detectados **antes** de producción | 5, cada uno con su test |

La última fila es la que importa y conviene leerla con cuidado: son cinco defectos que no
lanzaban excepción y que habrían publicado números plausibles y falsos. Ninguno lo encontró
el CI. Los destaparon correr contra el archivo real, auditar un resultado demasiado limpio,
y escribir un ejemplo ejecutable. El objetivo declarado —cero fallos silenciosos en
producción— sigue en pie; lo que este marcador mide es cuántos se atajaron antes.
