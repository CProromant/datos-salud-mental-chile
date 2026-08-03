# CHANGELOG

Formato: [Keep a Changelog]. Versionado de datos `AAAA.MM.N`, de código SemVer.
Un cambio metodológico que altere series ya publicadas exige versión mayor y mantener
disponible la versión anterior.

## [No publicado]

### Agregado
- **`deis_egresos`** — egresos hospitalarios, 2001-2024, verificado sobre siete archivos
  anuales completos. En 2023: 37.773 hospitalizaciones por trastorno mental y 7.683 egresos
  por lesión autoinfligida, que es el tramo entre las ~9.900 personas en control por intento
  suicida en APS y las ~2.000 muertes por suicidio al año. La URL no está enlazada de forma
  raspable —el índice de DEIS es un Ninja Tables por AJAX—: el patrón se recuperó del índice
  CDX de Wayback y después se comprobó contra el servidor real, año por año.
- **A-004 se repite exacta en egresos:** la lesión autoinfligida vive en `DIAG2`, no en
  `DIAG1`. Cero códigos X60-X84 en el diagnóstico principal, en los siete años.
- **Camino completo hasta `gold`,** con `obsm egresos <archivo>`: `silver.normalizar_egresos`,
  `gold.tabla_egresos_salud_mental` (**I-11**) y `gold.tabla_egresos_autoinfligida`
  (**I-12**). Sobre el archivo real de 2023: 327 filas comunales con 37.707 egresos por
  trastorno mental publicados de 37.773, y 291 filas con 7.136 de 7.683 por lesión
  autoinfligida. Cero celdas visibles entre 1 y k-1 en ambas.
- **I-12 nace con la puerta de `docs/06` cerrada,** igual que I-05: la firma exige
  `recursos_ayuda` y el CLI **no trae valor por defecto**, así que la serie de conducta
  suicida no se escribe sola. La revisión clínica sigue pendiente y el meta lo declara.
- **Tercer centinela territorial descubierto al correr el pipeline completo:** `88888` /
  `Extranjero`, 661 filas en 2023. El silver reportaba 141.033 filas sin territorio y los
  dos centinelas conocidos explicaban 140.372. De ahí salió `sin_territorio_sin_explicar`,
  que **tiene que ser cero**: si la fuente agrega un código nuevo, el balde de «comuna
  desconocida» se lo tragaría sin dejar rastro. Ahora las tres causas cuadran exacto.
- **Bug propio corregido antes de que llegara a los datos:** el enmascarado del ingestor
  recorría todas las columnas y convertía `_es_fila_total` al string `"False"`. Como
  `bool("False")` es `True`, el silver descartaba **todas** las filas creyéndolas totales y
  la tabla salía vacía sin un solo error. Lo destapó construir el transform, no los 62
  tests del ingestor.
- `grupo_edad` del silver de egresos pasa a llamarse `grupo_edad_fuente`: en el silver de
  defunciones ese nombre es la grilla quinquenal compatible con el INE, y compartirlo entre
  dos capas con significados distintos es cómo alguien estandariza contra la grilla
  equivocada sin que nada falle.

### Anomalías nuevas
- **A-021:** el archivo 2024 de DEIS trae 1.199.605 caracteres irrecuperables. Es UTF-8
  válido pero convertido desde latin-1 con reemplazo: `Ñuñoa` llega como `?u?oa`. No se
  repara —adivinar la letra sería inventar el dato— y solo daña glosas.
- **A-022:** el `*` es supresión de DEIS, no dato faltante, y saltó de 2,6 % (2019) a 7,9 %
  (2023). También enmascara `ANO_EGRESO`, así que un `groupby` por año descartaba el 8 % de
  2023 en silencio. Se imputa declarándolo en `anio_imputado`.
- **A-023:** 2021 está publicado con otro codebook (sexo numérico, 22 tramos quinquenales
  contra 12 decenales), y no son colapsables arriba de 79 años.

### Corregido
- **La versión del código estaba congelada en `0.2.0`.** Se etiquetó y publicó `v0.3.0` sin
  incrementarla, así que los trece archivos de ese release llevan
  `pipeline_version = "0.2.0"`, el mismo valor que los de `v0.2.0`: quien tenga uno de esos
  CSV no puede saber cuál de los dos releases lo produjo. Contradice `CLAUDE.md` §2.2 y
  `docs/07`. **Los archivos publicados no se reescriben** —serían datos distintos de los que
  la gente ya descargó— y el caso queda declarado acá y en las fichas. El código pasa a
  `0.3.0` y `tests/test_version.py` impide que se repita: exige que `pyproject.toml`,
  `__version__`, `PIPELINE_VERSION` y la última versión publicada del CHANGELOG coincidan.
- **El bloque «El denominador (cierre de Fase 2)» estaba rotulado `[No publicado]`** estando
  debajo de `[0.3.0]`, cuando su contenido —`fonasa_inscritos`, `deis_establecimientos`,
  I-03— es exactamente lo que sostiene `cobertura_salud_mental_aps.csv`, una de las series
  de ese release. Pasa a ser lo que siempre fue: parte de 0.3.0. Hay un test que ahora
  prohíbe que una sección no publicada quede debajo de una publicada.
- Fichas de dataset: la de cobertura decía «la mitad de sus filas» sin valor cuando son
  **casi dos tercios** (63,6 %), y no distinguía las 345 comunas de la grilla de las **185**
  que llegan a tener un valor. Ver la corrección en cada ficha.
- `docs/05-CALIDAD.md`: A-004 estaba listada antes que A-003, y la plantilla de ejemplo
  usaba el id `A-001`, el mismo de una anomalía real.
- `ine_ipc`: seis vías de acceso comprobadas y cerradas, documentadas en `docs/01`. Sigue
  `no_verificada` y sin URL inventada en el catálogo.

## [0.3.0] — 2026-08-02 — Tres series nuevas: cobertura, espera y psiquiatría

**Publicado.** Trece archivos, 106 MB. Descargas verificadas contra `SHA256SUMS.txt`.

> **Procedencia de este release.** Sus archivos llevan `pipeline_version = "0.2.0"`: la
> versión del código no se incrementó al etiquetar. El número no distingue este release del
> anterior; para identificarlos sirve `fecha_calculo`, que en estos archivos es del
> 2026-08-02. Corregido a partir de la versión siguiente.

Cinco series ahora. Las tres nuevas:

| Serie | Cobertura | Cifra de referencia |
|---|---|---|
| `cobertura_salud_mental_aps.csv` | 185 comunas, 2014-2025 | mediana 51,7 en control por mil inscritos |
| `listas_espera_servicio_salud.csv` | 29 Servicios, 2019-2025 | 264 días de mediana nacional |
| `espera_por_especialidad.csv` | nacional, 2025-2026 | 23.134 adultos esperando psiquiatra |

### Checklist de release (docs/07)
- `make test` y `make lint` en verde: 556 tests, ruff y mypy limpios.
- Anclas de reconciliación: **5 de 5** cuadran.
- Checklist ético de `docs/06`: **cero celdas visibles entre 1 y 4** en las tres, ninguna
  dimensión prohibida, procedencia completa en todas las filas.
- Revisión clínica y recursos de ayuda: **no aplican** — ninguna de las tres incluye
  suicidio. I-05, que sí lo incluye, queda fuera de este release por esa razón.
- DOI: no se genera. Zenodo quedó descartado.

### Lo que no cambia
Las dos series ya publicadas se regeneran idénticas. Este release agrega, no reemplaza.

### El denominador (cierre de Fase 2)

Lo que faltaba para que los conteos del REM significaran algo: **cuánta gente hay inscrita
en la atención primaria de cada comuna**. Tres fuentes nuevas y el indicador I-03.

### Agregado
- **`fonasa_inscritos`** — población inscrita validada en salud municipal, 345 comunas ×
  25 años (2001-2025), vía SINIM/SUBDERE. El dato lo produce FONASA pero no lo publica como
  archivo: su portal de datos abiertos es un WordPress con un plugin de gráficos.
- **`fonasa_padron_aps`** — el padrón por establecimiento, que fue lo que permitió entender
  el desajuste de universos de A-015.
- **`deis_establecimientos`** — maestro de establecimientos, **CC0**. Responde quién
  administra la APS de cada comuna: 210 comunas enteramente municipales, 114 mixtas y
  20 sin ningún establecimiento municipal.
- **I-03, cobertura del programa de salud mental en APS**
  (`gold.tabla_cobertura`): personas en control por mil inscritos. Mediana nacional de
  **51,7 por mil** en diciembre de 2025. Calculable en **185 de 345 comunas**; el resto
  declara por qué no.
- Tres comprobaciones independientes sobre el denominador, ninguna de las cuales borra ni
  imputa: coherencia con los tramos de beneficiarios, refutación por el propio numerador
  (quien está en control está inscrito) y fracción del padrón sobre la población comunal.
- `obsm rem cobertura`: el comando que produce la tabla. Se niega a correr si falta
  cualquiera de las cuatro capas silver y nombra el comando que falta, en vez de producir
  una tabla parcial.
- Ficha del dataset en `docs/DATASET-cobertura-salud-mental-aps.md`.

### Corregido
- **A-013:** desde ~2019 SINIM escribe `0` donde antes escribía `Sin Servicio`. Son 30
  comunas y 120 celdas; un `0` en un denominador da cobertura infinita. Se resuelven a nulo
  usando la serie completa de la comuna, que es evidencia que una sola fila no tiene.
- **A-014:** el CLI elegía el silver con `sorted(...)[-1]`, o sea por orden alfabético del
  nombre de archivo. `io.elegir_tabla` lo reemplaza en los seis sitios y **lanza con dos o
  más candidatos sin desempate explícito**. Al encenderlo aparecieron dos almacenes
  ambiguos reales: dos parquet idénticos del INE, y —el caso que la anomalía anticipaba en
  teoría— dos versiones **distintas** del bronze de FONASA, donde la correcta se venía
  eligiendo por accidente alfabético.
- **A-016:** el maestro de DEIS se regenera en vivo. Dos descargas separadas por minutos
  dieron hashes distintos y 1.996 filas con el nivel de atención reescrito —DEIS estaba
  unificando su glosario—. La fuente quedó **sin `sha256`** a propósito, verificándose por
  contrato de esquema.

### Corregido en la documentación
- **A-015 se documentó mal el primer día y la corrección quedó registrada junto al error.**
  Se concluyó que una fuente publicaba cifras corruptas; los valores estaban bien. La teoría
  encajaba con cero excepciones en 4.863 celdas, y ese ajuste casi perfecto venía de que dos
  variables miden universos que casi coinciden, no de que una contenga a la otra. Bastaba
  leer sus nombres completos: «Municipal» y «Beneficiaria».

### Métricas
- 463 tests (eran 337). 8 de 18 fuentes verificadas con descarga real. 3 indicadores activos.
- 16 anomalías documentadas.

### Reconocimiento de Fase 4
- **`dipres_ejecucion` verificada.** CC0/CC BY, CSV a nivel programa, 205 cortes mensuales
  desde 2017, partida 16 hasta sub-asignación con los 29 Servicios de Salud separados. Es la
  fuente mejor publicada del proyecto.
- **Alcance de Fase 4 corregido, con la cifra medida.** El gasto en salud mental **no es
  separable**: las glosas de la partida 16 que lo nombran suman 12,70 mil MM$ sobre
  25,24 billones de gasto ejecutado, un **0,05 %**. El resto vive dentro de FONASA, del pago por GRD y de la
  atención primaria. I-07 pasa a «gasto real per cápita **en salud**» y su ficha documenta,
  con la medición, por qué la pregunta original no tiene respuesta en esta fuente.
- Una trampa que vale por sí sola: buscar «MENTAL» como subcadena captura «InstruMENTAL
  Quirúrgico» e infla la cifra identificable.

### Fase 3, espera por especialidad
- **`obsm glosa06 <pdf>...`**: parser del informe trimestral e ingestor. Es la única fuente
  pública que aísla la espera por psiquiatría: 23.134 adultos y 12.585 niños y adolescentes
  al 31 de marzo de 2026. Ficha en `docs/DATASET-espera-por-especialidad.md`.
- Cuatro cosas cambian entre dos informes consecutivos —la etiqueta, el orden de la tabla,
  la página y el formato del período— y ninguna es estable. El parser acepta las dos formas
  observadas de cada una y falla ante una tercera.
- **A-018:** el informe de 2026 no suma su propio total declarado (faltan 11.478 registros,
  0,58 %). El de 2025 cuadra exacto. El parser captura todo lo que hay en el texto; el hueco
  está en la fuente. No usar la tabla para calcular participaciones.
- **A-017:** tensión dentro de `docs/06` entre «el cero sí se publica» y la supresión
  complementaria «la menor de las celdas restantes». No se cambia la política acá.

### Guardias nuevos
- Tests que comparan las cifras del README y el PLAN contra la realidad del repositorio
  (anomalías, fuentes verificadas, ingestores con entrada en el catálogo). Es la tercera vez
  que la documentación se descuelga; ahora CI lo atrapa.
- Tests que construyen el parser del CLI. Se agregaron porque 541 tests pasaban con el CLI
  roto: un subcomando duplicado hacía fallar `construir_parser` al primer uso y ningún test
  lo construía.

### Fase 3, primera serie
- **`obsm espera`**: un comando que baja los 30 JSON, ingiere, normaliza y escribe gold.
  2.340 filas: 29 Servicios de Salud más el nacional × 26 trimestres × 3 listas.
  Se aborta si falla cualquiera de las 30 descargas, porque la fila nacional es la suma
  exacta de los servicios y una serie incompleta da un total que no cuadra con sus partes.
- Ficha del dataset en `docs/DATASET-listas-espera-servicio-salud.md`.
- La tabla no baja a comuna: su unidad es el Servicio de Salud, y cuatro comunas pertenecen
  a dos Servicios a la vez. `silver.mapa_servicio_comuna` permite bajarla explícitamente.
- **A-017:** `docs/06` dice a la vez «el cero sí se publica» y que la supresión
  complementaria toma «la menor de las celdas restantes». Cuando la menor es un cero, las
  dos reglas chocan. El código implementa la segunda. No se cambia acá —`docs/09` prohíbe
  modificar la política para resolver un caso puntual— y queda un test que fija la conducta
  actual para que un cambio futuro sea deliberado.

### Fase 3, primer ingestor
- **`listaespera_minsal` ingerido.** 780 filas, 30 series, 26 trimestres (2019-03 a
  2025-06). Nacional al 2025-06: 2.699.409 registros esperando consulta de especialidad,
  mediana 264 días. Por Servicio: Metropolitano Norte 437 días contra Aconcagua 123.
- Tres trampas que el fixture no tenía y el archivo real sí, cada una con test:
  `promedio` y `mediana` son **días** y traen decimales legítimos (519 de 692 celdas de
  `ges_promedio`) —el caso inverso a A-010, donde los decimales estaban en un conteo y sí
  eran un error—; el campo `servicio` es un slug (`ARICA_Y_PARINACOTA`) y no el nombre de
  despliegue; y el de O'Higgins lleva apóstrofo tipográfico U+2019, con el que responde 200
  y sin el que da 404.

### Reconocimiento de Fase 3
- **`listaespera_minsal`** verificada: fuente que no estaba en el catálogo. JSON por
  Servicio de Salud en `listaesperasalud.cl`, serie trimestral 2019-2025, con registros,
  pacientes, promedio y mediana de días. 780 filas, 30 series. Nacional al 2025-06:
  2.699.409 registros esperando consulta de especialidad, mediana 264 días.
- **`glosa06`** verificada sobre dos informes reales. Es texto, no escaneo. Trae psiquiatría
  adulta (22.963) e infanto-adolescente (13.960) al 30-09-2025.
- **Alcance de Fase 3 corregido.** El criterio pedía mediana de días de psiquiatría por
  Servicio de Salud y **ninguna fuente pública lo publica**: el desglose por especialidad
  nunca trae días, y las medianas por Servicio agregan todas las especialidades. La letra b)
  de la propia glosa exige ese cruce. El criterio de término se reescribió para prometer lo
  que las fuentes permiten, y la limitación quedó en la ficha de I-06.

### Pendiente antes de publicar esta serie
- Licencias de la microdata de DEIS, el REM, SUBDERE y las dos fuentes de FONASA.

## [0.2.0] — 2026-07-27 — Primera serie publicable (Fase 1)

Primer release con datos. La serie es la **tasa comunal de mortalidad por suicidio,
Chile 2002-2023** (dataset `2026.07.1`): 346 comunas x 22 años, con tasa cruda,
estandarizada por edad, suavizada por Bayes empírico y años de vida potencial perdidos.

### Verificado contra fuentes externas
- Defunciones totales 2023 = 122.218 y 2020 = 126.169: **exacto** contra el Anuario de
  Estadísticas Vitales del INE.
- Población nacional 2020 y 2023: **exacto** contra las proyecciones del INE.
- Tasa nacional de suicidio 2015-2023 entre 8,0 y 10,6 por 100.000, dentro del rango
  publicado para Chile. AVPP de 38,8 años por muerte.
- Conservación de casos: 46.810 = 40.730 dentro de la ventana + 6.080 declarados fuera.

### Agregado
- `obsm run`: el pipeline completo en un comando. Descarga, verifica hashes, descomprime,
  ingiere, normaliza, reconcilia y escribe gold. Se detiene en el primer error.
- Ingestor `ine_proyecciones` y normalización del denominador en silver.
- Reconciliación **automática** contra `config/anclas.yml`: cinco anclas con procedencia,
  evaluadas antes de publicar. Si una no cuadra, no se escribe nada.
- Tasa estandarizada por edad con IC 95 % y AVPP en gold, con supresión extendida a todas
  las columnas derivadas.
- `ejemplos/practica.py`: ocho secciones ejecutables para aprender la herramienta.
- Ficha del dataset en `docs/DATASET-suicidio-comunal.md`.

### Corregido
- Nueve anomalías documentadas en `docs/05-CALIDAD.md`. Cinco eran defectos que **no
  lanzaban excepción** y habrían publicado números plausibles y falsos: cero suicidios en
  27 años por leer la columna de diagnóstico equivocada (A-004), una comuna inventada por
  validar el formato del CUT y no su existencia (A-007), doce años futuros con tasa cero,
  y el desglose por método —prohibido en docs/06— autorizado por un error de tipeo en
  `es_publicable`.
- La descarga no funcionaba contra las fuentes reales: user-agent rechazado con 403 y
  cadena de certificados incompleta. Resuelto con user-agent de navegador y `truststore`.
- `source_version` y `poblacion_version` iban en null en las 7.612 filas.

### Licencias
- Se investigaron DEIS y SUBDERE: **ninguna declara licencia** para el archivo que se usa.
  Se evaluó publicar bajo CC BY-NC-SA y no es legalmente posible —la cláusula 3(b) de
  CC BY-SA 4.0 del INE exige los mismos elementos de licencia—. Se mantiene CC BY-SA 4.0
  y la postura sobre uso comercial queda como norma en `USO-ACEPTABLE.md`.

### Métricas
- 337 tests. 4 de 17 fuentes verificadas con descarga real. 2 indicadores activos.

## [0.1.0] — 2026-07-26 — Andamiaje (Fase 0)

### Agregado
- Estructura del proyecto, documentación normativa (`docs/00` a `docs/09`), ADRs y
  playbook de sesiones.
- `territorio`: normalización de nombres de comuna con alias observados, códigos CUT como
  texto, vigencias regionales (caso Ñuble), tabla DPA semilla con validación de completitud.
- `cie10`: agrupadores de salud mental, suicidio, intención indeterminada, consumo,
  demencias, con política de publicación embebida.
- `quality`: supresión por umbral k con supresión complementaria, detección de filas de
  total, reconciliación contra anclas, validaciones estructurales.
- `indicators.tasas`: tasa cruda, estandarización directa (estándar OMS), suavizado
  bayesiano empírico Poisson-Gamma, AVPP, SMR.
- `ingest`: contrato base con falla ruidosa ante cambio de esquema; ingestor de defunciones
  DEIS funcional contra fixture.
- `transform`: silver (territorio, edad, clasificación) y gold (denominadores, tasas,
  supresión, procedencia).
- CLI: `sources list/verify/show`, `territorio validar/resolver`, `ingest`, `build
  silver/gold`, `qa`.
- 174 tests; CI con tests, lint y verificación de que no se versionen datos.

### Licencias
- Código MIT; datos derivados CC BY-SA 4.0; normas de uso en `USO-ACEPTABLE.md`, separadas
  de la licencia a propósito.
- La licencia de datos pasó de CC BY 4.0 a CC BY-SA 4.0 el 2026-07-27 (`docs/adr/0005`):
  el INE publica el denominador de toda tasa bajo CC BY-SA 4.0 y su CompartirIgual obliga
  al derivado. Sigue permitiendo uso comercial.

### Decisiones registradas
- ADR 0001: stack mínimo (Parquet + DuckDB + estático).
- ADR 0002: marco territorial vigente como principal.
- ADR 0003: publicación de suicidio por agrupador, nunca por método.

### Conocido y pendiente
- **Ninguna fuente verificada todavía.** Todas las URLs del catálogo están marcadas
  `no_verificada` y el pipeline de producción está bloqueado por diseño.
- Tabla DPA incompleta (16 de 346 comunas): completar desde la fuente oficial.
- Rangos CIE-10 y pesos de la población estándar pendientes de contraste con las
  publicaciones originales.
