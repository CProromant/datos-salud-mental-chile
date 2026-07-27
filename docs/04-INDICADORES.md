# 04 — Fichas de indicadores

Toda ficha tiene una sección **"qué NO significa"**. Es obligatoria porque el modo típico de
fallo de un observatorio no es publicar una cifra errónea, sino publicar una cifra correcta
que se lee mal.

Estado: `definido` = ficha lista, sin datos reales todavía. `activo` = calculándose en
producción con reconciliación pasando.

---

## I-01 · Tasa de mortalidad por suicidio

- **Estado:** definido (Fase 1)
- **Numerador:** defunciones con causa básica en el agrupador `SUICIDIO` (X60–X84 + Y87.0),
  por comuna de **residencia**.
- **Denominador:** población proyectada INE de la misma comuna, año, sexo y grupo etario.
- **Unidad:** por 100.000 habitantes.
- **Variantes publicadas:** cruda; estandarizada por edad (estándar OMS); suavizada por
  Bayes empírico. A nivel comunal la variante **principal es la suavizada**.
- **Desagregaciones:** región, comuna, sexo, grupo etario, año.
- **Supresión:** k = 10.
- **Sensibilidad:** serie paralela que suma `INTENCION_INDETERMINADA` (Y10–Y34), publicada
  aparte y nunca sumada por defecto.
- **Qué NO significa:**
  - No es una medida de la salud mental de la comuna: el suicidio es un desenlace raro y
    multicausal, y una comuna con buena tasa puede tener un sistema pésimo.
  - No permite rankear territorios: en la mayoría de las comunas la diferencia entre una y
    otra es indistinguible del ruido, y por eso se publica el `peso_local_eb`.
  - No es comparable con series previas a 1998 sin advertencia (CIE-9).
  - Los últimos dos años son preliminares y típicamente suben al consolidarse.

---

## I-02 · Años de vida potencial perdidos por suicidio

- **Estado:** definido (Fase 1)
- **Cálculo:** Σ max(0, 80 − edad al fallecer), agregado por comuna y año.
- **Por qué existe:** la tasa cruda trata igual una muerte a los 17 y una a los 79. El AVPP
  hace visible que el suicidio concentra pérdida de vida joven, que es justamente el
  argumento que la discusión presupuestaria ignora.
- **Qué NO significa:** no es una medida de valor de la vida; el límite de 80 años es una
  convención elegida por comparabilidad, no una afirmación normativa.

---

## I-03 · Cobertura del programa de salud mental en APS

- **Estado:** definido (Fase 2)
- **Numerador:** personas bajo control en el programa de salud mental (REM), por comuna.
- **Denominador:** población inscrita validada en APS (no la proyección comunal: la
  inscripción es el universo real del establecimiento).
- **Unidad:** porcentaje.
- **Qué NO significa:**
  - **No mide necesidad atendida.** Mide oferta usada. Una comuna sin dispositivos aparece
    con cobertura baja y una comuna con equipo grande aparece alta, sin que eso diga nada
    sobre cuánta gente lo necesita.
  - No distingue intensidad: una persona con un control al año y otra con doce cuentan igual.
    Por eso se publica junto con I-04.
  - Excluye al sector privado por completo.

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

- **Estado:** definido (Fase 3)
- **Fuente:** Glosa 06, por Servicio de Salud y trimestre.
- **Métricas:** casos en espera; mediana y percentil 90 de días.
- **Qué NO significa:**
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
