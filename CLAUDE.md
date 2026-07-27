# CLAUDE.md — Instrucciones operativas del repositorio

> Este archivo lo lee Claude Code al inicio de cada sesión. Es normativo, no descriptivo:
> lo que dice acá manda por sobre lo que parezca razonable en el momento.
> Si una instrucción de este archivo entra en conflicto con una petición del usuario,
> señálalo explícitamente antes de proceder.

## 1. Qué es este proyecto

`obsm` (Observatorio de Salud Mental de Chile) es un **motor de datos**, no una aplicación
clínica. Toma fuentes públicas dispersas (DEIS, REM, DIPRES, Glosa 06, Superintendencia,
INE, SENDA), las normaliza a un esquema territorial y temporal único, calcula indicadores
derivados que hoy nadie publica, y expone datasets versionados y trazables.

**Nunca** toca datos identificables de pacientes. **Nunca** entrega orientación clínica.
Si una tarea empuja en esa dirección, deténte y dilo.

Lectura obligatoria antes de tocar código nuevo:
- `docs/00-PROBLEMA.md` — para qué existe y quién lo usa
- `docs/02-ARQUITECTURA.md` — el flujo raw → bronze → silver → gold
- `docs/06-ETICA-Y-DATOS.md` — límites legales y de publicación (no negociables)

## 2. Los siete no negociables

1. **No inventes URLs, códigos ni nombres de columna.** Si no verificaste una URL en esta
   sesión (con `curl -I` o descarga real), no la escribas en `config/sources.yml` como si
   existiera. Márcala `estado: no_verificada` y déjala en la sección de pendientes.
   Una URL inventada es peor que una URL faltante: contamina el catálogo con confianza falsa.
2. **Todo número publicado tiene procedencia.** Cada fila de `gold` arrastra `source_id`,
   `source_version`, `fecha_extraccion` y `pipeline_version`. Si un cálculo no puede
   arrastrarlos, no va a `gold`.
3. **No se versiona data cruda.** `data/` está en `.gitignore` completo salvo
   `data/.gitkeep`. Los fixtures de test son sintéticos y viven en `tests/fixtures/`.
4. **Prohibido publicar desagregación por método de suicidio.** Ver `docs/06`. Esto incluye
   subcódigos X60–X84 individuales, columnas de "mecanismo" y cualquier cruce que permita
   reconstruirlos. El agregador `SUICIDIO` es la única salida pública.
5. **Supresión por umbral k.** Ninguna celda pública con conteo `1..k-1` (k por defecto = 10
   para mortalidad comunal). Se suprime la celda *y* sus complementarias para evitar
   reconstrucción por resta. Función única: `obsm.quality.suprimir_celdas_pequenas`.
6. **Los años preliminares se marcan.** DEIS declara preliminares los últimos dos años de
   defunciones. Toda serie que los incluya lleva `preliminar=True` y ningún indicador de
   tendencia los usa como punto final sin advertencia.
7. **Cambios de esquema fallan ruidosamente.** Si una fuente cambia columnas, el ingestor
   debe lanzar `SchemaDriftError`, no adaptarse en silencio. Adaptarse en silencio es cómo
   se publican series rotas.

## 3. Mapa del repositorio

```
config/sources.yml        Catálogo de fuentes, legible por máquina. Fuente de verdad.
config/indicators.yml     Definiciones de indicadores (fórmula, denominador, umbrales).
src/obsm/
  registry.py             Carga y valida sources.yml
  io.py                   Descarga con caché, hash SHA-256, manifiesto de extracción
  territorio.py           Normalización de comunas/regiones (CUT). El corazón del proyecto.
  cie10.py                Agrupadores CIE-10 de salud mental y lesiones autoinfligidas
  quality.py              Reglas de validación, reconciliación y supresión
  ingest/                 Un módulo por fuente. Escriben bronze. Nada de lógica de negocio.
  transform/              bronze → silver (normalizado) → gold (indicadores)
  indicators/             Tasas, estandarización directa, suavizado bayesiano empírico
  cli.py                  Interfaz `obsm ...`
tests/                    pytest. Los tests de territorio y cie10 son de regresión: no se relajan.
docs/                     Documentación normativa (ver índice en README)
```

## 4. Comandos

```bash
make setup           # entorno + deps
make test            # pytest -q (debe pasar antes de cualquier commit)
make lint            # ruff + mypy en src/
obsm sources list    # catálogo de fuentes y su estado
obsm sources verify  # HEAD a cada URL; reporta 404 / cambios de Content-Length
obsm ingest <id>     # descarga y escribe bronze/<id>/
obsm build silver    # normaliza bronze → silver
obsm build gold      # calcula indicadores → gold + manifiesto
obsm qa              # corre todas las validaciones y reconciliaciones
```

**Sí hay red hacia dominios de gobierno de Chile**, pero con dos condiciones que hay que
poner explícitamente o todo falla con errores que parecen de conectividad:

```bash
curl --ssl-no-revoke -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..." -o destino URL
```

- `--ssl-no-revoke`: sin esto sale `CRYPT_E_NO_REVOCATION_CHECK`. **No es interceptación de
  TLS ni un certificado inválido**: es que no se alcanza el servidor de revocación. Nunca
  lo confundas con un bloqueo de red ni lo «arregles» desactivando la verificación del
  certificado. Para `git`, el equivalente es `http.sslBackend=schannel` +
  `http.schannelCheckRevoke=false`.
- User-agent de navegador: varios servidores (SUBDERE, `repositoriodeis.minsal.cl`)
  responden `403` sin él. Algunos además responden `404` a `HEAD` aunque el `GET` funcione:
  verifica con `-r 0-3` y mirando los magic bytes, no con `HEAD`.

**Desde Python el problema es OTRO y hay que no confundirlos** (verificado 2026-07-27).
`requests` contra `repositoriodeis.minsal.cl` falla con:

```
SSLError: CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate
```

No es revocación: **el servidor sirve una cadena de certificados incompleta**, sin la CA
intermedia. `curl` en Windows usa schannel y la resuelve solo; `requests` usa el bundle de
`certifi` y no puede. La solución es `truststore`, que delega la validación al almacén del
sistema operativo —lo mismo que hace el navegador con el que un humano bajaría el archivo—:

```python
import truststore; truststore.inject_into_ssl()
```

Ya está cableado en `obsm.io.descargar`, junto con el user-agent de navegador. **Nunca**
`verify=False`: eso aceptaría cualquier certificado, incluido el de un atacante, y es una
respuesta distinta a un problema distinto.

Corolario: **verifica las URLs de verdad antes de decir que no se puede.** Esta sección
afirmaba lo contrario hasta el 2026-07-27 y estaba equivocada; el costo de creerle fue
pedirle al usuario descargas que la sesión podía hacer sola. La segunda lección, del mismo
día: dos herramientas pueden fallar contra el mismo servidor por causas distintas, y
aplicar el arreglo de una a la otra no funciona.

Lo que sigue vigente sin excepción: **no simules una descarga exitosa que no ocurrió**, y
no escribas en `sources.yml` una URL que no comprobaste en esta sesión.

## 5. Convenciones de datos

- **Territorio:** clave canónica `comuna_cut` (5 dígitos, string con ceros a la izquierda,
  ej. `"05101"`), `region_cut` (2 dígitos). Nunca uses el nombre de comuna como llave.
  Nunca uses `int` para códigos: `05101` se convierte en `5101` y arruina el join.
- **Tiempo:** `periodo` en ISO. Mensual `YYYY-MM`, anual `YYYY`. Nada de "ene-24".
- **Ñuble:** región 16, creada en 2018. Series históricas de sus 21 comunas aparecen bajo
  región 08 (Biobío) antes de 2018. `territorio.py` resuelve esto con vigencias; nunca lo
  parches a mano en un ingestor.
- **Encoding:** los archivos del sector público chileno mezclan UTF-8, Latin-1 y CP1252.
  Usa `obsm.io.leer_texto` que detecta y registra el encoding en el manifiesto.
  Si ves `Ã±` o `Bio Bio` con caracteres rotos, es encoding, no un nombre distinto.
- **Decimales:** coma decimal y punto de miles son habituales. `obsm.io.a_numero`.
- **Población:** denominadores desde proyecciones INE. Un cambio de base (Censo 2024) cambia
  todas las tasas retroactivamente; por eso el denominador lleva su propio `source_version`.
- **Moneda:** todo monto se guarda nominal y se deriva real con deflactor IPC en `gold`.
  Nunca guardes solo el valor real.

## 6. Convenciones de código

- Python 3.11+, tipado. `pandas` para transformación, `duckdb` para el almacén, `parquet`
  como formato de silver/gold. Sin ORM, sin framework web en esta fase.
- Funciones puras en `transform/` e `indicators/`: entra DataFrame, sale DataFrame, sin I/O.
  El I/O vive en `io.py` y en los ingestores. Esto es lo que hace testeable el proyecto.
- Errores del dominio en `obsm.errors`: `SourceUnavailableError`, `SchemaDriftError`,
  `ReconciliationError`, `SuppressionViolationError`. No uses `Exception` genérica.
- Logging estructurado con `logging`, nunca `print` fuera de `cli.py`.
- Docstrings en español, con la unidad y el denominador cuando corresponda.

## 7. Flujo por tipo de tarea

**Agregar una fuente**
1. Ficha en `docs/01-FUENTES.md` (qué contiene, granularidad, latencia, formato, trampas).
2. Entrada en `config/sources.yml` con `estado: no_verificada`.
3. Verificar URL realmente; recién ahí `estado: verificada` + `fecha_verificacion`.
4. Fixture sintético representativo en `tests/fixtures/<id>/` (incluyendo el caso feo:
   tildes, celdas combinadas, totales intercalados, comuna con nombre alternativo).
5. Ingestor en `src/obsm/ingest/<id>.py` con contrato de esquema declarado.
6. Test de esquema + test de reconciliación contra un total oficial conocido.
7. Documentar en `docs/05-CALIDAD.md` qué total se usa como ancla.

**Agregar un indicador**
1. Ficha en `docs/04-INDICADORES.md`: definición, numerador, denominador, fuente, unidad,
   limitaciones y **qué NO significa** (esta sección es obligatoria).
2. Entrada en `config/indicators.yml`.
3. Implementación pura en `indicators/`.
4. Test con caso calculado a mano (no con el output del propio código).
5. Revisión ética si toca suicidio, niñez o poblaciones pequeñas.

**Arreglar un dato que "se ve raro"**
No lo arregles. Primero reproduce, luego documenta la anomalía en
`docs/05-CALIDAD.md#anomalias`, luego decide. Muchas anomalías del REM son reales
(un CESFAM que dejó de reportar) y borrarlas es falsificar el diagnóstico.

## 8. Trampas conocidas (leer antes de depurar tres horas)

- Nombres de comuna con más de una grafía oficial: Coyhaique/Coihaique, Aysén/Aisén,
  Tiltil/Til Til, Llay-Llay/Llaillay, Paihuano/Paiguano, Marchihue/Marchigüe,
  Treguaco/Trehuaco, Alto Biobío/Alto Bío Bío, O'Higgins con y sin apóstrofo,
  Til Til con y sin espacio. Todas resueltas en `territorio.ALIAS`; si aparece una nueva,
  se agrega ahí **con test**, nunca inline.
- Comunas con nombre repetido en distintas regiones (ej. Los Álamos vs. Los Ángeles no,
  pero sí San Pedro / San Juan / Corral en textos abreviados): sin región, un nombre puede
  ser ambiguo. `normalizar_comuna` exige región cuando el nombre es ambiguo.
- Filas de total ("TOTAL PAÍS", "Total Servicio") mezcladas con filas de detalle: si no las
  eliminas, duplicas todo el país. Hay un check para esto en `quality.py`.
- Glosa 06 llega en PDF trimestral, no en CSV. El parser es frágil por diseño: si el layout
  cambia, debe fallar, no adivinar.
- El REM cambia de manual cada 1–2 años y las secciones se renumeran. El ingestor toma la
  sección por *nombre normalizado*, no por número, y valida contra el manual del año.
- Un establecimiento puede cambiar de código DEIS o de dependencia entre años; los saltos
  bruscos en series comunales suelen ser eso.

## 9. Definición de "listo"

Una tarea está lista cuando: `make test` pasa; hay un test que falla si el bug vuelve;
la documentación correspondiente está actualizada en el mismo commit; y el diff no incluye
datos descargados. Si no puedes verificar algo, dilo en el commit y en la respuesta, en vez
de dejarlo implícito.

## 10. Cómo responder en sesión

- Distingue siempre **verificado** de **supuesto**. Marca los supuestos como tales.
- Si una fuente no se pudo descargar, dilo primero, no al final.
- No propongas "y además podríamos hacer un dashboard". El alcance está en `PLAN.md`;
  los cambios de alcance se discuten, no se implementan de sorpresa.
- Prefiere un ingestor que funcione y esté probado a cinco stubs.
