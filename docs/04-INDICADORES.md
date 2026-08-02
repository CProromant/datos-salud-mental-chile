# 04 — Fichas de indicadores

Toda ficha tiene una sección **"qué NO significa"**. Es obligatoria porque el modo típico de
fallo de un observatorio no es publicar una cifra errónea, sino publicar una cifra correcta
que se lee mal.

Estado: `definido` = ficha lista, sin datos reales todavía. `activo` = calculándose en
producción con reconciliación pasando.

---

## I-01 · Tasa de mortalidad por suicidio

- **Estado:** activo (Fase 1) — calculado sobre datos reales 2002-2023, reconciliado
- **Numerador:** defunciones con causa básica en el agrupador `SUICIDIO` (X60–X84 + Y87.0),
  por comuna de **residencia**.
- **Denominador:** población proyectada INE de la misma comuna, año, sexo y grupo etario.
  Base 2017, comunas 2002-2035 (`ine_proyecciones`, verificada 2026-07-27).
- **Unidad:** por 100.000 habitantes.
- **Cobertura temporal: 2002-2023.** No es una elección: el denominador comunal del INE
  empieza en 2002 (A-008) y las defunciones están en CIE-9 hasta 1996 (A-002). Los años
  1997-2001 existen como **conteos**, nunca como tasas comunales; extrapolar población hacia
  atrás para completarlos está prohibido (`docs/02`, «gold no puede inventar población»).
- **Grupos etarios: quinquenales hasta `80+` abierto**, no hasta `85+`. Lo fija el
  denominador: el INE publica `80` como grupo abierto y partirlo exigiría inventar
  población. La población estándar OMS se colapsa en consecuencia, sumando los pesos de
  `80-84` (0,910) y `85+` (0,635) en `80+` (1,545). Numerador y denominador comparten la
  constante `TOPE_EDAD_PIPELINE` para que no puedan divergir: si divergieran,
  `tasa_estandarizada_directa` descartaría los grupos que no calzan y la tasa saldría
  calculada **sin adultos mayores**, sin que nada falle.
- **Variantes publicadas:** cruda; estandarizada por edad (estándar OMS colapsado a `80+`,
  método directo, con IC 95 %); suavizada por Bayes empírico. A nivel comunal la variante
  **principal es la suavizada**.
- **El límite inferior del IC se trunca en 0.** La aproximación normal sobre la varianza de
  Poisson produce límites negativos con conteos pequeños, y una tasa negativa no existe. Que
  el truncamiento haga falta es señal de que el conteo es demasiado bajo para el método: por
  eso la salida acompaña siempre el número de casos.
- **Población cero da tasa indefinida, no cero.** Hay celdas comuna × año sin habitantes
  (A-009). Un `0,0` se leería como «no hubo muertes» cuando significa «no hay a quién
  dividir».
- **Desagregaciones:** región, comuna, sexo, grupo etario, año.
- **Supresión:** k = 10.
- **Sensibilidad:** serie paralela que suma `INTENCION_INDETERMINADA` (Y10–Y34), publicada
  aparte y nunca sumada por defecto.
- **Qué NO significa:**
  - No es una medida de la salud mental de la comuna: el suicidio es un desenlace raro y
    multicausal, y una comuna con buena tasa puede tener un sistema pésimo.
  - No permite rankear territorios: en la mayoría de las comunas la diferencia entre una y
    otra es indistinguible del ruido, y por eso se publica el `peso_local_eb`.
  - No es comparable con series previas a **1997** sin advertencia: el corte CIE-9/CIE-10 es
    limpio en ese año (A-002). Además no se sabe cómo se codifica el suicidio en CIE-9 en
    este archivo —`E95x` aparece 0 veces—, así que antes de 1997 no hay serie, no hay una
    serie peor.
  - **No dice nada sobre los 85 y más por separado.** El tramo mayor se publica como `80+`
    porque el denominador no permite abrirlo. Una comparación con estudios que usan `85+`
    no es directa.
  - Los últimos dos años son preliminares y típicamente suben al consolidarse.

---

## I-02 · Años de vida potencial perdidos por suicidio

- **Estado:** activo (Fase 1) — 38,8 años perdidos por muerte en las celdas publicables
- **Cálculo:** Σ max(0, 80 − edad al fallecer), agregado por comuna y año.
- **Por qué existe:** la tasa cruda trata igual una muerte a los 17 y una a los 79. El AVPP
  hace visible que el suicidio concentra pérdida de vida joven, que es justamente el
  argumento que la discusión presupuestaria ignora.
- **Supresión: la misma k = 10 que el conteo, y no es negociable.** El AVPP es el dato más
  identificable de toda la salida: el aporte de cada muerte es 80 − edad, así que un AVPP de
  61 en una celda con una sola muerte dice que la persona tenía 19 años. Se suprime junto
  con el conteo, nunca después.
- **Las defunciones sin edad no aportan y se cuentan aparte.** Tratarlas como 0 afirmaría
  que murieron al nacer; como 80, que murieron justo en el límite. Ninguna de las dos es un
  dato, así que la celda declara `casos_sin_edad`.
- **Qué NO significa:** no es una medida de valor de la vida; el límite de 80 años es una
  convención elegida por comparabilidad, no una afirmación normativa. Tampoco es comparable
  con estudios que usen la esperanza de vida del año como límite en vez de uno fijo.

---

## I-03 · Cobertura del programa de salud mental en APS

- **Estado:** implementado (Fase 2). Se produce con `obsm rem cobertura`; ficha del dataset
  en [`DATASET-cobertura-salud-mental-aps.md`](DATASET-cobertura-salud-mental-aps.md).
- **Numerador:** personas bajo control en el programa de salud mental (REM), por comuna y
  corte semestral.
- **Denominador:** población inscrita validada en **APS municipal** (`fonasa_inscritos`), no
  la proyección comunal: la inscripción es el universo real del establecimiento.
- **Unidad:** personas en control **por cada mil inscritos**. No porcentaje: el denominador
  es un padrón comunal del orden de miles y un porcentaje comunicaría una décima que el dato
  no sostiene.
- **Cobertura efectiva:** **185 de 345 comunas.** Mediana nacional en diciembre de 2025:
  **51,7 por mil**; p10 = 40, p90 = 77.

### Por qué no se calcula en las otras 160 comunas

No es un problema de datos faltantes sino de **desajuste de universos**, y es la limitación
central de este indicador (ver [A-015](05-CALIDAD.md#a-015)):

- El **REM** cuenta actividad de toda la APS pública: municipal **y** dependiente del
  Servicio de Salud.
- **`fonasa_inscritos`** cuenta solo la municipal.

Donde la comuna se atiende en un hospital comunitario, el numerador incluye a esa población
y el denominador no. La cobertura resultante no es alta ni baja: no significa nada. Cada fila
declara su situación en la columna `denominador`:

| Valor | Qué pasa | Se publica |
|---|---|---|
| `completo` | toda la APS de la comuna es municipal y el padrón cubre a la mayoría de sus habitantes | sí |
| `parcial` | comuna mixta, o padrón que cubre menos de la mitad de la comuna | no, queda nulo |
| `ausente` | sin APS municipal, sin dato, o denominador refutado por el propio numerador | no, queda nulo |

Las filas no publicables van **sin valor**, no con una advertencia al lado: una advertencia
no viaja cuando alguien copia la celda.

- **Qué NO significa:**
  - **No mide necesidad atendida.** Mide oferta usada. Una comuna sin dispositivos aparece
    con cobertura baja y una comuna con equipo grande aparece alta, sin que eso diga nada
    sobre cuánta gente lo necesita.
  - **No es comparable entre comunas sin mirar `denominador`.** Dos comunas con el mismo
    valor pueden estar midiendo poblaciones distintas si una es mixta.
  - No distingue intensidad: una persona con un control al año y otra con doce cuentan igual.
    Por eso se publica junto con I-04.
  - Excluye al sector privado por completo.
  - **No hay dato para 2023.** SINIM publica el denominador de ese año como «No Recepcionado»
    en las 345 comunas.

---

## I-04 · Intensidad de tratamiento

- **Estado:** definido (Fase 2)
- **Cálculo:** controles de salud mental / personas bajo control, por comuna y semestre.
- **Uso:** distingue cobertura nominal de tratamiento real.
- **Qué NO significa:** más controles no es mejor atención; puede reflejar población más
  grave o menor capacidad de alta.

---

## I-05 · Ingresos por ideación e intento suicida

- **Estado:** definido (Fase 2)
- **Fuente:** secciones correspondientes del REM, por comuna y mes.
- **Qué NO significa:** un alza puede ser mejor detección, no más eventos. Es un indicador
  de **actividad del sistema**, no de incidencia poblacional. Se publica siempre junto con
  el número de establecimientos que reportaron.

---

## I-06 · Espera en psiquiatría adulto e infanto-adolescente

- **Estado:** definido (Fase 3). Fuentes verificadas el 2026-07-29; sin implementar.
- **Fuentes:** `glosa06` (PDF trimestral) para el desglose por especialidad;
  `listaespera_minsal` (JSON) para las medianas por Servicio de Salud.
- **Métricas:** casos en espera por especialidad, a nivel **nacional**; mediana y promedio
  de días por **Servicio de Salud**, con todas las especialidades agregadas.
- **La limitación central, y no es de este proyecto:** ninguna fuente pública cruza
  especialidad con territorio. El desglose por especialidad nunca trae días de espera, y las
  medianas por Servicio suman todas las especialidades. Verificado sobre dos informes.
  **No se puede decir cuánto espera un psiquiatra en una región concreta**, aunque la
  letra b) de la propia glosa obligue a publicarlo. El percentil 90 tampoco se publica en
  ninguna de las dos fuentes.
- **Qué NO significa:**
  - **Una mediana de días NO es la mediana de psiquiatría.** Es la de todas las
    especialidades del Servicio. Presentarla al lado de la cifra de psiquiatría invita a
    leerla como si lo fuera; por eso van en columnas separadas y con nombres distintos.
  - **La serie de medianas no puede empezar antes de 2022.** La fuente no las publica antes,
    y una tendencia que arranque en 2019 estaría comparando contra vacío.
  - "Casos" no es "personas": una persona puede tener varias interconsultas.
  - El reloj parte en la emisión de la interconsulta, no cuando la persona empezó a
    necesitar atención: subestima la espera vivida.
  - Una baja puede deberse a depuración administrativa de la lista, no a más atención. Por
    eso se publica junto a la tabla de quiebres.

---

## I-07 · Gasto real per cápita en salud mental por Servicio de Salud

- **Estado:** definido (Fase 4)
- **Cálculo:** ejecución atribuible a salud mental / población beneficiaria, deflactada a
  pesos de un año base.
- **Se publica como rango, no como punto.** El gasto en salud mental no es una línea
  presupuestaria única: queda repartido entre programas de APS, transferencias, prestaciones
  institucionales no desagregables y aportes de otros organismos.
- **Exclusiones declaradas en cada publicación:** PPI no desagregable, aporte SENDA, gasto
  municipal propio, gasto de bolsillo, gasto del sector privado.
- **Qué NO significa:** no es "lo que el Estado gasta en salud mental". Es lo que se puede
  atribuir con la desagregación disponible, que es menos.

---

## I-08 · Densidad de psiquiatras por 100.000

- **Estado:** definido (Fase 4)
- **Nivel máximo de publicación: regional.** El registro indica inscripción, no lugar ni
  jornada de ejercicio; una tasa comunal desde esa fuente sería precisión falsa.
- **Qué NO significa:** no mide horas disponibles, ni distribución público/privado, ni si el
  profesional atiende población beneficiaria.

---

## I-09 · Índice de brecha demanda-oferta

- **Estado:** definido (Fase 5)
- **Cálculo:** demanda esperada (prevalencia estimada × población por grupo etario) versus
  oferta observada, por comuna, con intervalo de incertidumbre.
- **Advertencia central:** la prevalencia estimada proviene de encuestas sin diagnóstico
  clínico y sin representatividad comunal. El índice es una herramienta de priorización
  relativa, no una medición de necesidad.
- **Qué NO significa:** no es una lista de comunas "que están mal". Es una hipótesis
  ordenada de dónde mirar primero.

---

## I-10 · Alerta de desviación de serie

- **Estado:** definido (Fase 5)
- **Método:** CUSUM sobre residuos de un modelo estacional simple, en series mensuales.
- **Salida:** issue interno para revisión humana. **Nunca** publicación automática ni
  notificación pública.
- **Qué NO significa:** una alerta es una anomalía estadística, casi siempre de registro
  antes que epidemiológica.
