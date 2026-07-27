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

- **Contiene:** egresos de establecimientos públicos y privados, con diagnóstico principal
  CIE-10, días de estada, condición al alta, establecimiento, comuna de residencia.
- **Granularidad:** registro de egreso.
- **Latencia:** anual, con rezago.
- **URL raíz:** portal de datos abiertos DEIS — *origen: busqueda_web (raíz), por_confirmar
  (archivo específico)*.
- **Trampas:**
  - Un egreso ≠ una persona: reingresos cuentan varias veces. No usar como prevalencia.
  - Cambios en la red de establecimientos (aperturas, cierres, cambios de código DEIS)
    producen saltos que no son epidemiológicos.
  - El sector privado reporta con calidad heterogénea.
- **Uso:** hospitalizaciones psiquiátricas, estada media, egresos por lesión autoinfligida,
  proxy de disponibilidad de camas.

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

### B2. `maestro_establecimientos` — Establecimientos de salud (DEIS)

- **Contiene:** código DEIS, nombre, tipo, nivel de complejidad, dependencia, comuna,
  Servicio de Salud, estado de funcionamiento.
- **Uso:** llave de agregación de todo el REM y de egresos. **Es dependencia dura de B1.**
- **URL:** portal DEIS / `midas.minsal.cl` para algunos subconjuntos — *por_confirmar*.
- **Trampa:** el maestro es un corte actual, no histórico. Hay que construir y mantener una
  versión con vigencias, o las series se rompen hacia atrás.

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

- **Contiene:** presupuesto vigente y ejecución por partida, capítulo, programa y subtítulo.
- **Latencia:** mensual/trimestral.
- **URL:** DIPRES — *por_confirmar*.
- **Trampas mayúsculas:**
  - **El gasto en salud mental no es una línea presupuestaria única.** Está repartido entre
    programas de APS, transferencias a Servicios de Salud, PPI no desagregable, y aporte de
    otros organismos (SENDA). Cualquier cifra única es una estimación.
  - Por eso el indicador se publica como **rango con supuestos explícitos**, y la ficha
    enumera qué queda fuera.
  - Reasignaciones intra-anuales hacen que "presupuesto inicial" y "vigente" difieran mucho.
- **Uso:** gasto real per cápita por Servicio de Salud; evolución en pesos constantes.

### D3. `ine_ipc` — Índice de precios al consumidor

- **Uso:** deflactar. Todo monto se guarda nominal; el real se deriva. **URL:** INE —
  *por_confirmar*.

---

## E. Denominadores y contexto

### E1. `ine_proyecciones` — Proyecciones de población por comuna, sexo y edad

- **Uso:** denominador de toda tasa. **Dependencia crítica.**
- **Trampa:** la base cambia con cada censo. El Censo 2024 obliga a re-basar; las tasas
  históricas cambian retroactivamente. Por eso el denominador es un dataset versionado y toda
  tasa publicada declara qué versión de proyección usó.
- **URL:** INE — *por_confirmar*.

### E2. `fonasa_inscritos` — Población inscrita validada en APS

- **Uso:** denominador correcto para cobertura de APS (la población inscrita, no la
  proyección comunal). **URL:** FONASA/MINSAL — *por_confirmar*.

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
