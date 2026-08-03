# 10 — Fuentes candidatas

Qué falta incorporar y en qué orden. **Ordenado por lo que cada fuente permite responder**,
no por facilidad ni por organismo.

> **Estado de verificación.** `alcanzable` significa que el sitio respondió con `200` en la
> fecha indicada; **no** que se haya abierto el archivo. Ninguna entrada de este documento
> puede pasar a `config/sources.yml` como `verificada` sin descarga real (CLAUDE.md §2.1).

---

## El portal de datos abiertos del Estado no sirve para esto {#datos-gob-cl}

Barrido sistemático de `datos.gob.cl` el **2026-08-03**, vía su API CKAN, con 30 términos
de búsqueda de salud mental y sus determinantes. Se hizo para descartar la hipótesis
razonable de que el catálogo nacional fuera el atajo. **No lo es**, y conviene dejarlo
escrito para que nadie repita el barrido.

**Lo que el portal no tiene.** Búsquedas directas, con tilde y sin ella:

| Búsqueda | Resultados |
|---|---|
| `"salud mental"` (frase exacta) | **0** |
| `psiquiatría` | **0** |
| `depresión` | **0** |
| `ansiedad` | **0** |
| `esquizofrenia` | **0** |
| `demencia` | **0** |
| `autismo` | **0** |
| `psicología` | **0** |
| `mental` | 1 — un subsidio de discapacidad |
| `suicidio` | 2 — un registro local de Santiago |
| `salud` | 345 — casi todo finanzas municipales |

**Ni un solo conjunto de datos del Estado chileno responde a «salud mental» en su propio
catálogo de datos abiertos.** Es el mismo vacío que `docs/00` describe como problema, ahora
medido sobre el catálogo oficial.

**Lo que el portal sí tiene, y por qué tampoco sirve.** Los 30 términos devolvieron 219
conjuntos distintos. Al mirarlos:

- **118 de 219 (54 %) no se tocan desde 2015.** Es un volcado único que nunca se actualizó.
- **137 de 219 (63 %) están bajo Creative Commons No Comercial**, incompatible con la
  CC BY-SA que [ADR 0005](adr/0005-licencia-datos-sharealike.md) obliga para `gold`. Aunque
  el dato sirviera, no podría alimentar una serie publicable.
- **51 provienen de diez establecimientos sueltos** —el Hospital Gustavo Fricke solo aporta
  21— que es exactamente lo que la sección «Qué NO incorporar» de este documento ya
  descartaba: dan una cobertura arbitraria que se lee como nacional.

**Conclusión operativa:** las fuentes útiles viven en los portales de cada organismo, no en
el catálogo central. Todo lo que sigue apunta ahí.

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

**Estado:** alcanzable el 2026-08-03, pero **el dominio es `suseso.gob.cl`, no `suseso.cl`**;
la ruta de estadísticas que figuraba da 404 y hay que ubicar la vigente. Falta el archivo y
su granularidad.

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

**Estado:** alcanzable el 2026-08-03, pero **la ruta cambió**: ahora es
`senda.gob.cl/informacion-y-conocimiento/observatorio-chileno-drogas/estudios/`. Ya está
en el catálogo como `no_verificada`.

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

**Estado:** **404** confirmado de nuevo el 2026-08-03. Dos rutas probadas, ninguna viva.
Es candidata a solicitud por Transparencia antes que a ingestor.

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

### 8. Servicio de Protección Especializada a la Niñez — niños bajo protección

La población con mayor carga de salud mental del país, y la que `docs/00` menciona
explícitamente al nombrar a la Defensoría de la Niñez como usuaria esperada.

**Estado:** el organismo **cambió de nombre**: `mejorninez.cl` redirige a
`servicioproteccion.gob.cl`, que responde (verificado 2026-08-03). Falta ubicar datos
abiertos. Cualquier referencia a «Mejor Niñez» en documentos externos apunta acá.

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
larga y buena metodología. Alcanzable el 2026-08-03.

---

## Tier 5 — Aparecidas en el barrido del 2026-08-03

Cuatro organismos que no estaban en este documento y que responden. Ninguna se ha abierto:
son **candidatas**, no fuentes.

### 14. Servicio Médico Legal — autopsias y causa de muerte violenta

**Qué agregaría:** el SML es quien determina la causa en las muertes violentas, incluidas
las que DEIS después codifica como suicidio. Sería la única vía para estimar cuánto de la
**intención indeterminada** (Y10–Y34) es realmente conducta suicida — el análisis de
sensibilidad que `docs/01` ficha A1 declara pendiente.

**Advertencia fuerte:** es la fuente más sensible imaginable en este proyecto y toca
directamente lo que `CLAUDE.md` §2.4 prohíbe publicar. Antes de pedir nada hay que decidir
en `docs/06` qué se podría publicar, si algo. `sml.gob.cl` responde; no se buscó el dato.

### 15. Registro Social de Hogares — determinantes a nivel de hogar

**Qué agregaría:** el RSH cubre a la mayoría de los hogares del país con datos
socioeconómicos actualizados, y a diferencia de CASEN **no es una muestra**. Sería un
denominador de vulnerabilidad mucho mejor que el de una encuesta.

**Advertencia:** casi con certeza no está disponible a nivel útil sin convenio. Su valor es
más probable como argumento para el dueño institucional que como descarga.

### 16. Instituto de Salud Pública — consumo de psicofármacos

**Qué agregaría:** el ISP registra el consumo de medicamentos controlados. Sería un proxy de
tratamiento farmacológico **independiente del REM**, y por tanto una forma de contrastar si
la actividad reportada por la red calza con lo que efectivamente se dispensa.

**Estado:** `ispch.cl` responde. No se ubicó la serie.

### 17. Chile Crece Contigo — desarrollo infantil temprano

**Qué agregaría:** la salud mental infantil antes de que llegue a ser diagnóstico. Es el
único punto del sistema con cobertura casi universal en primera infancia.

**Estado:** `crececontigo.gob.cl` redirige (302). No se ubicó el dato.

---

## Alcance verificado de todos los portales {#alcance}

Comprobado el **2026-08-03** con `curl` y user-agent de navegador, siguiendo redirecciones.
`200` significa que el sitio responde: **no** que el archivo exista ni que se haya abierto.

| Fuente | Portal | Estado |
|---|---|---|
| SENDA, estudios | `senda.gob.cl/informacion-y-conocimiento/observatorio-chileno-drogas/estudios/` | **200** — *la ruta cambió*, ver abajo |
| CASEN | `observatorio.ministeriodesarrollosocial.gob.cl/encuesta-casen` | **200** |
| MINEDUC datos abiertos | `datosabiertos.mineduc.cl` | **200** |
| Servicio de Protección (ex Mejor Niñez) | `servicioproteccion.gob.cl` | **200** — *cambió de nombre*, ver abajo |
| Poder Judicial | `numeros.pjud.cl` | **200** |
| SENADIS, Registro Nacional de Discapacidad | `senadis.gob.cl/pag/355/1723/...` | **200** |
| Servicio Médico Legal | `sml.gob.cl` | **200** |
| Instituto de Salud Pública | `ispch.cl` | **200** |
| SUSESO | `suseso.gob.cl/601/w3-channel.html` | **200** — el dominio es `.gob.cl`, no `.cl` |
| INE, seguridad y justicia (ENUSC) | `ine.gob.cl/estadisticas-por-tema/sociedad-y-condiciones-de-vida` | **200** |
| Registro Social de Hogares | `registrosocial.gob.cl` | **200** |
| DEIS | `deis.minsal.cl` | **200** |
| Chile Crece Contigo | `crececontigo.gob.cl` | 302 |
| **Superintendencia de Salud**, datos abiertos | `superdesalud.gob.cl/documentos/571/...` | **404** |
| **Gendarmería**, estadísticas | `gendarmeria.gob.cl/estadisticas.html` | **404** |
| **Fiscalía**, estadísticas | `fiscaliadechile.cl/Fiscalia/estadisticas/` | **404** |
| **CEAD**, estadísticas delictuales | `cead.spd.gov.cl` | **no resuelve** |
| `repositoriodeis.minsal.cl` (raíz) | — | 403 en la raíz; **los archivos sí bajan** con user-agent |

### Tres correcciones que salieron de verificar

1. **«Mejor Niñez» ya no se llama así.** `mejorninez.cl` redirige a
   `servicioproteccion.gob.cl`: es el **Servicio Nacional de Protección Especializada a la
   Niñez y Adolescencia**. La entrada 8 de este documento usaba el nombre antiguo.
2. **SENDA movió su observatorio de ruta.** La URL que figuraba —`/observatorio/estudios/`—
   redirige a `/informacion-y-conocimiento/observatorio-chileno-drogas/estudios/`. Sigue
   viva, pero un ingestor con la ruta vieja dependería de que la redirección se mantenga.
3. **Cuatro portales de estadísticas están caídos o movidos**: Superintendencia de Salud,
   Gendarmería, Fiscalía y CEAD. Para los cuatro, la vía realista es una solicitud por
   Transparencia antes que un ingestor — y para Gendarmería este documento ya lo decía.

**Lo que esta tabla no dice.** Que un portal responda `200` no significa que publique el
dato que se busca, ni en formato utilizable. Las Fases 3 y 4 corrigieron su alcance
**después** de bajar la fuente, y el IPC del INE fue el caso extremo: seis vías alcanzables
y ninguna con un archivo (`docs/01`, ficha D3). El siguiente paso de cualquiera de estas
entradas es abrir el archivo, no volver a comprobar que el sitio existe.

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
