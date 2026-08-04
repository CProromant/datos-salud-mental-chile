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
- [x] **7. Un solo comando.** `obsm run` descarga, verifica hashes, descomprime, ingiere,
      normaliza, reconcilia y escribe gold. Se detiene en el primer error y reutiliza lo
      ya descargado.

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

> **Estado al 2026-07-27. Fase 1 cerrada.** La primera tasa existe y está verificada contra referencias
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

- [x] **1. Mapear las secciones** de salud mental en los manuales REM año por año. El mapeo
      vive en `config/rem_secciones.yml`, generado desde los diccionarios oficiales; 14 años
      mapeados (2009/2012 encriptados, 2013 sin la hoja).
- [x] **2. Ingestor por serie** con contrato declarado y falla ruidosa. `rem_salud_mental`
      filtra por `CodigoPrestacion` mientras lee: solo el 7,8 % del archivo es la sección P6.
- [x] **3. Silver:** personas bajo control por `comuna_cut` × período × concepto × grupo
      etario. Faltan ingresos, egresos por alta clínica y controles por profesional.
- [x] **4. Cobertura sobre población inscrita** (I-03). Requirió tres fuentes nuevas
      —`fonasa_inscritos`, `fonasa_padron_aps` y `deis_establecimientos`— y descubrir que el
      denominador solo sirve en 185 de 345 comunas (A-015). Faltan razón control/ingreso,
      abandono estimado e intensidad.

**Término:** serie comunal **semestral** 2014–presente para al menos: personas bajo control
en programa de salud mental por grupo etario, e ingresos por intento e ideación suicida.

> Corregido el 2026-07-27 al leer el archivo real. Decía «mensual 2018–presente» y ninguna
> de las dos cosas era exacta:
>
> - **La periodicidad es semestral, no mensual.** Población bajo control es un *stock* con
>   corte en junio y diciembre; en el archivo de 2023 los únicos meses presentes son 6 y 12.
>   La Serie A (actividad) sí es mensual, pero mide otra cosa. `CLAUDE.md` ya advertía que
>   no se mezclan.
> - **La serie puede empezar en 2014, no en 2018.** Hay datos desde 2009, pero los
>   diccionarios de 2009 y 2012 están encriptados y el de 2013 no trae la hoja P6; sin
>   diccionario las columnas del archivo no tienen significado (ver
>   `docs/05-CALIDAD.md#quiebres-rem`).

**Riesgo principal:** discontinuidades por cambio de manual interpretadas como cambios
reales. Mitigación: marcar quiebres de serie explícitamente en una tabla de `quiebres` que
todo consumidor de la API recibe junto con los datos.

> **Estado al 2026-07-29. Fase 2 cerrada en lo esencial.** Serie semestral 2014-2025 de
> población bajo control publicada y verificada: 1.048.618 personas en el programa a
> diciembre de 2025, 108.496 con depresión moderada. Y el indicador que la fase prometía sin
> saber si sería posible —cobertura sobre población inscrita— existe y se calcula en 185 de
> 345 comunas.
>
> **Lo que la fase costó de más.** Siete anomalías nuevas (A-010 a A-016). Tres de ellas
> —A-010, A-011, A-012— eran **invisibles procesando un solo año** y solo aparecieron sobre
> la serie completa: una etiqueta partida por su grafía hacía ver una caída del 99 % en
> ansiedad que no existía. La regla que salió de ahí: un ingestor probado contra un año no
> está probado.
>
> **La deuda de ingresos por intento e ideación suicida quedó saldada el 2026-07-29.**
> `gold.tabla_ideacion_intento` (I-05) los publica desde 2019-06, que es cuando el REM
> empezó a registrarlos, con el quiebre de serie recortado y las salvaguardas de `docs/06`
> impuestas por código: la función **exige** recursos de ayuda y se niega a producir la
> tabla sin ellos.
>
> Construirla destapó A-019: esos conteos **ya se publicaban** dentro de
> `poblacion_control_salud_mental.csv`, entre setenta conceptos, sin ninguna de las cuatro
> obligaciones que `docs/06` impone a las salidas con suicidio. No por omisión deliberada:
> el guardia existía y miraba códigos CIE-10, y el REM trae el suicidio por una etiqueta de
> texto. La política se hace cumplir sobre la puerta por la que el dato entra, no sobre la
> que uno imaginó.

---

## Fase 3 — Espera y acceso: Glosa 06 y GES (semanas 10–12)

> **Alcance corregido el 2026-07-29, después de bajar la fuente.** El criterio anterior
> pedía «casos en espera, mediana y percentil 90 de días, **por Servicio de Salud**» para
> psiquiatría. **Eso no lo publica nadie.** Verificado sobre dos informes reales: el
> desglose por especialidad nunca trae días, y las medianas por Servicio agregan todas las
> especialidades. Las dos dimensiones no se cruzan en ninguna fuente pública, aunque la
> letra b) de la propia glosa exige el cruce. Dejarlo escrito como criterio era prometer lo
> que no se puede cumplir.

Dos fuentes, complementarias y ninguna suficiente por sí sola:

| | `glosa06` (PDF) | `listaespera_minsal` (JSON) |
|---|---|---|
| Especialidad | ✅ psiquiatría adulta e infantil | ❌ agrega todas |
| Servicio de Salud | ❌ solo nacional | ✅ los 29 |
| Mediana de días | ❌ nunca por especialidad | ✅ desde 2022 |
| Serie | trimestral | trimestral, 2019-2025 |

- [x] **1. Ingestor de `listaespera_minsal`.** Hecho: `obsm espera` produce 2.340 filas
      publicables, 29 Servicios × 26 trimestres × 3 listas, con ficha de dataset.
- [x] **2. Parser del PDF de la Glosa 06.** Hecho: `obsm glosa06 <pdf>...` extrae la tabla
      de especialidades y su trimestre del contenido. Verificado contra los dos informes
      publicados, que ya traen cuatro formatos distintos entre sí.
3. Serie histórica desde el primer informe en formato estable. **Bloqueado por la fuente:**
   el índice del MINSAL solo enlaza los dos informes más recientes y los nombres de archivo
   no siguen patrón. Los históricos hay que conseguirlos uno a uno.
4. Indicador de garantías GES de salud mental retrasadas.
5. **Solicitar por Transparencia los «archivos digitales complementarios»** que el informe
   declara en su letra I). Si traen especialidad por establecimiento, el criterio original
   vuelve a ser alcanzable; si no, esta fase llega hasta donde llega la fuente.

**Término:** dos series trimestrales verificadas contra su fuente original — espera por
Servicio de Salud (todas las especialidades) y espera en psiquiatría adulta e infantil
(nacional) — con la limitación del cruce declarada en la ficha del indicador, no escondida.

**Riesgo principal:** el parser rompe con cada rediseño del informe. Mitigación: el test de
oro es un fixture por layout conocido; el parser declara qué layout detectó. Ya se
identificaron dos cambios entre 2025 y 2026 —la etiqueta de la especialidad cambia de caja
y de género, y el orden de la tabla pasa de alfabético a por magnitud—, así que el parser
nace sabiendo que ninguna de las dos cosas es estable.

---

## Fase 4 — Recursos y gasto (semanas 13–16)

> **Alcance corregido el 2026-07-29, después de bajar la fuente.** El criterio pedía
> «gasto real per cápita **en salud mental** por Servicio de Salud». **El presupuesto no
> permite calcularlo, y ahora está medido.** En toda la partida 16 hay tres glosas que
> nombran salud mental —«Colocación Pacientes con Enfermedades Mentales», «Programa de
> Apoyo a la Salud Mental Infantil» y «Centros de Prevención de Alcoholismo y Salud
> Mental»— que suman **12,70 mil MM$ sobre 25,24 billones de gasto ejecutado: 0,05 %**.
> El resto vive dentro de
> FONASA, del pago por GRD y de la atención primaria, sin distinguirse.
>
> El plan anticipaba «publicar rango, no punto». La realidad es más dura: **no hay con qué
> acotar el rango.** Un 0,05 % identificable no permite ni un piso creíble.
>
> Esto no es un obstáculo del proyecto: es el hallazgo. `docs/00` lista el financiamiento
> como uno de los once problemas de la salud mental chilena, y esto lo convierte en un dato
> verificable desde el propio presupuesto abierto del Estado.

1. **`dipres_ejecucion`** — verificada. CC0/CC BY, CSV a nivel programa, 205 cortes
   mensuales desde 2017, la partida 16 hasta sub-asignación con los 29 Servicios de Salud
   como capítulos separados. Es la fuente mejor publicada del proyecto.
2. **Indicador viable: gasto total en salud per cápita por Servicio de Salud.** No aísla
   salud mental —nada lo hace— pero da el contexto sobre el que discutir, y es una serie
   que hoy nadie publica consolidada por Servicio.
3. **Indicador NO viable: gasto en salud mental.** Se documenta por qué, con la medición,
   en vez de publicar una estimación que el presupuesto no sostiene.
4. Registro Nacional de Prestadores Individuales: psiquiatras y psicólogos, con las
   advertencias del caso (el registro dice dónde está inscrito el prestador, no dónde
   atiende ni cuántas horas).
5. Deflactor IPC del INE para pesos reales.

**Término:** serie anual de gasto real **total en salud** per cápita por Servicio de Salud,
más una nota metodológica que documente, con la cifra medida, por qué el gasto en salud
mental no es separable.

**Riesgo principal:** que alguien tome la fracción identificable —0,05 %— como si fuera el
gasto en salud mental. Mitigación: no publicar esa cifra como indicador, solo como
evidencia de la imposibilidad, y decirlo en la ficha.

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
   el mes seis.

   > **Corregido el 2026-08-03: no es tarea de la Fase 1.** El plan decía «conseguirlo es
   > tarea de la Fase 1, en paralelo al código» y eso resultó irreal. Un proyecto sin serie
   > propia que mostrar no puede pedirle a una sociedad científica que ponga su nombre, y
   > una revisión clínica solicitada en frío, sin respaldo, tiene pocas probabilidades. El
   > orden correcto es el inverso: **primero la evidencia de que la herramienta sirve,
   > después el respaldo.**
   >
   > Para que «todavía no» no se convierta en «nunca» por deriva, el gatillo queda escrito.
   > Se sale a buscar dueño institucional cuando se cumplan las tres:
   >
   > - [ ] **Seis series publicadas y descargables**, con ficha cada una. Van cinco; I-11
   >       (egresos por trastorno mental) es la sexta y no tiene bloqueo ético.
   > - [ ] **Un hallazgo citable que nadie más publique.** Ya hay dos candidatos medidos:
   >       el gasto en salud mental es el **0,05 %** identificable de la partida 16, y
   >       **ninguna fuente pública cruza especialidad con territorio** pese a que la
   >       Glosa 06 lo obliga.
   > - [ ] **Respuesta a las solicitudes de Transparencia** (vencen el 2026-08-31). Llegar
   >       con las licencias resueltas, o con la negativa documentada, es parte del caso.
   >
   > Cumplidas las tres, la conversación deja de ser «ayúdenme a construir esto» y pasa a
   > ser «esto ya existe y funciona; úsenlo». Es una posición distinta para pedir.

2. **Un revisor con competencia epidemiológica** para las fichas de indicador.
3. **Un revisor con competencia en salud mental y prevención de suicidio** para todo lo que
   se publique sobre suicidio. **Bloquea I-05 e I-12**, que están implementados y detenidos
   solo por esto. `docs/09` impide que lo resuelva quien construye los indicadores, así que
   no hay atajo propio: llega con el dueño institucional o con alguien dispuesto a revisar
   dos fichas acotadas. Mientras tanto las dos series quedan escritas, probadas y sin salir,
   que es el estado correcto y no una deuda.
4. **Las licencias de las fuentes.** Resuelto para el INE el 2026-07-27: publica bajo
   CC BY-SA 4.0, y como sus proyecciones son el denominador de toda tasa, su cláusula
   CompartirIgual obliga al derivado. El proyecto adoptó CC BY-SA 4.0 para `gold`
   (ADR 0005). Resuelto para `deis_establecimientos` el 2026-07-29: **CC0**, la primera
   fuente del proyecto con licencia libre declarada — y prueba de que MINSAL sí declara
   licencia cuando quiere, lo que fortalece el caso para pedirla sobre las demás.
   **Siguen sin confirmar la microdata de DEIS, el REM, SUBDERE y las dos de FONASA**: una
   fuente bajo CC BY o dominio público no da problema, pero una con cláusula no comercial
   obligaría a reabrir la decisión antes de publicar. Es una dependencia externa porque no
   se resuelve programando, se resuelve leyendo o preguntando al organismo. La vía concreta
   es una solicitud por Ley de Transparencia. **Las cuatro se enviaron el 2026-08-03**, con acuse de recibo y número de
   seguimiento (ver `docs/solicitudes/`). Plazo legal: **2026-08-31**; con prórroga,
   2026-09-14. El reloj ya corre.

## Métricas del propio proyecto

- Nº de fuentes verificadas y corriendo sin intervención manual.
- Días de latencia entre publicación oficial y disponibilidad en el observatorio.
- Nº de indicadores con ficha completa y test de reconciliación.
- Uso: descargas, citas, consultas de la API.
- Fallos silenciosos detectados en producción: objetivo cero, y cada uno genera un test.

**Marcador al 2026-08-03** (Fases 0 a 3 cerradas, Fase 4 reconocida):

| métrica | valor | al 2026-07-27 |
|---|---|---|
| fuentes verificadas con descarga real | 13 de 20 | 4 de 17 |
| ingestores funcionando | 8 | 2 |
| series publicadas | 5 (release v0.3.0) | 1 |
| indicadores activos con ficha y verificación externa | 4 (I-01, I-02, I-03, I-06) | 2 |
| indicadores implementados sin publicar | 3 (I-05, I-11, I-12) | 0 |
| anclas de reconciliación automáticas | 5, todas cuadrando | 5 |
| anomalías documentadas con reproducción y decisión | 24 | 9 |
| tests | 652 | 323 |
| fallos silenciosos detectados **antes** de producción | 10, cada uno con su test | 5 |

La última fila es la que importa y conviene leerla con cuidado: son defectos que no lanzaban
excepción y que habrían publicado números plausibles y falsos. Ninguno lo encontró el CI. Los
destaparon correr contra el archivo real, auditar un resultado demasiado limpio, y escribir
un ejemplo ejecutable. El objetivo declarado —cero fallos silenciosos en producción— sigue en
pie; lo que este marcador mide es cuántos se atajaron antes.

> **Lección de Fase 2 (2026-07-29), que no es sobre datos sino sobre método.** El defecto más
> caro de la fase no fue de código: fue concluir que una fuente publicaba cifras corruptas
> cuando estaban bien (A-015). La teoría predecía un patrón nítido y la serie lo confirmaba
> con **cero excepciones en 4.863 celdas**, y ese ajuste casi perfecto fue precisamente lo
> que la hizo convincente. Venía de que dos variables medían universos que casi coinciden,
> no de que una contuviera a la otra.
>
> Lo que faltó era lo más barato disponible: **leer el nombre completo de las variables**.
> Decían «Municipal» y «Beneficiaria». Se prefirió inferir el significado de la forma de los
> números antes que leer la etiqueta.
>
> Corolario operativo, al lado del de Fase 0 sobre el andamiaje desconectado: **un ajuste
> excelente contra los datos no valida la premisa**, y cuando un intermediario parece
> contradecirse, la pregunta no es qué le pasa al intermediario sino qué dice quien produjo
> el dato. Bajar la fuente original resolvió en una tarde lo que dos días de razonamiento
> sobre SINIM habían resuelto al revés.
