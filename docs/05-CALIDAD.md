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

## Pendientes de verificación heredados del andamiaje

1. Contrastar los rangos CIE-10 de `cie10.py` contra la lista tabular oficial vigente.
2. Verificar los pesos de la población estándar OMS contra la publicación original.
3. ~~Confirmar el número oficial de comunas (`N_COMUNAS_ESPERADO`) contra la DPA vigente.~~
   **Resuelto 2026-07-27.** 346 comunas en 16 regiones, contra el maestro `CUT_2018_v04`
   de SUBDERE (fuente `subdere_cut`, sha256 `d1b7fc3a…`). `config/territorio_comunas.csv`
   quedó completo. Ver la anomalía «capas cartográficas con CUT obsoleto» más abajo.
4. Completar `config/territorio_comunas.csv` desde la fuente oficial.
5. Verificar todas las URLs del catálogo y promover estados.
