# 06 — Ética, datos personales y publicación segura

Este documento es normativo. Sus reglas están implementadas en `quality.py` y `cie10.py`,
de modo que violarlas requiere modificar código con test, no solo olvidarse.

> Aviso: este texto describe criterios de diseño, no constituye asesoría legal. Antes de la
> primera publicación pública hay que someterlo a revisión jurídica. La revisión está
> registrada como tarea bloqueante en `PLAN.md`, Fase 5.

---

## 1. Datos personales

El observatorio trabaja **solo con datos agregados o desidentificados de acceso público**.
No solicita, no almacena y no procesa registros clínicos identificables.

Marco relevante en Chile:

- **Ley 21.719** de protección de datos personales, que moderniza el régimen anterior, crea
  una agencia con potestad sancionatoria y clasifica los **datos de salud como datos
  sensibles**, con exigencias reforzadas de licitud, finalidad y seguridad. Su régimen
  sancionatorio hace que un proyecto de datos de salud mal diseñado sea un riesgo legal real,
  no teórico.
- **Ley 17.374** y el **secreto estadístico**: la información recogida con fines estadísticos
  no puede difundirse de forma que permita identificar a una persona.
- **Ley 21.331**, que reconoce derechos de las personas en la atención de salud mental,
  incluida la confidencialidad de su ficha clínica.

Consecuencias operativas, que no se negocian por conveniencia analítica:

1. Ninguna fuente con registros identificables entra al pipeline. Si una fuente pública
   resulta contener identificadores directos o cuasi-identificadores peligrosos, **se
   reporta al organismo y no se usa**.
2. El registro individual desidentificado (por ejemplo, una base de defunciones) se procesa
   solo para agregarlo. No se publica nunca a nivel de registro, ni siquiera "anonimizado":
   fecha exacta + comuna + sexo + edad exacta puede identificar a una persona en una comuna
   de dos mil habitantes.
3. Todo dato crudo permanece fuera del control de versiones y fuera del repositorio público.

---

## 2. Riesgo de reidentificación y supresión

**Umbral k.** No se publica ninguna celda con conteo entre 1 y k−1.

| Tipo de dato | k | Justificación |
|---|---|---|
| Mortalidad (incluye suicidio) a nivel comunal | 10 | Evento raro, territorio chico, alta sensibilidad social |
| Actividad asistencial (controles, ingresos) | 5 | Menor sensibilidad, mayor volumen |
| Cualquier cruce con más de tres dimensiones | 10 | El riesgo crece con la desagregación, no con el tema |

**El cero sí se publica.** "Cero muertes" no identifica a nadie y sí informa. Suprimir ceros
sería confundir privacidad con opacidad.

**Supresión complementaria.** Si en un grupo queda una sola celda suprimida y el total del
grupo es conocido, la celda se reconstruye por resta. En ese caso se suprime además la menor
de las celdas restantes. Implementado en `quality.suprimir_celdas_pequenas`.

**Supresión de derivados.** Si se suprime el conteo, se suprime también toda cifra desde la
cual el conteo sea recuperable: tasa cruda (conteo = tasa × población / 100.000),
porcentajes sobre un total conocido y AVPP. La tasa suavizada EB sí se publica, porque no
permite recuperar el conteo original.

---

## 3. Publicación de datos de suicidio

Esta es la parte donde una decisión de diseño puede causar daño directo, y por eso es la más
restrictiva del proyecto. Se sigue el consenso internacional sobre comunicación responsable
del suicidio (OMS y guías de prensa), adaptado a un producto de datos.

**Prohibido, sin excepciones:**

1. **Desagregar por método.** Ni subcódigos X60–X84 individuales, ni columna "mecanismo", ni
   cruce que permita reconstruirlos. La evidencia sobre efecto de imitación asociado a la
   difusión detallada de métodos es la razón. El agregador `SUICIDIO` es la única salida.
   Verificado por `cie10.es_publicable` y `quality.verificar_politica_publicacion`.
2. **Rankings de comunas por tasa de suicidio.** Con eventos raros, un ranking ordena ruido y
   estigmatiza territorios. Se publican tasas suavizadas con su incertidumbre, y la interfaz
   presenta rangos, no posiciones.
3. **Titulares de alerta automáticos.** Las alertas de desviación abren un issue interno
   para revisión humana. Nunca generan una publicación automática.
4. **Datos sobre casos individuales o eventos identificables**, aunque hayan sido noticia.

**Obligatorio en toda salida pública que incluya suicidio:**

- Nota metodológica: definición CIE-10 usada, exclusión de Y10–Y34 de la serie principal,
  años preliminares marcados, población denominadora y su versión.
- Advertencia de interpretación cuando el suavizado domina al dato local.
- Enlace a recursos de ayuda vigentes en Chile, verificados en la fecha de publicación.
  La verificación es parte del checklist de release: un número de ayuda desactualizado en un
  producto sobre suicidio es un daño concreto, no un detalle de forma.

**Revisión humana.** Ninguna publicación que incluya suicidio sale sin revisión de una
persona con competencia en salud mental. Está en `docs/09-GOBERNANZA.md` como requisito, no
como recomendación.

---

## 4. Uso previsto y usos que se rechazan

**Previsto:** diagnóstico territorial, evaluación de política pública, priorización de
recursos, investigación, fiscalización, periodismo especializado.

**Rechazado explícitamente, y por diseño imposible con estos datos:**

- Predicción o puntuación de riesgo individual. Es la aplicación más tentadora de una base
  así y la más dañina: agrega vigilancia sobre personas que ya enfrentan estigma, con una
  exactitud que no justifica la intervención que gatillaría.
- Evaluación de desempeño de profesionales o equipos concretos. La unidad de análisis es el
  territorio y el sistema.
- Focalización comercial (seguros, marketing farmacéutico, scoring). La licencia de los
  datos derivados lo prohíbe expresamente.

---

## 5. Sesgos que el dato arrastra y hay que declarar

No declararlos convierte una limitación en un error de lectura.

| Sesgo | Efecto | Cómo se declara |
|---|---|---|
| Subregistro de suicidio por codificación como intención indeterminada | Subestima la tasa, de forma desigual entre territorios | Serie de sensibilidad Y10–Y34 publicada aparte |
| Datos de la red pública solamente | Invisibiliza la atención privada, sesgo por nivel socioeconómico | Nota en cada indicador de actividad |
| "Bajo control" mide oferta usada, no necesidad | Una comuna sin oferta parece una comuna sin problema | Indicador de brecha nunca usa cobertura como proxy de necesidad |
| Lista de espera cuenta desde la interconsulta | Subestima la espera real vivida | Nota en el indicador de espera |
| Registro de prestadores refleja inscripción, no ejercicio | Sobrestima oferta local en comunas con domicilios administrativos | Prohibida la desagregación comunal de esa fuente |
| Cambios de criterio administrativo | Producen saltos que parecen cambios reales | Tabla de quiebres de serie que acompaña a los datos |

---

## 6. Checklist previo a publicar (obligatorio)

- [ ] ¿Toda celda cumple el umbral k, incluida la supresión complementaria?
- [ ] ¿Se suprimieron los derivados desde los que se reconstruye un conteo suprimido?
- [ ] ¿La tabla está libre de desagregación por método?
- [ ] ¿Los años preliminares están marcados?
- [ ] ¿Cada cifra arrastra su procedencia y la versión del denominador?
- [ ] ¿Hay nota metodológica y de limitaciones?
- [ ] Si incluye suicidio: ¿revisión de una persona con competencia clínica? ¿recursos de
      ayuda verificados hoy?
- [ ] ¿Se evitó todo formato de ranking territorial?
