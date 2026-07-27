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

## Quiebres de serie

Una tabla `quiebres` acompaña a todo dataset publicado: fecha, fuente, descripción y efecto
esperado. Ejemplos que ya se anticipan:

| Fecha | Fuente | Quiebre | Efecto |
|---|---|---|---|
| 1997-1998 | defunciones | paso de CIE-9 a CIE-10 | comparabilidad limitada hacia atrás |
| 2018 | todas | creación de la región de Ñuble | series regionales de Biobío y Ñuble no comparables sin recodificar |
| variable | REM | cambio de manual y renumeración de secciones | discontinuidades que no son epidemiológicas |
| pendiente | población | re-base de proyecciones tras el Censo 2024 | todas las tasas cambian retroactivamente |
| variable | Glosa 06 | cambios de criterio de depuración de la lista | saltos de nivel sin cambio de acceso |

## Anomalías {#anomalias}

Registro vivo. **Una anomalía no se corrige hasta estar explicada.** Muchas son reales: un
CESFAM que dejó de reportar tres meses es un dato sobre el sistema, y borrarlo falsifica el
diagnóstico.

Formato de entrada:

```
### A-001 · <fuente> · <fecha de detección>
Qué se observó:
Reproducción: (comando)
Hipótesis:
Verificación:
Decisión: [conservar | marcar | excluir con nota]
```

### A-001 · capas cartográficas de comunas · 2026-07-27

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



### A-002 · deis_defunciones · 2026-07-27

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

### A-004 · deis_defunciones · 2026-07-27

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

### A-003 · deis_defunciones · 2026-07-27

**Qué se observó:** `COD_COMUNA` trae 4 caracteres en 1.551.470 filas y 5 en 1.630.976.

**Verificación:** las de 4 corresponden a las regiones 01–09, que perdieron el cero a la
izquierda (`8304` por `08304`, Laja). Es el problema que `CLAUDE.md §5` anticipa.

**Decisión:** conservar tal cual en `bronze`; `silver` está obligado a pasarlo por
`territorio.formatear_cut_comuna`. Hay un test que verifica que el problema siga presente
en el fixture, para que nadie «arregle» la fuente por el lado equivocado.

### A-005 · reconciliación · 2026-07-27

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

### A-006 · deis_defunciones · 2026-07-27

**Qué se observó:** al ingerir el archivo real (869 MB) el proceso no llegaba a arrancar.

**Verificación:** `detectar_encoding` declara `muestra_bytes: int = 200_000` pero hacía
`ruta.read_bytes()[:muestra_bytes]`: cargaba el archivo completo y recién después recortaba.
`leer_texto` cargaba otra copia entera, y el ingestor solo usaba de ella la primera línea.
Entre ambas, ~1,7 GB antes de que pandas empezara.

**Decisión:** `detectar_encoding` lee solo la muestra; se agrega `leer_primera_linea` para
los ingestores. Corrida completa: 3.182.446 filas en 11 min 12 s.

**Lección:** ningún fixture de 15 filas puede exponer esto. Hay defectos que solo existen a
escala real, y por eso la ingesta contra la fuente real es parte de verificar, no un extra.

### A-007 · deis_defunciones · 2026-07-27

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

**Lección:** un indicador de calidad que sale perfecto a la primera hay que auditarlo antes
que celebrarlo. Acá el `0` no medía lo que su nombre decía que medía.

### A-008 · ine_proyecciones · 2026-07-27

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

### A-009 · ine_proyecciones · 2026-07-27

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

## Pendientes de verificación heredados del andamiaje

1. Contrastar los rangos CIE-10 de `cie10.py` contra la lista tabular oficial vigente.
2. Verificar los pesos de la población estándar OMS contra la publicación original.
3. ~~Confirmar el número oficial de comunas (`N_COMUNAS_ESPERADO`) contra la DPA vigente.~~
   **Resuelto 2026-07-27.** 346 comunas en 16 regiones, contra el maestro `CUT_2018_v04`
   de SUBDERE (fuente `subdere_cut`, sha256 `d1b7fc3a…`). `config/territorio_comunas.csv`
   quedó completo. Ver la anomalía «capas cartográficas con CUT obsoleto» más abajo.
4. Completar `config/territorio_comunas.csv` desde la fuente oficial.
5. Verificar todas las URLs del catálogo y promover estados.
