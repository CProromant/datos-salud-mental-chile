# 05 — Calidad, reconciliación y anomalías

## Niveles de verificación

**1. Contrato de esquema.** Automático en cada ingesta. Columna requerida ausente →
`SchemaDriftError`. Cambio de esquema es evento humano, no se auto-repara.

**2. Validaciones estructurales.** En cada corrida:

- llave primaria única (`validar_sin_duplicados`);
- cobertura territorial sobre el total esperado (`validar_cobertura_territorial`);
- tasa de comunas no resueltas por nombre; un alza entre cortes indica cambio de fuente;
- filas de total detectadas y descartadas, con conteo reportado;
- proporción de edades convertidas desde meses/días.

**3. Anclas de reconciliación.** Un total calculado se compara contra una cifra oficial
publicada. Sin esto el pipeline puede estar perfectamente ordenado y perfectamente
equivocado.

| Fuente | Ancla | Tolerancia | Estado |
|---|---|---|---|
| `deis_defunciones` | total nacional de defunciones del año, publicado por DEIS | 0,5% | por implementar (Fase 1) |
| `deis_defunciones` | total nacional de suicidios del año, informes oficiales | 1% | por implementar (Fase 1) |
| `rem_salud_mental` | población bajo control nacional del corte semestral | 1% | por implementar (Fase 2) |
| `glosa06` | totales por Servicio de Salud impresos en el propio PDF | 0,1% | por implementar (Fase 3) |
| `dipres_ejecucion` | ejecución total de la partida 16 | 0,1% | por implementar (Fase 4) |

Regla: **si no cuadra, no se publica.** Se abre issue con la diferencia y su hipótesis.

**4. Verificación manual por muestreo.** Tres registros al azar por corte, contrastados a
mano contra la publicación original. Se documenta quién y cuándo.

## Anclas de reconciliación {#anclas}

Las anclas viven en `config/anclas.yml`, no en el código. Cada una declara de dónde salió,
en qué página y cuándo se leyó; un ancla sin `referencia` ni `fecha_verificacion` **no se
carga**, porque un número sin origen comprobable no valida nada: solo traslada la fe de un
lugar a otro.

| ancla | qué valida | valor | tolerancia | origen |
|---|---|---|---|---|
| `defunciones_totales_2023` | ingesta completa del numerador | 122.218 | 0,5 % | Anuario Vitales 2023 (INE), p.38 |
| `defunciones_totales_2020` | ídem, año de 53 semanas | 126.169 | 0,5 % | ídem |
| `causas_externas_hombres_2023` | derivación de `causa_cie10` | 6.180 | 1 % | Anuario Vitales 2023, Gráfico 28 p.49 |
| `poblacion_nacional_2020` | denominador | 19.458.310 | 0,01 % | INE, proyecciones base 2017 |
| `poblacion_nacional_2023` | denominador | 19.960.889 | 0,01 % | ídem |

Cuatro reconcilian **exacto** (0,000000 %) y la de causas externas queda en 0,39 %.

**El ancla de causas externas es la que vigila A-004.** Es la única que toca la derivación
de `causa_cie10`. Si el ingestor volviera a leer solo `DIAG1`, las causas externas caerían a
casi cero —la naturaleza de la lesión vive en el capítulo XIX (`S`,`T`), no en el XX— y la
publicación se detendría. Sin ella, un suicidio mal derivado solo se nota si alguien mira
específicamente el número de suicidios.

Su tolerancia es 1 % y no 0,5 % por una razón de la fuente, no de los datos: el anuario
publica un porcentaje redondeado a una décima, no un conteo. «9,7 %» significa
[9,65 %, 9,75 %], que sobre 63.710 hombres es la banda [6.148, 6.212] — ±0,5 % de puro
redondeo, que consumiría toda la tolerancia habitual.

**Por qué el denominador tiene tolerancia veinte veces más estricta.** Las anclas de
defunciones comparan productos de dos organismos distintos, donde un desvío pequeño puede
ser metodológico. Las de población salen de sumar el mismo archivo que el pipeline lee: ahí
cualquier diferencia es un defecto de lectura, no una discrepancia legítima.

**Dónde se hacen cumplir.** `obsm build gold` reconcilia en modo estricto **antes** de
calcular: una sola ancla fuera de tolerancia aborta y no se escribe archivo. Verificado
alterando un ancla a propósito — el CSV anterior quedó intacto y el proceso salió con
código 1. `obsm qa` corre las mismas anclas en modo diagnóstico, sin bloquear, para ver
todas las caídas de una vez.

Existe `--sin-reconciliar` para depurar. La salida que produce **no es publicable** y el
metadato lo declara.

**Lo que estas anclas NO validan.** Sigue sin haber ancla del conteo de suicidios en sí:
el subconjunto X60-X84 no tiene una cifra oficial publicada que se haya comprobado en
sesión. Se buscó el 2026-07-27 sin éxito en el Anuario del INE (solo trae porcentajes por
capítulo), en los *Indicadores Básicos de Salud* del DEIS (traen tasas de 2007, no conteos,
y una tasa antigua arrastra el denominador de su época) y en la vigilancia de epi.minsal.cl
(cubre lesiones no mortales). Queda pendiente.

Lo verificado, entonces: la ingesta completa cuadra, el denominador cuadra, y el capítulo de
causas externas cuadra. Eso acota mucho dónde podría estar un error del numerador, pero no
es lo mismo que verificar el suicidio. La diferencia importa y por eso queda escrita.

**Sobre el desglose por sexo del anuario.** El archivo trae 63.711 hombres y el anuario dice
63.710. La diferencia es del anuario: su desglose sale de la Tabla 3 (p.45), que suma 122.217
porque excluye un registro sin edad. El desglose propio cierra exacto —63.711 + 58.495 + 12
indeterminados = 122.218— y confirma la advertencia que ya traía A-005 sobre esa tabla.

**Historia de por qué esto existe.** `quality.verificar_reconciliacion` sabía comparar dos
números desde el primer día y pasaba sus tests, pero **ninguna parte del pipeline la
llamaba**. La regla «si no cuadra, no se publica» dependía de que una persona se acordara de
correr la comprobación a mano; la reconciliación de A-005 se hizo en un script desechable
que después se perdió. Un pipeline que valida solo cuando alguien se acuerda no valida.

## Quiebres de serie

Una tabla `quiebres` acompaña a todo dataset publicado: fecha, fuente, descripción y efecto
esperado. Ejemplos que ya se anticipan:

| Fecha | Fuente | Quiebre | Efecto |
|---|---|---|---|
| 1997-1998 | defunciones | paso de CIE-9 a CIE-10 | comparabilidad limitada hacia atrás |
| 2018 | todas | creación de la región de Ñuble | series regionales de Biobío y Ñuble no comparables sin recodificar |
| **2018-2019** | REM-P6 | el formulario cae de 128 a 105 columnas y de 196 a 142 filas | **medido**: quiebre estructural, no epidemiológico |
| **2021-2022** | REM-P6 | las columnas casi se duplican, de 122 a 234 | **medido**: quiebre estructural |
| 2011-2014 | REM-P6 | de 55 a 124 columnas | prácticamente otro instrumento |
| pendiente | población | re-base de proyecciones tras el Censo 2024 | todas las tasas cambian retroactivamente |
| variable | Glosa 06 | cambios de criterio de depuración de la lista | saltos de nivel sin cambio de acceso |

### REM: tres bloques comparables, no una serie {#quiebres-rem}

Medido el 2026-07-27 sobre los diccionarios de códigos de la Serie P, bajados de los 17
archivos `SERIE_REM_YYYY.zip` publicados por DEIS. La sección de salud mental es **REM-P6**
en todos los años en que se pudo leer, pero sus dimensiones no se parecen:

| Año | Filas × Columnas | |
|---|---|---|
| 2009 | — | diccionario **encriptado con contraseña** |
| 2010 | 88 × 55 | |
| 2011 | 90 × 55 | |
| 2012 | — | diccionario **encriptado** |
| 2013 | — | archivo de **0 bytes** en el servidor |
| 2014 | 201 × 124 | |
| 2015 | 199 × 126 | |
| 2016 | 192 × 126 | |
| 2017 | 203 × 128 | |
| 2018 | 196 × 128 | |
| 2019 | 142 × 105 | **quiebre** |
| 2020 | 135 × 122 | |
| 2021 | 138 × 122 | |
| 2022 | 143 × 234 | **quiebre** |
| 2023 | 146 × 236 | |
| 2024 | 146 × 236 | |
| 2025 | 155 × 235 | |

**Consecuencia para el alcance.** El plan asumía «serie mensual comunal 2018–presente». Lo
que hay son **tres bloques**: 2014-2018, 2019-2021 y 2022-2025. Empalmar conceptos entre
bloques va a ser posible para algunos y no para otros, y cuáles es una pregunta abierta
hasta extraer la correspondencia columna → concepto de cada año.

**Por qué la serie no puede empezar en 2009.** Los datos de 2009, 2012 y 2013 están
publicados, pero sin diccionario no se sabe qué cuenta cada columna: el archivo trae
`Col01` a `Col38` y el significado depende del `CodigoPrestacion` de la fila. Dos
diccionarios están protegidos con contraseña y uno pesa cero bytes. Hasta encontrarlos en
otra parte, esos años son ilegibles aunque estén descargados.

**Cómo se midió sin bajar 3,5 GB.** Cada `SERIE_REM_YYYY.zip` pesa ~220 MB y de cada uno
solo interesaba un diccionario de medio mega. Se usó `io.listar_zip_remoto` y
`io.extraer_de_zip_remoto`, que leen el índice central del ZIP por rangos HTTP y bajan solo
el miembro pedido: **6,8 MB en total**.

## Anomalías {#anomalias}

Registro vivo. **Una anomalía no se corrige hasta estar explicada.** Muchas son reales: un
CESFAM que dejó de reportar tres meses es un dato sobre el sistema, y borrarlo falsifica el
diagnóstico.

Formato de entrada:

```
### A-001 · <fuente> · <fecha de detección> {#a-001}
Qué se observó:
Reproducción: (comando)
Hipótesis:
Verificación:
Decisión: [conservar | marcar | excluir con nota]
```

### A-001 · capas cartográficas de comunas · 2026-07-27 {#a-001}

**Qué se observó:** la capa «Comunas de Chile» del Centro de Datos OCUC (ArcGIS Hub,
`e3a1f8c4aa014429847c2944e3d92406_0`), publicada bajo el título «División Político
Administrativa de Chile 2026», entrega 341 comunas y 13 regiones.

**Reproducción:**

```
curl --ssl-no-revoke "https://services9.arcgis.com/kKJR3Qt68ohAWuet/arcgis/rest/services/\
Comunas_de_Chile/FeatureServer/0/query?where=1%3D1&outFields=cut&returnDistinctValues=true\
&returnGeometry=false&returnCountOnly=true&f=json"
```

**Hipótesis:** no faltan cinco comunas; la capa arrastra la codificación CUT anterior a 2007.

**Verificación:** ningún CUT empieza en 14, 15 ni 16. Chillán figura como `8401` (debería
ser `16101`) con `provincia = NUBLE` dentro de la región 8; Valdivia como `10501` (debería
ser `14101`); Arica como `1201` (debería ser `15101`). Hay además contradicción interna: el
campo `region_1` da `XV` para Arica y `I` para Camarones, ambas de la misma provincia. El
título «2026» corresponde a la fecha de publicación del recurso, no a la vigencia de los datos.

**Por qué importa más de lo que parece:** DEIS, REM e INE usan el CUT vigente. Un maestro con
códigos antiguos no rompe el join: lo deja vacío. Las 21 comunas de Ñuble, las 12 de Los Ríos
y las 4 de Arica y Parinacota —37 en total— quedarían con cero eventos y aparecerían como las
más sanas del país, sin un solo error en pantalla.

**Decisión:** excluida como fuente territorial. Se adoptó el maestro `subdere_cut`.

**Control heredado:** toda capa o tabla territorial candidata debe verificar que Chillán sea
`16101`. Es un solo dato y detecta ocho años de desfase.



### A-002 · deis_defunciones · 2026-07-27 {#a-002}

**Qué se observó:** la serie oficial de defunciones DEIS cubre 1990–2023, pero los códigos
de causa de los primeros años no son CIE-10.

**Reproducción:** barrido sobre las 3.182.446 filas de
`DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.zip`, contando por año qué forma tiene
`DIAG1`.

**Verificación:** el corte es limpio, sin años mezclados.

| años | filas | forma de `DIAG1` | clasificación |
|---|---|---|---|
| 1990–1996 | 536.746 | 100 % empieza en dígito (`9509`, `9941`) | CIE-9 |
| 1997–2023 | 2.645.700 | 100 % empieza en letra (`X70`, `P219`) | CIE-10 |

**Por qué importa:** los agrupadores de `cie10.py` buscan rangos tipo `X60`–`X84`. Contra
códigos CIE-9 no lanzan ninguna excepción: **devuelven cero**. Una serie de suicidio que
arrancara en 1990 mostraría siete años planos en cero, con la forma de un hallazgo
epidemiológico y no de un error de software. Es el modo de falla más caro del proyecto:
silencioso y con apariencia de dato.

**Decisión:** conservar. El ingestor agrega `clasificacion_causa` (`cie10` / `cie9` /
`desconocido`) derivada de la forma del código, no del año, porque el año también puede
venir mal. Filtrar es decisión de `transform/`, no del ingestor. `ANIO_INICIO_CIE10 = 1997`
queda documentado en `obsm.ingest.deis_defunciones`.

**Control heredado:** ninguna serie que use agrupadores CIE-10 puede incluir filas con
`clasificacion_causa != "cie10"` sin advertencia explícita.

**Pendiente abierto:** no se sabe cómo se codifica el suicidio en 1990–1996. `E95x`, la
clase habitual de CIE-9 para lesiones autoinfligidas, aparece **0 veces** en las 536.746
filas del período, tanto en `DIAG1` como en `DIAG2`. Hasta resolverlo, **la serie de
suicidio no puede empezar antes de 1997**. Una versión anterior de este documento afirmaba
que `E950` se publicaba como `9509`: era una conjetura no verificada y se retiró.

### A-004 · deis_defunciones · 2026-07-27 {#a-004}

**Qué se observó:** el código de suicidio no está en la columna de causa básica.

**Reproducción:** conteo de `X60`–`X84` sobre las 2.645.700 filas CIE-10 (1997–2023).

| columna | significado según el diccionario | X60–X84 |
|---|---|---|
| `DIAG1` | causa básica de defunción | **0** |
| `DIAG2` | causa externa de defunción | **46.805** |

Los ejemplos son inequívocos: `DIAG1 = T71X` (asfixia) con `DIAG2 = X704` (ahorcamiento
autoinfligido). `DIAG1` trae la naturaleza de la lesión; el código que define el hecho
está en `DIAG2`.

**Por qué importa:** `transform/silver.py` aplica todos los agrupadores a una sola columna.
Con `causa_cie10 = DIAG1`, el agrupador `SUICIDIO` habría devuelto **cero suicidios en
veintisiete años**, sin lanzar ninguna excepción. 46.805 muertes en 27 años son ~1.730 al
año, que es el orden de magnitud correcto para Chile: la cifra correcta era comprobable y
la incorrecta también lo era, porque un cero absoluto es imposible.

Este es el mismo modo de falla de A-002 y se cometió en el mismo commit que lo documentaba.
Escribir la advertencia no basta: hay que ejecutarla contra el dato.

**Decisión:** conservar ambas columnas con su nombre y significado —`causa_basica` y
`causa_externa`— y derivar `causa_cie10` como la externa cuando existe y la básica cuando
no. Así los agrupadores de lesiones (X60-X84) y los de enfermedad (F30-F39, que van en la
básica con `DIAG2` vacío) leen ambos la columna correcta. La procedencia queda en
`origen_causa_cie10`.

**Control heredado:** `test_el_agrupador_de_suicidio_no_devuelve_cero` corre el fixture de
estructura real de punta a punta por `silver` y exige un conteo distinto de cero. Ningún
indicador de mortalidad por causa externa debe darse por bueno sin un test que cuente.

### A-003 · deis_defunciones · 2026-07-27 {#a-003}

**Qué se observó:** `COD_COMUNA` trae 4 caracteres en 1.551.470 filas y 5 en 1.630.976.

**Verificación:** las de 4 corresponden a las regiones 01–09, que perdieron el cero a la
izquierda (`8304` por `08304`, Laja). Es el problema que `CLAUDE.md §5` anticipa.

**Decisión:** conservar tal cual en `bronze`; `silver` está obligado a pasarlo por
`territorio.formatear_cut_comuna`. Hay un test que verifica que el problema siga presente
en el fixture, para que nadie «arregle» la fuente por el lado equivocado.

### A-005 · reconciliación · 2026-07-27 {#a-005}

**Qué se observó:** al contrastar los totales anuales del archivo de causas contra la serie
«Defunciones por Semana Epidemiológica» del propio DEIS, 4 de 14 años caen fuera del ±0,5 %.

| año | causas | semanal | dif % |
|---|---|---|---|
| 2012 | 98.711 | 98.211 | +0,51 % |
| **2014** | 101.960 | 103.431 | **−1,42 %** |
| 2016 | 104.026 | 103.417 | +0,59 % |
| **2020** | 126.169 | 127.734 | **−1,23 %** |
| resto | — | — | +0,23 % a +0,32 % |

**Hipótesis:** las dos diferencias grandes son negativas y las demás positivas y estables.
Eso no parece error de dato sino de unidad de tiempo.

**Verificación:** contando semanas distintas por año en la serie semanal, **2014 y 2020 son
los únicos años de 53 semanas** del período (también 2025). Son exactamente los dos que
salen negativos. Un año epidemiológico de 53 semanas cubre ~7 días más que uno calendario,
y ~7/365 = 1,9 % acota bien las diferencias observadas.

**Decisión:** **la serie semanal no sirve como ancla de reconciliación al ±0,5 %.** No está
en año calendario sino en año epidemiológico, y comparar ambas es comparar períodos
distintos. El sesgo positivo estable de +0,28 % en los años de 52 semanas es el residuo del
mismo desfase de bordes.

**RESUELTO el mismo día.** Se obtuvo el ancla en año calendario: el *Anuario de Estadísticas
Vitales 2023* del INE (fuente `ine_vitales_anuario`, p.38). La reconciliación es **exacta a
la unidad**, no dentro de tolerancia:

| año | archivo de causas | Anuario INE |
|---|---|---|
| 2023 | 122.218 | **122.218** |
| 2020 | 126.169 | **126.169** |

Eso confirma tres cosas de una: el archivo de causas se lee completo y sin pérdida, está en
año calendario, y el desvío de esta anomalía era de la serie semanal y no de los datos.

Cuidado al releer el anuario: la Tabla 3 (p.45) dice 122.217 porque desagrega por grupo de
edad y deja fuera un registro sin edad; y 63.710 hombres + 58.495 mujeres = 122.205, con 12
registros de sexo no asignado. La cifra comparable es la de titular, 122.218.

**Lección:** un ancla de reconciliación es tan buena como su definición temporal. Dos
productos del mismo organismo pueden no ser comparables entre sí.

### A-006 · deis_defunciones · 2026-07-27 {#a-006}

**Qué se observó:** al ingerir el archivo real (869 MB) el proceso no llegaba a arrancar.

**Verificación:** `detectar_encoding` declara `muestra_bytes: int = 200_000` pero hacía
`ruta.read_bytes()[:muestra_bytes]`: cargaba el archivo completo y recién después recortaba.
`leer_texto` cargaba otra copia entera, y el ingestor solo usaba de ella la primera línea.
Entre ambas, ~1,7 GB antes de que pandas empezara.

**Decisión:** `detectar_encoding` lee solo la muestra; se agrega `leer_primera_linea` para
los ingestores. Corrida completa: 3.182.446 filas en 11 min 12 s.

**Lección:** ningún fixture de 15 filas puede exponer esto. Hay defectos que solo existen a
escala real, y por eso la ingesta contra la fuente real es parte de verificar, no un extra.

### A-007 · deis_defunciones · 2026-07-27 {#a-007}

**Qué se observó:** silver corrió sobre los 3.182.446 registros reales y reportó
`cut_invalidos: 0`. Ese cero era demasiado limpio para una serie de 34 años que cruza la
creación de las regiones 14 y 15 (2007) y de la 16 (2018), así que se comprobó.

**Verificación:** dos hallazgos, uno bueno y uno malo.

1. **DEIS recodificó su historia al CUT vigente.** Chillán aparece como `16101` en los 34
   años, incluidos los anteriores a la creación de Ñuble. No hay mezcla de marcos
   territoriales en el archivo, lo que coincide con la decisión de ADR 0002.
2. **64 filas traen `99999`**, centinela de «comuna ignorada». Silver validaba el *formato*
   del CUT, no su *existencia*: `99999` tiene cinco dígitos, pasaba como comuna real y
   generaba `region_cut` 99. La ruta por nombre sí contrastaba contra la DPA; la ruta por
   código, que es la que se considera más confiable, no. De ahí el `cut_invalidos: 0`.

**Decisión:** silver valida ahora la pertenencia a la DPA en ambas rutas y el reporte
distingue `cut_mal_formados` (no parsea) de `cut_fuera_de_dpa` (parsea pero no existe).
Las 64 filas se mantienen —no se borran— mapeadas a `COMUNA_DESCONOCIDA` y contadas, para
que el total nacional siga cuadrando con el ancla de reconciliación. Quedan excluidas de
todo indicador comunal por no tener denominador.

**Seguimiento (2026-07-27).** Al construir la cadena completa sobre fixtures se vio que un
caso ocurrido en una comuna sin denominador **desaparece de `gold` sin dejar rastro**: el
join es contra la población, así que el centinela `99999` se cae y el total publicado deja
de cuadrar con el de la fuente. `gold` declara ahora `casos_sin_denominador` y
`areas_sin_denominador` en su metadato. Sobre el archivo real el valor es 0 —las 64 filas
con `99999` no incluyen ningún suicidio, comprobado— pero el cero ahora está medido en vez
de supuesto.

**Lección:** un indicador de calidad que sale perfecto a la primera hay que auditarlo antes
que celebrarlo. Acá el `0` no medía lo que su nombre decía que medía.

### A-008 · ine_proyecciones · 2026-07-27 {#a-008}

**Qué se observó:** al verificar el denominador se constató que las proyecciones comunales
del INE (base 2017) empiezan en **2002**, mientras la serie de defunciones va de 1990 a 2023.

**Verificación:** descarga real del archivo comunal (9.768.366 bytes, sha256 `c2a88471…`):
56.052 filas = 346 comunas × 2 sexos × 81 edades, con una columna `Poblacion <año>` por cada
año de 2002 a 2035. Cruce contra la DPA: 346 comunas y 16 regiones, **cero diferencias en
ambas direcciones**. Total nacional 2020 = 19.458.310, idéntico a la cifra publicada.

**Decisión:** la ventana de tasas comunales es **2002-2023**, no 1990-2023. El límite lo fija
el denominador, no el numerador, y se acumula con el de A-002: las defunciones están en CIE-9
hasta 1996, así que la serie de suicidio en CIE-10 no puede empezar antes de 1997 y la de
*tasas comunales* no antes de 2002. Los años 1990-2001 quedan disponibles como conteos, nunca
como tasas comunales. Ningún indicador debe extrapolar población hacia atrás para rellenar.

**Consecuencia operativa:** el cálculo de tasas debe fallar ruidosamente si se le pide un año
sin denominador, no devolver `NaN` ni cero. Un cero en una tasa se lee como «no hubo casos»,
que es exactamente la lectura contraria a «no hay población para dividir».

**Nota de trampa:** `Comuna` viene como entero sin cero a la izquierda (`1101`), igual que
`COD_COMUNA` en DEIS (A-003). Con `zfill(5)` el join es perfecto; sin él se pierden en
silencio todas las comunas de las regiones 01 a 09.

### A-009 · ine_proyecciones · 2026-07-27 {#a-009}

**Qué se observó:** al ingerir el archivo real aparecieron **8.060 celdas con población
cero** (0,42 % de 1.905.768). Un test del propio ingestor afirmaba que eso no podía pasar.

**Verificación:** los ceros son correctos. Se concentran en **15 comunas de 346**, todas
diminutas: Antártica (3.286 celdas), Río Verde, Timaukel, Laguna Blanca, Ollagüe, Tortel,
Torres del Paine, O'Higgins. Las comunas sí tienen habitantes —Antártica pasa de 48 en 2002
a 137 en 2020—; lo que está vacío son celdas concretas de comuna × sexo × edad × año. En
Antártica no vive ninguna mujer de 73 años, y eso es un hecho, no un dato faltante.

**Decisión:** los ceros se conservan tal cual. Lo que se corrigió fue el test, que afirmaba
`poblacion > 0` y pasaba únicamente porque el fixture no tenía ceros: validaba el supuesto
contra sí mismo, el mismo defecto que produjo A-004. El fixture ahora incluye Antártica con
celdas en cero, y el contrato quedó en lo que sí es verdad: la población puede ser cero,
nunca nula ni negativa. Un nulo indicaría lectura fallida; un cero indica que no hay nadie.

**Consecuencia operativa:** el cálculo de tasas no puede dividir por estas celdas. Un
denominador cero con numerador cero no es una tasa de 0 sino una tasa indefinida, y con
numerador positivo es imposible por construcción (nadie puede morir en una celda donde no
vive nadie): si aparece, es un error de join, no un dato. La supresión por umbral k ya
retiraría estas celdas de la salida pública, pero el cálculo debe protegerse antes, porque
la supresión ocurre después.

**Nota:** estas 15 comunas son exactamente donde importa el suavizado bayesiano empírico del
paso 4 de Fase 1. Una tasa comunal calculada sobre denominadores de dos dígitos es ruido.

**Lección (repetida):** un fixture que no contiene el caso feo no prueba nada sobre él, y un
test escrito contra ese fixture confirma la creencia del autor en vez de la fuente. Es la
segunda vez en este proyecto; por eso la ingesta contra el archivo real es parte de
verificar y no un extra.

### A-010 · rem_salud_mental · 2026-07-28 {#a-010}

**Qué se observó:** la ingesta de los doce años murió en el primero, 2014, con
`TypeError: cannot safely cast non-equivalent float64 to int64`.

**Verificación:** el archivo trae valores **fraccionarios** en columnas que cuentan
personas: `123.55`, `186.1`, `0.85`. Son poquísimos —uno o dos por columna en 200.000
filas— pero están en filas de la sección P6, o sea en el dato que se publica. Una persona
bajo control con decimales no existe: es un error de digitación del formulario.

**Decisión:** no se redondean. Forzar a entero hace una de dos cosas malas: revienta la
ingesta del año completo, o altera el dato en silencio. Se conservan tal cual, se cuentan
en el reporte de silver (`celdas_con_valor_fraccionario`) y redondear queda como decisión
de la capa que publica, que además puede declararlo.

**Segundo defecto, este propio y peor.** El comando guardaba cada año por separado
justamente para que un fallo no costara el trabajo previo — pero su manejo de errores
atrapaba solo `ObsmError`. Un `TypeError` se escapó y mató la corrida entera en el primer
año, perdiendo los once siguientes. El diseño era correcto y la implementación lo
contradecía. Ahora atrapa cualquier excepción por año.

**Lección:** un mecanismo de recuperación que solo maneja los errores que uno anticipó no
es un mecanismo de recuperación. Los errores que cuestan caro son precisamente los que no
se anticiparon.

### A-011 · rem_salud_mental · 2026-07-28 {#a-011}

**Qué se observó:** la serie nacional de trastornos de ansiedad mostraba una caída del 99 %
en un solo año y una recuperación al siguiente.

| año | personas |
|---|---|
| 2018 | 257.266 |
| **2019** | **1.589** |
| 2020 | 226.703 |

**Verificación:** no es epidemiología, es el lector de diccionarios. En la hoja P6 de 2019
los códigos aparecen **dos veces**: en las filas 73-104 con su grupo y su concepto, y otra
vez en las filas 118-139 sin ninguno de los dos —un listado al final del formulario—. El
extractor guardaba en un diccionario, así que ganaba la última aparición. Los veintidós
códigos de ansiedad quedaron con el grupo que venía arrastrado desde el encabezado anterior
(«Programa de rehabilitación tipo II») y el concepto en blanco, y al agrupar por etiqueta
sus 234.027 casos se fueron a otra fila.

**El dato nunca se perdió: se perdió su nombre.** Para un observatorio eso es igual de
grave, porque un número sin etiqueta no se puede leer, comparar ni corregir. Y el síntoma
—una caída seguida de una recuperación— es exactamente lo que un lector interpretaría como
el efecto de una política o de la pandemia.

**Decisión:** ante un código repetido gana la aparición que trae concepto; las repeticiones
se registran en el log. Corregidos cuatro años: 2019 (22 etiquetas), 2025 (12), 2021 (10) y
2017 (2). Tras el arreglo, 2019 da 234.027, entre sus dos vecinos.

**Cómo apareció, que es lo importante.** Todo lo anterior se probó sobre 2023, y en 2023
las etiquetas están bien: el defecto era **invisible** con un solo año. Lo destapó mirar la
serie completa en el tiempo.

**Lección:** verificar una serie exige mirarla entera. Un año aislado valida el lector, no
la serie; y una anomalía temporal que se explica sola por «la pandemia» o «un cambio de
política» merece la misma desconfianza que cualquier otro resultado cómodo.

### A-012 · rem_salud_mental · 2026-07-28 {#a-012}

**Qué se observó:** al preparar la ficha del dataset, el mismo concepto aparecía dos veces
en la tabla publicable:

```
NUMERO DE PERSONAS EN CONTROL EN EL PROGRAMA   202.768
Número de personas en control en el programa   845.850
```

**Verificación:** el formulario escribe los conceptos con distinta grafía según el año.
Veintidós conceptos estaban partidos, incluidas erratas de la propia fuente: «post
traumatico» sin tilde en unos años y con tilde en otros, «Síndrome de rett» con minúscula.
En total, 116 etiquetas que eran 70 conceptos.

**Por qué importa más de lo que parece.** Quien filtre por `"Depresión moderada"` pierde en
silencio las filas de `"DEPRESIÓN MODERADA"`. El total nacional se parte en dos y nada lo
advierte: ambas cifras son plausibles por separado.

**Decisión:** silver agrega `etiqueta_norm` —mayúsculas, sin tildes— y gold agrupa por esa
llave. La etiqueta que se publica es la **variante más frecuente en los datos**: elegirla
por frecuencia y no por criterio propio hace que la decisión sea reproducible y que se
mueva sola si la fuente estandariza su escritura.

**Un tropiezo en el arreglo, que vale más que el arreglo.** La primera corrección cambió el
valor por defecto de `tabla_rem`, pero el CLI pasa las dimensiones explícitamente: se
modificó un default que nadie usaba. La corrida terminó sin error y con **exactamente las
mismas 229.892 filas** que antes. Ese número idéntico fue la única señal.

**Lección:** verificar no es «corrió sin error», es «cambió lo que esperaba que cambiara».
Un arreglo que deja la salida byte por byte igual no arregló nada.

### A-013 · fonasa_inscritos · 2026-07-28 {#a-013}

**Qué se observó:** buscando el denominador de cobertura de APS, la serie de población
inscrita de SINIM trae comunas con valor `0` y población real de decenas de miles. Tocopilla
aparece con **0 inscritos** y 28.369 habitantes proyectados.

**Verificación:** mirando la misma comuna hacia atrás en la serie, el valor no siempre fue
cero:

```
05703 LLAILLAY        2015 = Sin Servicio    2020 = 0    2025 = 0
02301 TOCOPILLA       2015 = Sin Servicio    2020 = 0    2025 = 0
05201 ISLA DE PASCUA  2015 = Sin Servicio    2020 = 0    2025 = 0
```

Lo que cambió no fue la realidad: fue la codificación. Hasta ~2019 SINIM escribía la palabra
`Sin Servicio` —la atención primaria de esa comuna no la administra el municipio sino
directamente el Servicio de Salud— y desde entonces escribe `0`. Son **36 comunas**, 25 de
ellas todavía en 2025.

**Por qué importa.** Un centinela textual es imposible de confundir: `int("Sin Servicio")`
revienta. Un `0` entra sin ruido en cualquier cálculo. Como denominador da división por cero
o cobertura infinita; como numerador dice «ninguna persona inscrita» de una comuna que tiene
CESFAM funcionando. Es el mismo dato faltante, pero uno falla ruidosamente y el otro miente.

Las otras tres marcas del vocabulario tampoco son números y tampoco significan lo mismo
entre sí: `Costo Fijo` (647 celdas) es una comuna financiada por costo fijo y no por
per cápita; `No Recepcionado` (345) es que el dato no llegó —**todo el año 2023**—; `No
Aplica` (17) es que la comuna no existía aún.

**Decisión:** cuando se implemente el ingestor, las cuatro marcas se conservan en una columna
`motivo_sin_dato` y **el `0` de una comuna sin servicio municipal se convierte en nulo, no en
cero**, cruzando contra la lista de las 36. No se imputa. Una comuna sin APS municipal no
tiene denominador comunal, y publicar una cobertura para ella sería inventarla.

**Lección:** cuando una fuente cambia de centinela textual a centinela numérico, el error
deja de ser visible y empieza a ser plausible. Antes de usar una serie larga como
denominador, hay que mirar el **vocabulario de lo no numérico año por año**, no solo si
parsea.

### A-014 · silver → gold · 2026-07-28 {#a-014}

**Qué se observó:** al validar `fonasa_inscritos` contra las proyecciones del INE, la
cobertura nacional daba **33 %** en vez del ~73 % esperado. El denominador estaba al doble:
`data/silver/ine_proyecciones/` contenía **dos parquet idénticos**, uno con sufijo de hash,
dejados por dos corridas del ingestor con distinta convención de nombre.

**Verificación:** el error era del análisis exploratorio, que hacía `glob("*.parquet")` y
concatenaba. **La tabla `gold` publicada no está afectada:** el CLI usa `candidatos[-1]`
([cli.py:140](../src/obsm/cli.py#L140), [cli.py:565](../src/obsm/cli.py#L565)), toma un solo
archivo, y las tasas de suicidio publicadas siguen reconciliando contra el Anuario del INE.

**Lo que sí queda como riesgo.** `candidatos[-1]` elige **por orden alfabético** entre los
archivos que haya. Con dos copias del mismo contenido da igual. Con dos versiones distintas
—proyecciones base 2017 y base Censo 2024 conviviendo en el directorio, que es justamente lo
que viene— elegiría una por accidente de nombre, en silencio, y cambiaría todas las tasas
publicadas sin que nada lo advierta. Es el modo de falla que CLAUDE.md §2.7 prohíbe.

**Decisión: corregido el 2026-07-29.** `io.elegir_tabla` reemplaza a los seis
`sorted(...)[-1]` del CLI. Devuelve `None` si no hay archivos, el único si hay uno, y
**lanza `SchemaDriftError` con dos o más sin desempate explícito**. El mensaje nombra los
archivos y ofrece las dos salidas: borrar el obsoleto, o pasar el elegido a mano. Elegir a
mano es aceptable; elegir por accidente, no.

`obsm qa` lo trata distinto que `build`: reporta el almacén ambiguo como hallazgo y sigue
con las demás fuentes, porque `qa` existe para enumerar problemas. El que bloquea la
publicación es `build gold`.

### Lo que apareció al encender el guard

Dos almacenes ambiguos reales, no uno:

| Directorio | Archivos | ¿Eran lo mismo? |
|---|---|---|
| `silver/ine_proyecciones/` | 2 parquet | **sí**, idénticos — el caso que originó la anomalía |
| `bronze/fonasa_inscritos/` | 2 parquet | **no**: 8.625 filas sin `variable_codigo` contra 34.500 con cuatro variables |

El segundo es exactamente el escenario que la anomalía anticipaba en teoría, encontrado en
la práctica el mismo día: **dos versiones genuinamente distintas de una fuente**, una de
ellas producida por una versión anterior del ingestor. `sorted()[-1]` elegía la correcta
—`sinim_p…` ordena después de `sinim_h…`— y por eso todo funcionaba. La corrección estaba
decidida por el orden alfabético de un nombre de archivo.

Resueltos ambos, el pipeline reproduce cifras idénticas: 185 comunas con cobertura,
5/5 anclas cuadrando.

**Lección:** el riesgo se documentó como hipotético —«cuando convivan base 2017 y base
Censo 2024»— y ya estaba ocurriendo en otra fuente, sin síntoma. Un guard que solo se
justifica por un escenario futuro conviene encenderlo igual: lo primero que hace es decir
cuántas veces el escenario ya pasó.

### A-015 · fonasa_inscritos · 2026-07-28 (corregido el 2026-07-29) {#a-015}

> **Esta anomalía se documentó mal el primer día y la corrección es más importante que el
> hallazgo.** Se dejó el texto original tachado abajo, no por prolijidad: el error de
> razonamiento es el que vale la pena no repetir.

**Qué se observó:** comunas de miles de habitantes con cifras de una o dos cifras de
población inscrita. Quirihue: 9.204 en 2014 y **33** en 2025, sobre 12.244 habitantes.

**Qué se concluyó primero, y era falso.** SINIM publica, además del total `HPISM`, tres
variables etarias (`HPVM6`, `HPV2064`, `HPVM64`). Puestas al lado, el total parecía
contradecirlas: Quirihue 2024 declaraba 31 en total y 6.133 repartidos por edad. Se razonó
que los tramos eran el desglose del total, que por ser disjuntos su suma era una cota
inferior, y que `total < suma(tramos)` era **imposible por construcción**. La serie
respaldaba la teoría de forma casi perfecta: 0 violaciones en 4.863 celdas entre 2001 y
2018, y un salto a 87-100 por año desde 2019.

**Qué mostró la fuente original.** FONASA publica el padrón por establecimiento
(`Inscritos-APS-2022.zip`). Para Quirihue trae **una sola fila**:

```
COMUNA    NOMBRE_CENTRO                     NOMBRE_DEPENDENCIA  TOTAL_INSCRITOS
Quirihue  Posta De Salud Rural Los Remates  Municipal                        11
```

El 11 es correcto. El único establecimiento **municipal** de Quirihue es una posta rural con
once inscritos; al resto de la comuna la atiende un establecimiento dependiente del Servicio
de Salud, que no entra en un padrón de APS municipal. Lo mismo en Palena (una posta, 5
inscritos).

**La confusión estaba en los nombres de las variables**, y bastaba leerlos completos:

| Variable | Nombre real | Universo |
|---|---|---|
| `HPISM` | Población Inscrita Validada en Servicios de Salud **Municipal** | inscritos en APS municipal |
| `HPV2064` | Población Adulta 20-64 Validada como **Beneficiaria** por FONASA | beneficiarios del seguro |

No son el total y su desglose: son **dos universos distintos**. En casi todas las comunas
casi coinciden —de ahí los dieciocho años sin violaciones— y divergen exactamente donde la
APS no es municipal. El «quiebre de 2019» tampoco era un quiebre de calidad: es el año en
que SINIM dejó de escribir `Costo Fijo` en esas comunas y empezó a publicar su cifra
municipal real, que siempre había sido chica.

**Confirmación cruzada, por dos vías independientes:**

1. De las **24 comunas sin ninguna fila** en el padrón de FONASA, **22** son las que SINIM
   marca `Sin Servicio`. Las dos fuentes coinciden en cuáles no tienen APS municipal.
2. El REM registra actividad del orden de **miles** de personas en control en Quirihue,
   Palena y Tocopilla, donde el padrón municipal dice 11, 5 y 0.

### La anomalía real

No hay valores corruptos. Hay un **desajuste de universos** entre numerador y denominador:

- El **REM** cuenta actividad de toda la APS pública: municipal **y** dependiente del
  Servicio de Salud.
- **`fonasa_inscritos`** cuenta solo la municipal, tanto vía SINIM como en el archivo
  original de FONASA (`Municipal` 13.446.800 + `Otra Institución` 138.216; los
  establecimientos del Servicio de Salud no aparecen).

Donde la comuna se atiende en un hospital comunitario, el numerador incluye a esa población
y el denominador no. La cobertura resultante no es alta ni baja: **no significa nada**.

**Decisión:** las dos marcas se conservan porque siguen señalando el caso correcto, con la
interpretación corregida en sus docstrings. `denominador_implausible` conserva su nombre por
compatibilidad, y el nombre es malo: el valor no es implausible, lo implausible es usarlo de
denominador comunal. No se imputa nada y no se borra nada.

**Lo que falta:** un denominador de APS **total**. El padrón de FONASA trae `COD_CENTRO`,
así que cruzarlo con el maestro de establecimientos de DEIS permitiría saber qué comunas
quedan incompletas y en cuánto. Es trabajo pendiente, no resuelto acá.

### Lección

La teoría anterior no era descuidada: predecía un patrón nítido y la serie lo confirmaba con
0 excepciones en 4.863 celdas. **Un ajuste excelente contra los datos no valida la premisa**;
acá el ajuste venía de que dos universos casi coinciden, no de que uno contenga al otro.

Lo que faltó fue lo más barato: **leer el nombre completo de las variables**. Decían
«Municipal» y «Beneficiaria», y esas dos palabras contenían la respuesta desde el principio.
Se prefirió inferir el significado de la forma de los números antes que leer la etiqueta —el
mismo error que ya había aparecido en esta sesión con el REM y que quedó anotado en el
resumen anterior.

Y la comprobación decisiva no salió de razonar mejor sobre SINIM, sino de **bajar la fuente
original**. Cuando un intermediario parece contradecirse, la pregunta no es qué le pasa al
intermediario: es qué dice el que produjo el dato.

<details>
<summary>Texto original del 2026-07-28, incorrecto, conservado como registro</summary>

Se afirmaba que once comunas con historial «Costo Fijo» publicaban desde 2020 «cifras de una
o dos cifras sobre miles de habitantes» y que el campo del total estaba **roto** mientras sus
componentes estaban bien; que los tramos eran subconjuntos disjuntos del total y que
`total < suma(tramos)` era imposible por construcción; y que el quiebre de 2019 era un
defecto de la fuente. Nada de eso era cierto: los valores son correctos, los tramos miden
otro universo, y 2019 es el año en que SINIM empezó a publicar la cifra municipal real.

</details>

### A-016 · deis_establecimientos · 2026-07-29 {#a-016}

**Qué se observó:** la verificación de hash de `obsm.io.descargar` abortó la primera ingesta
del maestro de establecimientos. El archivo bajado con `curl` minutos antes y el bajado por
el pipeline tenían hashes distintos.

**Verificación:** no era una descarga corrupta ni una página de error servida con 200. El
archivo **había cambiado de verdad** entre dos descargas separadas por minutos: 5.707 → 5.717
establecimientos y **1.996 filas** con un campo reescrito. Todas en la misma columna:

```
                     antes            ahora
Primer Nivel         2.478      ->    3.016
Primario               534      ->        0
Secundario           1.414      ->        0
Segundo Nivel          235      ->    1.693
Terciario                6      ->        0
Tercer Nivel           173      ->      177
No Aplica              861      ->      826
```

DEIS estaba **unificando el glosario en vivo**, y la descarga cayó a mitad de la migración.
Las tres duplicidades de grafía desaparecieron, y 39 establecimientos pasaron de `No Aplica`
a `Segundo Nivel`, que es una corrección de contenido y no solo de escritura.

**Lo que esto valida.** El ingestor normaliza ambas grafías a una sola forma canónica antes
de filtrar. Con 1.996 filas cambiadas entre las dos descargas, la salida de
`componer_aps_comunal` fue **idéntica**: 344 comunas con APS pública y 20 sin ningún
establecimiento municipal, en ambos archivos. Solo se movió el conteo bruto de
establecimientos (2.714 → 2.719), por las diez altas reales.

Un ingestor que hubiera filtrado por `== "Primer Nivel"` habría contado 2.478 APS el lunes y
3.016 el martes, y esa diferencia del 22 % se habría leído como una expansión de la red.

**Decisión: esta fuente no lleva `sha256` en el catálogo.** No es una omisión: un archivo
regenerado en cada petición no tiene un hash estable, y fijarlo haría fallar toda ingesta
futura con un mensaje que culpa a una corrupción inexistente. Lo que se verifica en su lugar
es el **contrato de esquema** —columnas requeridas y glosas conocidas— y una glosa nueva
lanza `SchemaDriftError`. El campo `verificacion` del catálogo lo declara explícitamente,
para que la ausencia del hash no se lea como descuido.

**Lección:** la verificación de hash cumplió su función aunque el problema no fuera el que
esperaba detectar. Sirvió para **descubrir que la fuente es volátil**, que es información que
no teníamos y que cambia cómo hay que tratarla. Un chequeo que falla por un motivo distinto
al previsto sigue siendo un chequeo que sirvió; lo que no se puede hacer es apagarlo o
actualizar el hash sin mirar, que es la reacción natural y habría escondido el hallazgo.

### A-017 · política de supresión · 2026-07-29 {#a-017}

**Qué se observó:** escribiendo el test de la tabla de listas de espera se esperaba que un
cero sobreviviera a la supresión, y no sobrevivió. Con un grupo de valores `[3, 0, 900]` y
k=5, la salida suprime **el 3 y el 0**.

**Verificación: el código hace exactamente lo que dice la política.** La tensión está dentro
de `docs/06`, que afirma las dos cosas:

> «**El cero sí se publica.** "Cero muertes" no identifica a nadie y sí informa. Suprimir
> ceros sería confundir privacidad con opacidad.»

> «**Supresión complementaria.** Si en un grupo queda una sola celda suprimida y el total
> del grupo es conocido, la celda se reconstruye por resta. En ese caso se suprime además
> **la menor** de las celdas restantes.»

Cuando la menor de las celdas restantes **es** un cero, las dos reglas piden cosas opuestas.
`quality.suprimir_celdas_pequenas` implementa la segunda al pie de la letra.

**Las dos alternativas protegen igual.** Con el grupo `[3, 0, 900]` y total conocido 903:

| Se suprime | Visible | Lo que se deduce |
|---|---|---|
| 3 y 0 (hoy) | 900 | los dos suprimidos suman 3 — no se separan |
| 3 y 900 | 0 | los dos suprimidos suman 903 — no se separan |

Ninguna permite aislar la celda de riesgo. La diferencia es qué información se pierde: hoy
se pierde un cero —que es informativo y no identifica a nadie— y con la alternativa se
perdería el 900.

**Decisión: no se cambia acá.** `docs/09` es explícito en que la política de publicación se
modifica por decisión registrada y **no para resolver un caso puntual**, y esto apareció
justamente resolviendo un caso puntual. Además `docs/07` obliga a versión nueva del dataset
cuando cambia una metodología que altera series publicadas: la tabla de suicidio comunal
tiene 4.856 celdas suprimidas y algunas serían ceros.

Queda como **pregunta abierta para el comité**, con un test que fija la conducta actual
(`test_un_cero_puede_caer_como_complementaria_y_esta_documentado`) para que un cambio futuro
sea deliberado y no un efecto lateral de otra cosa.

**Lección:** el test se escribió esperando lo que la documentación prometía en su frase más
memorable, y falló contra lo que la misma documentación ordena tres párrafos después. Cuando
un test falla, la primera pregunta no es «¿qué le pasa al código?» sino «¿qué esperaba yo y
en qué me lo basé?». Acá la respuesta fue que dos reglas del mismo documento se contradicen
en un borde que nadie había pisado.

### A-018 · glosa06 · 2026-07-29 {#a-018}

**Qué se observó:** al parsear la tabla de especialidades del informe del I trimestre de
2026, la suma del detalle da **1.970.175** y el propio informe declara **1.981.653**.
Faltan 11.478 registros, un 0,58 %.

**Verificación:** el parser captura **todos los números presentes en el texto**, comprobado
línea por línea: lo único con cifra que queda fuera son el pie de página y la propia fila de
total. El informe del III trimestre de 2025, procesado con el mismo código, cuadra
**exacto**: 2.051.482 = 2.051.482, diferencia 0.

O sea que el hueco no es del parser. **La tabla de especialidades del informe de 2026 no
suma su propio total declarado.** No es truncamiento por umbral —la especialidad más chica
que lista tiene 28 registros y la de 2025 tenía 7— así que no se trata de un corte de cola.

**Por qué importa poco para psiquiatría y mucho para el resto.** Las dos especialidades de
salud mental están entre las mayores de la tabla y se publican con su cifra completa; la
serie que este proyecto necesita no está afectada. Lo que no se puede hacer con esta tabla
es **calcular participaciones**: un «psiquiatría es el X % de la lista de espera» computado
sobre un denominador que no cuadra consigo mismo es un número inventado con aspecto de dato.

**Decisión:** se declara y no se corrige. El reporte del parser trae `total_declarado`,
`suma_detalle` y `diferencia_con_total` en cada corrida, y sobre 0,5 % emite advertencia.
Repartir los 11.478 faltantes entre las especialidades listadas sería inventar.

**Lección: el ancla más barata es la que la fuente ya trae.** El total declarado de la
propia tabla no costó nada obtener y encontró dos cosas en una sesión: primero una fila que
el parser se inventaba —el pie de página emparejado con el número de página, exactamente
+27— y después un defecto del informe. Una fuente que publica su propio total está
ofreciendo una verificación gratis; no usarla es desperdiciarla.

### A-019 · rem_salud_mental · 2026-07-29 {#a-019}

**Qué se observó:** al construir I-05 se buscó dónde estaban ya publicados los conteos de
ideación e intento suicida, y resultó que **ya se publican**: `poblacion_control_salud_mental.csv`
los incluye desde el release `2026.07.1`, en 6.334 filas, como dos de sus setenta conceptos.

**Por qué es un problema.** `docs/06` impone obligaciones a **toda salida pública que
incluya suicidio**:

> - Nota metodológica (…)
> - Advertencia de interpretación (…)
> - **Enlace a recursos de ayuda vigentes en Chile, verificados en la fecha de publicación.**
> - **Revisión humana.** Ninguna publicación que incluya suicidio sale sin revisión de una
>   persona con competencia en salud mental.

La tabla publicada no cumple ninguna de las cuatro para estos conceptos. No porque alguien
las omitiera: **porque nadie notó que esa tabla contenía suicidio.** Entró como «población
bajo control en salud mental», que suena a actividad asistencial, y las dos filas sensibles
viajaron dentro sin activar ninguna revisión.

**El modo de fallo, que es el interesante.** La política estaba escrita, era clara y estaba
implementada en `cie10.es_publicable` y `quality.verificar_politica_publicacion` — pero esos
guardias miran **agrupadores CIE-10 y nombres de columna prohibidos**, y acá el suicidio no
entra por un código CIE-10 sino por una etiqueta de texto del formulario REM. El guardia
existía, era correcto, y no cubría esta puerta.

**Decisión:**

1. `gold.tabla_ideacion_intento` (I-05) exige `recursos_ayuda` en su firma y **se niega a
   producir la tabla sin ellos**, además de declarar la revisión clínica como pendiente. Es
   la única regla de `docs/06` que el proyecto hace cumplir por código y no por costumbre.
2. La tabla ya publicada **queda como está hasta la próxima versión del dataset**: retirarla
   sin reemplazo dejaría a quien la citó sin fuente, y `docs/07` obliga a mantener disponible
   la versión anterior. Lo que corresponde es publicar la versión nueva con las salvaguardas
   y declarar el cambio en el CHANGELOG.
3. **Pendiente para el comité:** decidir si `poblacion_control_salud_mental.csv` debe excluir
   estos dos conceptos y remitir a I-05, o incorporar las salvaguardas a la tabla completa.

**Lección: una política de publicación se hace cumplir sobre la puerta por la que el dato
entra, no sobre la que uno imaginó.** El proyecto vigilaba los códigos CIE-10 porque el
suicidio llegó primero por ahí, y el REM lo trajo por otro lado —una etiqueta de texto— sin
que ningún guardia mirara. Vale preguntarse, para cada regla implementada, por cuántas
puertas distintas puede entrar aquello que prohíbe.

### A-020 · dipres_ejecucion · 2026-07-29 {#a-020}

**Qué se observó:** al leer el diccionario de datos que DIPRES publica junto al CSV —después
de haber commiteado el hallazgo de Fase 4— apareció que los montos vienen **«expresados en
Miles»**. Las cifras absolutas que había publicado estaban mal por un factor de mil.

**Y al revisarlas aparecieron dos errores más, peores:**

| | Lo que publiqué | Lo correcto |
|---|---|---|
| Unidad | «MM$», sin corresponder a nada | miles de pesos en el origen |
| Denominador | 51.878 (ingresos + gastos) | 25,24 billones (solo gasto) |
| Identificable | 17 | 12,70 mil MM$ |
| Fracción | 0,03 % | **0,05 %** |

El denominador era el peor de los tres. En el presupuesto chileno los subtítulos 01-15 son
**ingresos** y los 21 en adelante **gastos**; sumarlos cuenta el mismo peso dos veces, una
al entrar y otra al salir. Daba 51,88 billones para medio año de Salud, que es más que todo
el presupuesto anual del Gobierno Central. **La cifra era absurda y la publiqué igual**,
porque venía expresada en una unidad que yo mismo había inventado y que no permitía
contrastarla contra nada conocido.

**El hallazgo sobrevive**, y esa es la parte incómoda: 0,03 % y 0,05 % sostienen la misma
conclusión, así que ninguna de las tres equivocaciones cambiaba el titular. Un error que no
mueve la conclusión es precisamente el que nadie revisa.

**Lo que lo destapó** fue leer el diccionario de datos **que la fuente publica en el mismo
directorio**, y que yo había bajado en la misma sesión sin abrir.

### Lecciones

1. **Una cifra absoluta hay que poder contrastarla con algo conocido.** «51.878 MM$» no se
   parecía a nada; «51,9 billones para medio año de Salud» se compara de inmediato con el
   presupuesto del país y se cae sola. Escribir la unidad correcta no es prolijidad: es lo
   que habilita la comprobación.
2. **Un ratio puede estar bien con numerador y denominador mal.** El 0,03 % era casi
   correcto por casualidad, y esa casualidad sostuvo tres errores.
3. **Leer el diccionario que la fuente publica cuesta dos minutos.** Es la tercera vez en
   este proyecto que la respuesta estaba en documentación de la propia fuente sin abrir —
   antes fueron los nombres de las variables de SINIM (A-015) y el manual del REM.

## Pendientes de verificación heredados del andamiaje

1. Contrastar los rangos CIE-10 de `cie10.py` contra la lista tabular oficial vigente.
2. Verificar los pesos de la población estándar OMS contra la publicación original.
3. ~~Confirmar el número oficial de comunas (`N_COMUNAS_ESPERADO`) contra la DPA vigente.~~
   **Resuelto 2026-07-27.** 346 comunas en 16 regiones, contra el maestro `CUT_2018_v04`
   de SUBDERE (fuente `subdere_cut`, sha256 `d1b7fc3a…`). `config/territorio_comunas.csv`
   quedó completo. Ver la anomalía «capas cartográficas con CUT obsoleto» más abajo.
4. Completar `config/territorio_comunas.csv` desde la fuente oficial.
5. Verificar todas las URLs del catálogo y promover estados.
