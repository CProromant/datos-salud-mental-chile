# 01 — Catálogo de fuentes

> **Regla de honestidad del catálogo.** Ninguna URL de este documento fue confirmada con una
> descarga real desde este repositorio, porque el entorno de desarrollo no tiene salida a
> dominios de gobierno de Chile. Cada ficha declara el **origen de la URL**:
>
> - `busqueda_web` — la URL apareció literalmente en resultados de búsqueda del 2026-07-26.
>   Probablemente correcta, igualmente debe verificarse.
> - `por_confirmar` — se sabe que el organismo publica esto, pero la URL exacta no está
>   confirmada. **No copiar a código sin verificar.**
>
> El primer trabajo de la Fase 1 es correr `obsm sources verify` en una máquina con red y
> promover fuentes a `verificada` con fecha. Hasta entonces el pipeline se niega a tratarlas
> como estables.

Formato de ficha: qué contiene · granularidad · latencia · formato · trampas · uso en el
observatorio.

---

## A. Mortalidad y morbilidad

### A1. `deis_defunciones` — Defunciones con causa básica (DEIS/MINSAL)

- **Contiene:** registro de defunciones con causa básica CIE-10, sexo, edad, comuna de
  residencia y de ocurrencia, fecha.
- **Granularidad:** registro individual desidentificado, agregable a comuna×año.
- **Cobertura temporal:** series largas (desde los noventa en adelante, con corte CIE-9/CIE-10
  en 1997-1998).
- **Latencia:** anual. **Los últimos dos años son preliminares** por el proceso de depuración
  y codificación.
- **Formato:** CSV en el portal de datos abiertos DEIS.
- **URL raíz:** `https://deis.minsal.cl/#datosabiertos` — *origen: busqueda_web*.
  Espejo probable en `https://datos.gob.cl/organization/ministerio_de_salud` — *busqueda_web*.
- **Trampas:**
  - Encoding inconsistente entre años; separador que puede ser `,` o `;`.
  - Cambio CIE-9 → CIE-10 corta la comparabilidad hacia atrás.
  - Comuna de residencia vs. de ocurrencia: para tasas territoriales se usa **residencia**.
    Usar ocurrencia infla las comunas con hospital grande.
  - Defunciones de residentes en el extranjero y comuna ignorada: van a un código
    `comuna_cut = "99999"`, nunca se reparten.
  - Codificación de intención indeterminada (Y10–Y34): en Chile una fracción de suicidios
    puede quedar ahí. Se usa como **análisis de sensibilidad**, no en la serie principal.
- **Uso:** mortalidad por suicidio (X60–X84 + Y87.0), mortalidad por trastornos mentales y
  del comportamiento (F00–F99 como causa básica), AVPP.

### A2. `deis_egresos` — Egresos hospitalarios

**Verificada el 2026-08-02**: siete archivos anuales abiertos y contados por completo
(2001, 2010, 2015, 2019, 2021, 2023, 2024).

- **Contiene:** egresos de establecimientos públicos y privados, con diagnóstico principal
  CIE-10 (`DIAG1`), causa externa (`DIAG2`), días de estada, condición al alta, previsión,
  y comuna y región **de residencia**.
- **NO contiene establecimiento ni edad exacta.** La entrega pública viene desidentificada:
  solo hay tramos etarios y una marca de pertenencia al SNSS. La ficha anterior prometía
  ambos campos y estaba equivocada. Sin establecimiento **no se puede** medir disponibilidad
  de camas ni atribuir egresos a un hospital, así que ese uso queda descartado.
- **Granularidad:** registro de egreso desidentificado, agregable a comuna×año.
- **Cobertura temporal:** 2001–2024, un ZIP por año, todos respondiendo el 2026-08-02.
- **Volumen:** ~1,6 millones de egresos al año; el CSV descomprimido pesa entre 220 y 290 MB.
- **Formato:** ZIP con un CSV (separador `;`) y el diccionario de datos en XLSX.
- **Encoding:** latin-1 hasta 2023, UTF-8 desde 2024.
- **URL:** `https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_{anio}.zip`
  — *origen: verificada_en_sesion*. El índice de `deis.minsal.cl` es un Ninja Tables que se
  arma por AJAX y no es raspable; el patrón se recuperó del índice CDX de Wayback y
  **después** se comprobó contra el servidor real, año por año.
- **Licencia:** sin declarar, igual que el resto del repositorio DEIS. Ver `LICENSE-DATA.md`.
- **Trampas:**
  - **Un egreso ≠ una persona**: los reingresos cuentan varias veces y no hay identificador
    de paciente, así que es imposible deduplicar. **No usar como prevalencia.**
  - **La lesión autoinfligida está en `DIAG2`, no en `DIAG1`** — misma trampa que
    defunciones ([A-004](05-CALIDAD.md#a-004)). En 2023: 0 códigos X60–X84 en `DIAG1` y
    7.683 en `DIAG2`. Un agrupador aplicado solo al diagnóstico principal devuelve cero
    sin lanzar ningún error.
  - **`*` es supresión aplicada por DEIS**, no dato faltante, y desde 2023 alcanza al 8 %
    de las filas: los totales comunales dejan de sumar el nacional. Ver
    [A-022](05-CALIDAD.md#a-022).
  - **`99999` / `Ignorada`** es residencia desconocida, un centinela distinto del anterior.
  - **2021 usa otro codebook** (sexo numérico, 22 tramos quinquenales) y el esquema varía
    entre 15, 16 y 18 columnas según el año. Ver [A-023](05-CALIDAD.md#a-023).
  - **El archivo 2024 llega con los acentos destruidos en origen**, irrecuperables. Solo
    afecta glosas; los códigos están intactos. Ver [A-021](05-CALIDAD.md#a-021).
  - El sector privado reporta con calidad heterogénea.
- **Uso:** hospitalizaciones por trastorno mental (F00–F99 en `DIAG1`: 37.773 en 2023),
  egresos por lesión autoinfligida (X60–X84 en `DIAG2`: 7.683 en 2023), estada media.
- **Por qué importa:** es el eslabón que faltaba entre el control ambulatorio del REM y la
  mortalidad de DEIS. Los 7.683 egresos por lesión autoinfligida de 2023 se ubican entre
  las ~9.900 personas en control por intento suicida en APS y las ~2.000 muertes por
  suicidio al año.

### A3. `deis_urgencias` — Atenciones de urgencia

- **Contiene:** atenciones de urgencia agregadas por establecimiento, semana y causa
  agrupada; incluye una agrupación de causas externas.
- **Latencia:** semanal.
- **URL raíz:** portal de datos abiertos DEIS — *por_confirmar*.
- **Trampas:** la agrupación de causas es gruesa y cambia; puede no permitir aislar lesión
  autoinfligida con precisión. **Verificar antes de prometer este indicador.**
- **Uso:** señal de alta frecuencia para alertas; nunca como conteo clínico exacto.

---

## B. Actividad de la red y población bajo control

### B1. `rem_salud_mental` — Resúmenes Estadísticos Mensuales (REM)

- **Contiene:** producción y población bajo control de todos los establecimientos de la red
  pública. Las secciones de salud mental cubren ingresos al programa, población bajo control
  por diagnóstico y grupo etario, controles por tipo de profesional, egresos por alta
  clínica, y rehabilitación de personas con trastornos psiquiátricos.
- **Granularidad:** establecimiento × mes (algunas series, semestral).
- **Latencia:** aprox. un mes de desfase declarado en la normativa de tributación.
- **Formato:** planillas y bases consolidadas; manuales anuales en PDF que definen cada
  sección.
- **URL raíz:** `https://repositoriodeis.minsal.cl/` — *origen: busqueda_web*. Manuales
  observados en rutas del tipo
  `.../ContenidoSitioWeb2020/REM/2025/SERIE/Manual Series REM 2025-2026 SERIE A -BS-BM- DV1.2.pdf`
  y `.../REM/2026/SERIE/MANUALREMP2026Version1.1.pdf` — *busqueda_web*.
- **Trampas (esta es la fuente más traicionera del proyecto):**
  - **Las secciones se renumeran entre manuales.** Nunca referenciar por número: mapear por
    nombre normalizado de sección y validar contra el manual del año. El mapeo vive en
    `config/rem_secciones.yml`, con una entrada por año.
  - Serie A (actividad) vs Serie P (población bajo control) tienen periodicidad distinta;
    P se recoge en junio y diciembre. Mezclarlas produce dobles conteos.
  - Un establecimiento que deja de reportar un mes aparece como caída del 100%. Distinguir
    "cero real" de "no reportado" exige una tabla de establecimientos esperados por mes.
  - Códigos DEIS de establecimiento cambian; hace falta una tabla de equivalencias histórica.
  - Estrategias (CESFAM, COSAM, CECOSF, SAPU) reportan bajo códigos propios: agregar a comuna
    exige el maestro de establecimientos.
- **Uso:** cobertura, ingresos por ideación e intento suicida, intensidad de tratamiento,
  distribución de la carga entre APS y especialidad.

### B2. `deis_establecimientos` — Establecimientos de salud (DEIS)

- **Contiene:** 5.717 establecimientos con código DEIS, nombre, tipo, nivel de atención,
  dependencia administrativa, comuna, Servicio de Salud y estado de funcionamiento.
  33 columnas, separador `;`, UTF-8, 2,4 MB.
- **Uso:** llave de agregación del REM y de egresos, **y** la respuesta a quién administra la
  atención primaria de cada comuna — de lo que depende que un denominador de cobertura
  signifique algo.
- **Verificada** el 2026-07-29 con descarga real desde `datos.gob.cl`.
- **Licencia: CC0.** La **única** fuente del proyecto con licencia libre declarada: sin
  restricción de uso ni obligación de atribución.
- **El hallazgo que la hace valiosa acá.** De 344 comunas con APS pública, **210** la tienen
  enteramente municipal, **114** son mixtas y **20 no tienen ningún establecimiento
  municipal**. Pesado por población: 58,9 % de Chile vive donde la APS es toda municipal,
  38,3 % en comunas mixtas y 2,8 % donde no hay APS municipal. Como `fonasa_inscritos` es un
  padrón **municipal** y el REM cuenta actividad de **toda** la APS pública, esto es
  exactamente el mapa de dónde se puede calcular cobertura y dónde no.
  Las 20 comunas sin APS municipal —Tocopilla, Andacollo, Isla de Pascua, Llaillay,
  Hualaihué, Coyhaique, Aisén…— coinciden con las que SINIM marca «Sin Servicio»: dos
  fuentes independientes señalando las mismas comunas.
- **Trampa 1 — dos columnas de código.** `EstablecimientoCodigo` es la vigente y calza con
  las 1.889 del padrón de FONASA. `EstablecimientoCodigoAntiguo` usa otro formato (`03-216`)
  y da **cero** coincidencias; elegir la primera columna que aparezca toma la equivocada.
- **Trampa 2 — el archivo se regenera en vivo.** Dos descargas separadas por minutos dieron
  hashes distintos y **1.996 filas** con el nivel de atención reescrito: DEIS estaba
  unificando las grafías duplicadas (`Primario`→`Primer Nivel`, `Secundario`→`Segundo
  Nivel`) justo en ese momento. Por eso esta fuente **no lleva `sha256`** en el catálogo y
  se verifica por contrato de esquema. Ver [A-016](05-CALIDAD.md#a-016).
- **Trampa 3 — `EstadoFuncionamiento` cambia de caja.** «Vigente en Operación Habitual» y
  «Vigente en operación habitual» son el mismo estado; comparar exacto descarta 209 vigentes.
- **Trampa 4 — es UTF-8.** Leerlo como latin-1 no falla: produce `OperaciÃ³n`, que después no
  calza con ningún filtro y hace desaparecer esos establecimientos en silencio.
- **Trampa 5 — es un corte actual, no histórico.** Trae `FechaInicioFuncionamientoEstab` y
  `FechaCierre`, pero la fotografía es la de hoy. Aplicarlo a años pasados atribuye al pasado
  la organización presente; para una serie hay que reconstruir vigencias, que todavía no se
  hace.

---

## C. Acceso y garantías

### C1. `glosa06` — Lista de espera No GES y garantías GES retrasadas

- **Contiene:** casos en espera y tiempos (mediana, percentiles) de consulta nueva de
  especialidad y cirugía electiva, por Servicio de Salud y especialidad; y garantías GES
  retrasadas. Informe exigido por la Ley de Presupuestos (Partida 16, Glosa 06).
- **Granularidad:** Servicio de Salud × especialidad × trimestre.
- **Latencia:** trimestral, con algunos meses de desfase.
- **Formato:** **PDF**. No hay CSV oficial equivalente. Aquí está buena parte del valor
  agregado del observatorio.
- **URLs:** índice en `https://www.minsal.cl/eje-tiempos-de-espera/` — *busqueda_web*.
  Ejemplos de informes observados: `.../wp-content/uploads/2025/11/1764018133827_Glosa-06-LE-III-trimestre-2025.pdf`
  y `.../wp-content/uploads/2026/07/Glosa-06-letra-a-b-c-i-j-k-comun-a-la-partida-1er-trimestre-1.pdf`
  — *busqueda_web*.
- **Trampas:**
  - El nombre de archivo no sigue patrón estable: hay prefijos numéricos y sufijos variables.
    Hay que scrapear el índice, no construir URLs.
  - El layout de tablas cambia entre años; el parser debe declarar el layout detectado y
    fallar si no reconoce ninguno.
  - "Casos" ≠ "personas": una persona puede tener varias interconsultas. Los informes lo
    explicitan; el indicador debe hacerlo también.
  - La lista se cuenta desde la emisión de la interconsulta, no desde el inicio del síntoma:
    subestima la espera real vivida.
  - Cambios de criterio de depuración de la lista alteran el nivel sin que cambie el acceso.
- **Uso:** espera en psiquiatría adulto e infanto-adolescente; garantías GES de salud mental
  retrasadas.

**Verificada el 2026-07-29** sobre dos informes reales (III trim 2025 y I trim 2026): se
abrieron, se extrajo el texto y se ubicó la cifra de psiquiatría.

- **Es texto, no escaneo.** 55-56 páginas producidas desde Word. `PyMuPDF` extrae limpio y
  detecta 40-76 tablas por documento. No hace falta OCR.
- **Lo que sí trae** — la Tabla 15 desglosa registros por especialidad:

  | | Psiquiatría adulta | Psiquiatría infanto-adolescente |
  |---|---|---|
  | al 30-09-2025 | 22.963 | 13.960 |
  | al 31-03-2026 | 23.134 | 12.585 |

- **Lo que NO trae, y es el límite de la fase:** el desglose por especialidad **nunca**
  incluye días de espera. Verificado en los dos informes — ninguna página contiene a la vez
  una especialidad y la palabra «mediana». Las medianas viven en la Tabla 12, por Servicio
  de Salud y con todas las especialidades sumadas. **Las dos dimensiones no se cruzan en
  ninguna parte**, pese a que la letra b) de la propia glosa exige «una tabla desglosada por
  cada una de las especialidades, que incluya (…) el promedio y la mediana de días».
- **Trampa nueva 1 — la etiqueta cambia de caja y de género** entre informes:
  `PSIQUIATRÍA ADULTO` (2025) contra `Psiquiatría adulta` (2026). Es
  [A-012](05-CALIDAD.md#a-012) otra vez; agrupar por llave normalizada, nunca por la cadena
  cruda.
- **Trampa nueva 2 — el orden de la tabla cambia:** alfabético en 2025, por magnitud
  descendente en 2026. Anclar en la posición de la fila rompe al primer informe nuevo.
- **Pendiente:** el informe declara en su letra I) que el detalle por establecimiento va en
  **«archivos digitales complementarios»** que no están enlazados en el sitio. Conseguirlos
  —por Transparencia— es lo único que permitiría cruzar especialidad con territorio.

### C1b. `listaespera_minsal` — Visualizador de listas de espera (series trimestrales)

- **Contiene:** serie trimestral por Servicio de Salud con tres listas —consulta nueva de
  especialidad, intervención quirúrgica, garantías GES retrasadas— y cuatro métricas cada
  una: registros, pacientes, promedio y **mediana** de días.
- **Granularidad:** Servicio de Salud × trimestre. 29 servicios más el nacional.
- **Cobertura:** 2019-03 a 2025-06 (26 trimestres, 780 filas).
- **Formato:** **JSON**, uno por servicio, sin sesión ni token:
  `https://www.listaesperasalud.cl/data/data_{SERVICIO}.json`
- **Verificada** el 2026-07-29 bajando los 29 servicios más el nacional.
- **Por qué importa:** tiene exactamente la dimensión que al PDF de la Glosa 06 le falta
  —mediana de días por Servicio— y le falta la que el PDF sí tiene. **Son complementarias y
  ninguna las cruza.** Nacional al 2025-06: 2.699.409 registros en espera de consulta de
  especialidad, mediana 264 días.
- **Lo que NO trae: especialidad.** Las claves agregan todas las especialidades juntas, así
  que no permite aislar psiquiatría. Para eso hay que ir al PDF.
- **Trampa 1 — la mediana no existe antes de 2022.** Cobertura por año: 0 % en 2019-2021,
  50 % en 2022, 100 % desde 2023. Una tendencia de medianas que arranque antes está
  comparando contra vacío.
- **Trampa 2 — la lista GES está mal cubierta:** `ges_pacientes` aparece en el 3 % de las
  celdas y `ges_mediana` cae al 3 % en 2025.
- **Trampa 3 — el apóstrofo de O'Higgins.** Su archivo usa apóstrofo **tipográfico**
  (U+2019): `data_SERVICIO_DE_SALUD_O’HIGGINS.json` responde 200 y la misma URL con `'`
  da 404. Es la familia de trampas que `territorio.ALIAS` ya cubre para nombres de comuna,
  ahora en una ruta HTTP.
- **Sin `sha256`:** los archivos se actualizan cada trimestre.

### C2. `ges_decreto` — Decreto GES vigente y garantías de oportunidad

- **Contiene:** problemas de salud garantizados, con sus plazos. Relevantes: depresión,
  esquizofrenia primer episodio, trastorno bipolar, consumo problemático en menores, y desde
  el decreto 2025-2028, tratamiento hospitalario de menores de 15 años con depresión grave y
  riesgo suicida.
- **Formato:** decreto y normas técnicas, PDF.
- **URL:** MINSAL / Superintendencia de Salud — *por_confirmar*.
- **Uso:** definir qué está garantizado y calcular el complemento: qué queda fuera.

---

## D. Recursos y financiamiento

### D1. `prestadores_individuales` — Registro Nacional de Prestadores Individuales

- **Contiene:** profesionales de salud registrados, con especialidad certificada.
- **Organismo:** Superintendencia de Salud. **URL:** *por_confirmar*.
- **Trampas serias:**
  - El registro indica inscripción, **no dónde ejerce ni cuántas horas ni si sigue activo**.
  - La dirección registrada puede ser administrativa. Cualquier tasa "por comuna" derivada de
    aquí es una aproximación gruesa y debe rotularse como tal.
  - Psicólogos: no hay certificación obligatoria de especialidad clínica, por lo que el
    conteo no distingue clínicos de otros.
- **Uso:** densidad de psiquiatras por 100.000 a nivel regional (**no comunal**), con
  advertencia explícita.

### D2. `dipres_ejecucion` — Ejecución presupuestaria, Partida 16

- **Contiene:** ejecución mensual del presupuesto del Gobierno Central a cuatro niveles
  —Nacional, Partida, Capítulo y Programa—, con diccionario de datos. La partida 16
  (MINISTERIO DE SALUD) baja hasta **sub-asignación**: 8.058 filas en el corte a junio de
  2026, con los 29 Servicios de Salud como capítulos separados.
- **Granularidad:** sub-asignación × mes. **Cobertura:** 205 cortes mensuales, 2017-2026.
- **Verificada** el 2026-07-29 con descarga real (9.456.706 bytes, 39.381 filas,
  19 columnas, separador `;`, UTF-8).
- **Licencia: CC0 y CC BY según el corte** (65 y 135 datasets respectivamente). Las dos son
  compatibles con la CC BY-SA de `gold`. **Es la fuente mejor publicada del proyecto.**

#### El hallazgo: el gasto en salud mental no es separable

En toda la partida 16 hay **tres glosas** que nombran salud mental:

| Glosa | Nivel | Ejecutado a junio 2026 |
|---|---|---|
| Colocación Pacientes con Enfermedades Mentales | Sub-Asignación | 12,69 mil MM$ |
| Centros de Prevención de Alcoholismo y Salud Mental | Asignación | 0,01 mil MM$ |
| *(«Programa de Apoyo a la Salud Mental Infantil» aparece como ingreso por transferencia, no como gasto)* | | |

**12,70 mil MM$ sobre 25,24 billones de gasto ejecutado: 0,05 %.** El resto —consultas de psiquiatría,
hospitalización, programas de APS, farmacia— vive dentro de FONASA, del pago por Grupo
Relacionado de Diagnóstico y del Programa de Atención Primaria, sin distinguirse.

No es un defecto del dato ni una limitación del pipeline: **el presupuesto no está
estructurado para responder la pregunta.** Cambió el alcance de la Fase 4 y la definición de
[I-07](04-INDICADORES.md#i-07).

- **Trampa 1 — no hay URL estable.** Cada corte mensual es un dataset CKAN con UUID propio.
  Construir la ruta por patrón falla; hay que consultar la API de `datos.gob.cl`.
- **Trampa 2 — «MENTAL» como subcadena captura «InstruMENTAL Quirúrgico».** Es material quirúrgico e infla la cifra identificable a la mitad. Hay que usar
  frontera de palabra, igual que `quality._RE_TOTAL_PREFIJO` hace con «Totoral».
- **Trampa 3 — los montos traen punto de miles** y ningún decimal.
- **Uso previsto:** gasto total en salud por habitante y Servicio de Salud, deflactado con
  el IPC. **No** gasto en salud mental, que esta fuente no permite calcular.

### D3. `ine_ipc` — Índice de precios al consumidor

- **Uso:** deflactar. Todo monto se guarda nominal; el real se deriva
  (`CLAUDE.md` §5). Es la dependencia que falta para
  [I-07](04-INDICADORES.md#i-07).
- **Estado: `no_verificada`.** No se encontró un archivo descargable del índice. **URL:**
  *por_confirmar* — y no se escribe ninguna en `config/sources.yml` hasta tenerla.

**Seis vías cerradas, todas comprobadas el 2026-08-02.** Se anotan para que la próxima
sesión no las repita:

| Vía | Resultado |
|---|---|
| Página del IPC en `ine.gob.cl` | 200, 219 enlaces, **cero** a archivos: los arma JavaScript |
| `stat.ine.cl` (INE.STAT, un .Stat/SDMX) | 381 datasets, **ninguno** de precios; es de empleo e ingresos |
| `calculadoraipc.ine.cl` | **La calculadora está rota**: su propio `js/events.js` y su endpoint `reportes/xmlVariacionGrilla.asp` responden 404 |
| `datos.gob.cl`, dataset `ipc` del INE | Existe, pero con **cero recursos**: es un puntero de vuelta a la página del INE |
| Índice CDX de Wayback sobre `ine.gob.cl` | Respuesta vacía (la misma técnica sí funcionó para `deis_egresos`) |
| `si3.bcentral.cl` (BDE del Banco Central) | **Exige inicio de sesión**; no entrega datos de forma anónima |

**Complicación de licencia, aparte de la de acceso.** El dataset del INE en `datos.gob.cl`
está marcado **CC Non-Commercial**, que contradice los términos generales CC BY-SA 4.0 del
mismo organismo — la misma contradicción ya registrada para `ine_vitales_anuario` en
`LICENSE-DATA.md`. Si el deflactor terminara siendo CC-NC, **no podría alimentar `gold`**:
`ADR 0005` obliga a CC BY-SA y las dos licencias son incompatibles. Conviene resolver la
licencia **antes** de construir el ingestor, no después.

**Caminos que quedan, en orden de preferencia:**

1. **Solicitud por Ley de Transparencia al INE** pidiendo la serie del IPC en formato
   reutilizable y su licencia por escrito. Resuelve acceso y licencia de una vez, y ya hay
   cuatro solicitudes redactadas en `docs/solicitudes/` que sirven de molde.
2. **Credenciales del Banco Central.** El registro en la BDE es gratuito y su API entrega
   la serie; requiere una acción humana que la sesión no puede hacer sola.
3. **Anexo estadístico del boletín mensual del INE**, si publica el índice en XLSX. Los
   boletines están en `/docs/default-source/índice-de-precios-al-consumidor/boletines/`,
   pero los nombres llevan hash de Sitefinity y no son deducibles.

**Lo que NO se va a hacer:** tomar el IPC de un agregador de terceros (`mindicador.cl` y
similares). Funcionan, pero el argumento central del proyecto es la trazabilidad, y un
intermediario sin trazabilidad propia no puede ser el denominador de una serie de pesos
reales.

---

## E. Denominadores y contexto

### E0. `subdere_cut` — Códigos Únicos Territoriales, el maestro de la DPA

**Verificada el 2026-07-27.** Es la fuente **crítica** del proyecto y llevaba desde Fase 1
sin ficha propia, mencionada solo de pasada en la sección de licencias.

- **Contiene:** la planilla de códigos y nombres de la División Político-Administrativa:
  región, provincia y comuna, con los CUT **como texto y con los ceros a la izquierda**.
- **Por qué es la fuente crítica:** de acá deriva `config/territorio_comunas.csv`, y de ahí
  la llave `comuna_cut` con la que se une **todo** lo demás. Si este maestro está mal, no
  falla nada: los joins quedan vacíos y las comunas afectadas aparecen como las más sanas
  del país. Ver [A-001](05-CALIDAD.md#a-001).
- **Granularidad:** comuna. **Ancla de reconciliación: 346 comunas en 16 regiones.**
- **Formato:** XLS. **URL:**
  `https://www.subdere.gov.cl/sites/default/files/documentos/CUT_2018_v04.xls`
  — *origen: busqueda_web, verificada con descarga y sha256*. Espejo en `geoportal.cl`.
- **Versión:** `CUT_2018_v04`, vigente desde el 2018-09-06 — es decir **posterior a la
  creación de Ñuble**, que es justamente lo que se necesita.
- **Trampas:**
  - **Control de vigencia obligatorio: Chillán debe ser `16101`, no `8401`.** Las capas que
    circulan como «DPA» suelen arrastrar la codificación anterior a 2007 —sin Los Ríos, sin
    Arica y Parinacota, sin Ñuble— y producen joins vacíos sin un solo error en pantalla.
    Es un solo dato y detecta ocho años de desfase.
  - El servidor responde **403 sin user-agent de navegador**.
- **Licencia:** `sin_declarar`, investigada el 2026-07-27. En `datos.gob.cl` SUBDERE publica
  CC-NC dos datasets de DPA, pero ambos son **cartografía** (shapefiles con geometrías).
  Esta planilla es otra cosa: códigos, nombres y provincias, sin una sola coordenada. Un
  listado de códigos administrativos oficiales es un hecho establecido por acto
  administrativo, no una obra —la Ley 17.336 excluye los hechos y los textos oficiales del
  Estado, y Chile no tiene derecho *sui generis* de bases de datos—.

### E0b. `ine_vitales_anuario` — Anuario de Estadísticas Vitales (ancla)

**Verificada el 2026-07-27. No es una fuente del pipeline**, y por eso no tenía ficha: de
acá salen **dos cifras** que se usan para comprobar el conteo propio, y el documento no se
redistribuye.

- **Uso:** ancla de reconciliación en año calendario para `deis_defunciones`. Cifras
  oficiales leídas del PDF (p. 38): **2023 = 122.218** y **2020 = 126.169** defunciones.
  Ambas coinciden **exacto** con el conteo del archivo de causas, no dentro de tolerancia.
- **Formato:** PDF. **URL:** anuario 2023 en `ine.gob.cl`, verificada con sha256.
- **Trampa de lectura:** la Tabla 3 (p. 45) dice 122.**217** porque desagrega por grupo de
  edad y excluye un registro sin edad; y 63.710 hombres + 58.495 mujeres = 122.205, con 12
  de sexo no asignado. **La cifra comparable es la de titular, 122.218**, y confundirlas
  hace fallar un ancla que en realidad cuadra.
- **Licencia:** declarada CC BY-NC 2.0, **en contradicción** con los términos generales
  CC BY-SA 4.0 del mismo organismo. Sin resolver. Mientras siga abierta se trata la
  condición más restrictiva como la vigente para este documento. No contamina la salida del
  proyecto porque `alimenta_gold: false` y solo se toman dos cifras: un dato aislado no es
  una obra. Si alguna vez se ingiere de verdad, hay que reabrir [ADR 0005](adr/0005-licencia-datos-sharealike.md).

### E1. `ine_proyecciones` — Proyecciones de población por comuna, sexo y edad

- **Uso:** denominador de toda tasa. **Dependencia crítica.**
- **Contiene:** población por comuna × sexo × edad simple, un valor por año. 56.052 filas
  (346 comunas × 2 sexos × 81 edades), 42 columnas. CSV latin-1, separador `,`.
- **Granularidad temporal:** 2002-2035. `Edad` llega a 80 como **grupo abierto** (80 y más).
- **Verificada** el 2026-07-27 con descarga real (9.768.366 bytes,
  sha256 `c2a88471…`). Cuadra exactamente con la DPA: 346 comunas y 16 regiones, cero
  diferencias en ambas direcciones. Total nacional 2020 = 19.458.310, igual a lo publicado.
- **Trampa 1 — formato ancho:** una columna `Poblacion <año>` por cada año. Hay que pasarlo
  a formato largo antes de usarlo como denominador.
- **Trampa 2 — cero a la izquierda:** `Comuna` viene como entero (`1101`, no `"01101"`),
  igual que `COD_COMUNA` en DEIS. Leer como string y `zfill(5)`. Sin eso se pierde el join
  de todas las comunas de las regiones 01-09.
- **Trampa 3 — cobertura:** empieza en **2002**. Defunciones va de 1990 a 2023 y en CIE-10
  desde 1997, así que **no hay denominador comunal para 1997-2001**. La ventana efectiva de
  tasas comunales es **2002-2023**.
- **Trampa 4 — re-base:** la base cambia con cada censo. El INE publicó el 2026-01-28 las
  estimaciones **base Censo 2024** (1992-2070); en la sesión de verificación solo se ubicó
  en vivo la presentación de resultados en PDF, no los tabulados comunales. Migrar de base
  recalcula las tasas históricas retroactivamente, así que es un cambio versionado y
  anunciado, nunca una actualización silenciosa: toda tasa publicada declara qué versión de
  proyección usó.
- **URL:** `ine.gob.cl/docs/default-source/proyecciones-de-poblacion/cuadros-estadisticos/base-2017/`
  — ver `config/sources.yml`. El listado de cuadros del sitio se arma por JavaScript: no se
  puede raspar del HTML.

### E2. `fonasa_inscritos` — Población inscrita validada en salud municipal

- **Uso:** denominador de cobertura de APS. Es lo que convierte «108.496 personas con
  depresión moderada» en «de los inscritos, tantos por mil están en control». Sin él, una
  comuna grande siempre parece tener más enfermedad que una chica.
- **Contiene:** población inscrita y validada por comuna y año. 345 comunas × 25 años
  (2001-2025) = 8.625 celdas. Total 2025: **14.807.159 inscritos**, 73,3 % de la población
  proyectada por el INE.
- **Verificada** el 2026-07-28 con descarga real (491.120 bytes,
  sha256 `e7dbdf8d…`). Las 345 comunas validan contra la DPA sin excepciones. Los totales
  anuales reproducen exactamente los calculados a mano antes de escribir el ingestor.
- **Dónde está, y dónde no.** El dato lo produce **FONASA** al validar la población para el
  per cápita, pero **FONASA no lo publica como archivo**: `datosabiertos.fonasa.cl` es un
  WordPress con un plugin de gráficos, sin API ni índice descargable (verificado el mismo
  día). Quien lo publica es **SINIM/SUBDERE**, declarando a FONASA como fuente. Antes de dar
  con SINIM se descartaron: el portal de FONASA, `adjuntos.fonasa.gob.cl` (vivo pero no
  enumerable), Wayback, `datos.gob.cl` (solo un Servicio de Salud regional, sin archivos) y
  el propio REM —su sección P7 cuenta **familias** inscritas, no personas—.
- **Trampa 1 — no es un `.xls`.** Se sirve con `Content-Type: application/x-msexcel` y
  extensión `.xls`, pero el cuerpo es **SpreadsheetML 2003**, o sea XML. `xlrd` no lo abre y
  `pandas.read_excel` tampoco. Además empieza con un salto de línea **antes** del prólogo
  XML: sin `lstrip()`, cualquier parser estricto falla.
- **Trampa 2 — el `ss:Type` miente.** El código de comuna viene declarado
  `ss:Type="Number"` con el cero a la izquierda intacto en el texto (`01402`). Se lee el
  texto del nodo, nunca el tipo declarado.
- **Trampa 3 — cuatro centinelas, cuatro significados.** `Costo Fijo` (comuna financiada
  por costo fijo, no por per cápita), `Sin Servicio` (la APS la administra el Servicio de
  Salud, no el municipio), `No Recepcionado` (**todo 2023**, en las 345 comunas) y
  `No Aplica`. Ninguno es cero ni faltante al azar.
- **Trampa 4 — el cero que no es cero.** Desde ~2019 SINIM escribe `0` donde antes escribía
  `Sin Servicio`. Son 30 comunas. Como denominador da división por cero; como numerador dice
  que nadie está inscrito en una comuna con CESFAM funcionando. Ver
  [A-013](05-CALIDAD.md#a-013).
- **Trampa 5 — el total está roto y sus componentes no.** Desde 2019, en un centenar de
  celdas por año el total contradice los tramos etarios que la propia fuente publica:
  Quirihue 2024 declara **31** inscritos en total y 499 + 4.045 + 1.589 = 6.133 repartidos
  por edad. Por eso la descarga pide **las cuatro variables juntas** (`464,466,470,471`):
  los tramos son disjuntos, su suma es una cota inferior del total, y esa desigualdad
  detecta el defecto sin umbral y sin nada externo. Entre 2001 y 2018 se cumple en 4.863 de
  4.863 celdas. Ver [A-015](05-CALIDAD.md#a-015).
- **Trampa 6 — no es toda la APS.** Es población inscrita en APS **municipal**. La APS
  dependiente de los Servicios de Salud queda fuera, así que no es el universo completo de
  la atención primaria pública.
- **Trampa 7 — el parámetro de períodos.** Los años van unidos por coma en **un** parámetro
  (`periodos[]=26,25,24,…`). Repetir `periodos[]` una vez por año devuelve **solo el primer
  año**, sin error y sin aviso: 345 filas perfectamente plausibles y 24 años perdidos.
- **Licencia:** `sin_declarar`. SINIM no publica términos de uso explícitos; pendiente de
  aclarar antes de redistribuir el dato derivado.

### E2b. `fonasa_padron_aps` — Padrón de inscritos en APS por establecimiento

**Verificada el 2026-07-29.** Estaba en el catálogo y en uso desde Fase 2 **sin ficha acá**,
que es un incumplimiento del flujo de `CLAUDE.md` §7: la ficha va primero. Se escribe ahora
con lo ya verificado.

- **Contiene:** inscritos en atención primaria por establecimiento × tramo (A/B/C/D) × grupo
  etario × sexo. 243.520 filas para septiembre de 2022, 1.889 establecimientos, 23 grupos
  etarios. Total nacional 13.585.016.
- **Granularidad:** establecimiento; agregable a comuna. Las 321 comunas presentes resuelven
  contra la DPA **sin una sola excepción por nombre**.
- **Cobertura temporal:** 2019, 2020, 2021 y 2022. **No llega más allá de 2022**, y por eso
  para 2023-2025 el único denominador disponible sigue siendo `fonasa_inscritos` (SINIM).
- **Formato:** ZIP con CSV, 41 MB descomprimido, encoding latin-1, campos entre comillas.
- **URL:** `https://www.fonasa.gob.cl/wp-content/uploads/2024/09/Inscritos-APS-2022.zip`
  — *origen: verificada_en_sesion*. Índice en `nuevo.fonasa.gob.cl/beneficiarios-y-prestaciones/`.
  **No** está en `datosabiertos.fonasa.cl`: ese portal es un WordPress con un plugin de
  gráficos y sin archivos. Concluir que el dato no existía por no encontrarlo ahí fue un
  error de sesión; vive en el sitio institucional.
- **Los nombres de archivo no siguen un patrón** (`Resultados-Inscritos-201908.zip`,
  `Poblacion-Inscrita-EAPS-a-Sep-2021.zip`): hay que tomarlos del índice, no construirlos.
- **Licencia:** `sin_declarar`.
- **Trampas:**
  - **El límite central, y es el mismo de `fonasa_inscritos`:** cubre la APS **municipal**
    (13.446.800) y «Otra Institución» (138.216), pero **no** los establecimientos
    dependientes del Servicio de Salud. Faltan 24 comunas completas y en otras el padrón es
    parcial —Quirihue aparece con 11 inscritos porque su único establecimiento municipal es
    una posta rural—. Esto es lo que explica [A-015](05-CALIDAD.md#a-015) y lo que reduce la
    cobertura calculable a 185 de 345 comunas.
  - `TRAMO` incluye una categoría `X` (787.606 personas) **cuyo significado no se ha
    verificado**. No usarla como tramo socioeconómico sin aclararlo.
- **Uso:** fue lo que permitió entender el desajuste de universos de A-015 y decidir en qué
  comunas la cobertura de I-03 significa algo. No alimenta `gold` como denominador directo.

### E3. `encavi` — Encuesta Nacional de Calidad de Vida y Salud 2023-2024

- **Contiene:** encuesta poblacional, aprox. 16.590 casos, muestreo probabilístico nacional,
  con módulos relevantes de bienestar y salud. — *origen: busqueda_web (existencia y tamaño)*.
- **Uso:** contexto y calibración de prevalencias; no reemplaza epidemiología psiquiátrica
  con entrevista diagnóstica.

### E4. `casen` — Encuesta de Caracterización Socioeconómica Nacional

- **Uso:** determinantes sociales para el análisis de desigualdad territorial. Ministerio de
  Desarrollo Social — *por_confirmar*.

### E5. `senda_estudios` — Estudios nacionales de drogas (población general y escolar)

- **Uso:** consumo de sustancias como comorbilidad y como demanda de la red. — *por_confirmar*.

### E6. `suseso_licencias` — Licencias médicas por trastornos mentales

- **Contiene:** estadísticas de licencias médicas curativas, con desglose por capítulo CIE.
  Organismo: Superintendencia de Seguridad Social. — *por_confirmar*.
- **Uso:** salud mental laboral; es una de las pocas series que captura población ocupada.
- **Trampa:** mide licencias tramitadas, no morbilidad; sensible a cambios de criterio de
  rechazo, lo que la Ley 21.331 justamente prohíbe discriminar.

---

## Fuentes descartadas (y por qué)

| Fuente | Motivo |
|---|---|
| Registros clínicos individuales (RayEn, fichas) | Datos personales sensibles; fuera de alcance por diseño |
| Datos de redes sociales / scraping de foros | Sesgo incorregible y problemas éticos evidentes |
| Encuestas de percepción privadas | Útiles como contexto, no reproducibles ni relicenciables |
| Registros de instituciones privadas de salud | Sin acceso público sistemático |

## Pendientes de investigación (Fase 1)

1. Confirmar todas las URLs y fijar `estado: verificada` con fecha.
2. Determinar si existe API o solo descarga de archivos en el portal DEIS.
3. Confirmar si `deis_urgencias` permite aislar lesión autoinfligida.
4. Conseguir el maestro histórico de establecimientos o construirlo.
5. Revisar términos de uso y licencia de cada portal antes de redistribuir datos derivados.
   **Resuelto para el INE el 2026-07-27; sigue abierto para el resto.** Los términos
   generales del INE son CC BY-SA 4.0: permiten uso comercial —así que el temor a una
   cláusula NC era infundado para esa fuente— pero exigen ShareAlike. Como
   `ine_proyecciones` es el denominador de toda tasa, el proyecto adoptó CC BY-SA 4.0 para
   su capa `gold` (ADR 0005). Ya no bloquea la publicación.
   Falta verificar la licencia de DEIS (`deis_defunciones`, `por_confirmar`) y de SUBDERE
   (`subdere_cut`, `por_confirmar`) —fuentes bajo CC BY o dominio público no dan problema,
   porque se pueden incorporar a una obra CC BY-SA; una con cláusula NC sí obligaría a
   reabrir— y queda por aclarar la contradicción entre el CC BY-NC 2.0 registrado para
   `ine_vitales_anuario` y el CC BY-SA 4.0 del mismo organismo.
