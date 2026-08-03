# 10 — Fuentes candidatas

Qué falta incorporar y en qué orden. **Ordenado por lo que cada fuente permite responder**,
no por facilidad ni por organismo.

> **Estado de verificación.** `alcanzable` significa que el sitio respondió el 2026-08-02;
> **no** que se haya abierto el archivo. Ninguna entrada de este documento puede pasar a
> `config/sources.yml` como `verificada` sin descarga real (CLAUDE.md §2.1).

---

## Tier 1 — Cierran preguntas que el proyecto ya hace a medias

Las tres están **ya en el catálogo como `no_verificada`** y son del mismo portal DEIS que
ya sabemos descargar. Es el trabajo de mejor relación valor/esfuerzo que queda.

### 1. `deis_egresos` — Egresos hospitalarios ✅ **incorporada el 2026-08-02**

**Qué agregó:** la hospitalización psiquiátrica, que era un agujero. El proyecto sabía
cuánta gente está en control ambulatorio (REM) y cuánta muere (DEIS), pero nada de lo que
pasa en medio. Ahora hay 2001–2024, ~1,6 millones de egresos por año: **37.773
hospitalizaciones por trastorno mental** y **7.683 egresos por lesión autoinfligida** en
2023, que se ubican justo entre las ~9.900 personas en control por intento suicida en APS y
las ~2.000 muertes por suicidio al año.

**Se cumplió lo previsto:** mismo portal y misma trampa de `DIAG2` que `deis_defunciones`.

**No se cumplió lo previsto:** la fuente **no trae establecimiento ni edad exacta** —viene
desidentificada—, así que el uso «proxy de disponibilidad de camas» que prometía la ficha
A2 quedó descartado. Y trajo cuatro trampas que no estaban en el pronóstico:
[A-021](05-CALIDAD.md#a-021) (acentos destruidos en origen en 2024),
[A-022](05-CALIDAD.md#a-022) (supresión propia de DEIS que alcanza al 8 % de las filas) y
[A-023](05-CALIDAD.md#a-023) (2021 publicado con otro codebook completo).

**Trampa que sí estaba prevista y sigue vigente:** un egreso no es una persona. Los
reingresos cuentan varias veces y no hay identificador de paciente, así que no sirve como
prevalencia.

### 2. `suseso_licencias` — Licencias médicas por trastornos mentales

**Qué agrega:** la única medida del **costo económico** de la salud mental en Chile que
existe como dato administrativo. Los trastornos mentales son de las principales causas de
licencia, y eso no aparece en ninguna serie del proyecto.

**Por qué importa políticamente:** [I-07](04-INDICADORES.md#i-07) mostró que el presupuesto
no permite decir cuánto se gasta en salud mental. Las licencias miden el costo **por el otro
lado** —días de trabajo perdidos— y ese sí está desagregado por diagnóstico.

**Estado:** `suseso.cl` alcanzable. Falta ubicar el archivo y su granularidad.

### 3. `deis_urgencias` — Atenciones de urgencia

**Qué agrega:** frecuencia semanal, la más alta del proyecto. Y potencialmente el **intento
suicida atendido en urgencia**, que es el eslabón que falta entre el intento registrado en
APS y la muerte.

**Bloqueante declarado en el catálogo:** confirmar si la agrupación de causas permite aislar
lesión autoinfligida. **Si no lo permite, esta fuente no sirve para el proyecto** y conviene
saberlo antes de construir.

---

## Tier 2 — Dimensiones que el proyecto no tiene

### 4. SENDA — Estudios nacionales de drogas

**Qué agrega:** consumo de sustancias en población general y escolar, con serie larga y
representatividad regional. Es la comorbilidad más frecuente de los trastornos mentales y
el proyecto no la toca.

**Estado:** `senda.gob.cl/observatorio/estudios/` alcanzable. Ya está en el catálogo como
`no_verificada`.

**Advertencia de diseño:** es una **encuesta**, no un registro administrativo. Su unidad de
error es distinta —muestreo, no cobertura— y mezclarla con series del REM sin declararlo
produce comparaciones inválidas.

### 5. CASEN — Determinantes sociales

**Qué agrega:** pobreza, empleo, educación y aislamiento por comuna, que son los
determinantes que `docs/00` lista como uno de los once problemas. Permite preguntar si la
brecha de cobertura sigue a la brecha socioeconómica.

**Estado:** el observatorio del Ministerio de Desarrollo Social responde.

**Advertencia:** representatividad comunal limitada. CASEN no es representativa en todas las
comunas, y usarla como si lo fuera es un error clásico.

### 6. Superintendencia de Salud — Registro de prestadores

**Qué agrega:** [I-08](04-INDICADORES.md#i-08), densidad de psiquiatras y psicólogos. Es la
oferta de recurso humano, que hoy es invisible.

**Estado:** `superdesalud.gob.cl/datos-abiertos/` da **404**. Hay que buscar la ruta actual.

**Límite ya declarado en el catálogo:** el registro dice dónde está **inscrito** el
prestador, no dónde atiende ni cuántas horas. Por eso `nivel_maximo_publicable: region` —
la desagregación comunal está prohibida para esta fuente.

### 7. MINEDUC — Deserción y convivencia escolar

**Qué agrega:** la salud mental adolescente por su desenlace educativo. Deserción y
problemas de convivencia son a la vez determinante y consecuencia, y el proyecto hoy solo ve
adolescentes cuando llegan al sistema de salud.

**Estado:** `datosabiertos.mineduc.cl` responde, portal armado por JavaScript. Habrá que
buscar la API detrás, como en SINIM y en el visualizador de listas de espera.

---

## Tier 3 — Poblaciones que el sistema general no ve

Estas cuatro comparten algo: describen personas con **riesgo muy superior al de la población
general** y que no aparecen en las series actuales.

### 8. Mejor Niñez — Niños bajo protección del Estado

La población con mayor carga de salud mental del país, y la que `docs/00` menciona
explícitamente al nombrar a la Defensoría de la Niñez como usuaria esperada.

**Estado:** `mejorninez.cl` responde. Falta ubicar datos abiertos.

**Advertencia ética fuerte:** población de niños, niñas y adolescentes bajo protección. La
supresión k=10 de `docs/06` aplica sin discusión, y cualquier cruce necesita revisión antes
de construirse, no después.

### 9. Poder Judicial — Salud mental y justicia

**Qué agrega:** internaciones involuntarias y medidas de protección. La Ley 21.331 reconoce
derechos en la atención de salud mental y nadie publica cuántas internaciones no voluntarias
ocurren.

**Estado:** `numeros.pjud.cl` responde, portal JS.

**Advertencia:** es la fuente más sensible de toda la lista. Antes de tocarla conviene
decidir en `docs/06` qué se puede publicar.

### 10. SENADIS — Discapacidad de origen psíquico

Registro Nacional de la Discapacidad. Permite dimensionar la discapacidad psíquica y mental,
que no aparece en ninguna serie actual.

### 11. Gendarmería — Salud mental en privación de libertad

Prevalencia muy superior a la población general y ausencia casi total de datos públicos.
**Probablemente no exista como dato abierto**; vale una solicitud por Transparencia antes
que un ingestor.

---

## Tier 4 — Contexto y utilidades

### 12. `ine_ipc` — Deflactor

Ya en el catálogo. **Necesario para [I-07](04-INDICADORES.md#i-07)**: sin él no hay pesos
reales, y `CLAUDE.md` §5 prohíbe guardar solo el valor real. Es la dependencia más chica y
concreta que queda.

### 13. INE — ENUSC, victimización

Percepción de inseguridad y victimización por comuna. Determinante de salud mental con serie
larga y buena metodología.

---

## Qué NO incorporar, y por qué

**Datos de hospitales individuales.** El portal nacional publica egresos y urgencias de
establecimientos sueltos —el Hospital Gustavo Fricke tiene diez años de series—. Son de
buena calidad y **no sirven**: dan una cobertura arbitraria que se lee como nacional. El
proyecto usa el registro consolidado de DEIS o nada.

**Registros de prestadores a nivel comunal.** Ya está prohibido en el catálogo. Un
psiquiatra inscrito en Providencia que atiende en tres regiones infla Providencia y vacía
las otras.

**Cualquier fuente con datos identificables.** `docs/06` §1: si una fuente pública resulta
traer identificadores, se reporta al organismo y no se usa.

---

## Orden recomendado

1. ~~**`deis_egresos`**~~ — hecha el 2026-08-02. Cerró el hueco entre control y muerte.
2. **`ine_ipc`** — desbloquea I-07, es chico y concreto.
3. **`suseso_licencias`** — la única medida del costo económico que existe.
4. **`deis_urgencias`** — pero **primero verificar si aísla lesión autoinfligida**; si no, se
   descarta y se ahorra la fase.
5. El resto, según lo que pida quien use los datos.

El punto 5 no es pereza. Las Fases 3 y 4 corrigieron su alcance **después** de bajar la
fuente, y en ambos casos el plan pedía algo que los datos no permitían. Construir contra un
pedido concreto de un usuario real es más barato que construir contra una hipótesis.
