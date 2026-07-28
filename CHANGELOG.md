# CHANGELOG

Formato: [Keep a Changelog]. Versionado de datos `AAAA.MM.N`, de código SemVer.
Un cambio metodológico que altere series ya publicadas exige versión mayor y mantener
disponible la versión anterior.

## [0.2.0] — 2026-07-27 — Primera serie publicable (Fase 1)

Primer release con datos. La serie es la **tasa comunal de mortalidad por suicidio,
Chile 2002-2023** (dataset `2026.07.1`): 346 comunas x 22 años, con tasa cruda,
estandarizada por edad, suavizada por Bayes empírico y años de vida potencial perdidos.

### Verificado contra fuentes externas
- Defunciones totales 2023 = 122.218 y 2020 = 126.169: **exacto** contra el Anuario de
  Estadísticas Vitales del INE.
- Población nacional 2020 y 2023: **exacto** contra las proyecciones del INE.
- Tasa nacional de suicidio 2015-2023 entre 8,0 y 10,6 por 100.000, dentro del rango
  publicado para Chile. AVPP de 38,8 años por muerte.
- Conservación de casos: 46.810 = 40.730 dentro de la ventana + 6.080 declarados fuera.

### Agregado
- `obsm run`: el pipeline completo en un comando. Descarga, verifica hashes, descomprime,
  ingiere, normaliza, reconcilia y escribe gold. Se detiene en el primer error.
- Ingestor `ine_proyecciones` y normalización del denominador en silver.
- Reconciliación **automática** contra `config/anclas.yml`: cinco anclas con procedencia,
  evaluadas antes de publicar. Si una no cuadra, no se escribe nada.
- Tasa estandarizada por edad con IC 95 % y AVPP en gold, con supresión extendida a todas
  las columnas derivadas.
- `ejemplos/practica.py`: ocho secciones ejecutables para aprender la herramienta.
- Ficha del dataset en `docs/DATASET-suicidio-comunal.md`.

### Corregido
- Nueve anomalías documentadas en `docs/05-CALIDAD.md`. Cinco eran defectos que **no
  lanzaban excepción** y habrían publicado números plausibles y falsos: cero suicidios en
  27 años por leer la columna de diagnóstico equivocada (A-004), una comuna inventada por
  validar el formato del CUT y no su existencia (A-007), doce años futuros con tasa cero,
  y el desglose por método —prohibido en docs/06— autorizado por un error de tipeo en
  `es_publicable`.
- La descarga no funcionaba contra las fuentes reales: user-agent rechazado con 403 y
  cadena de certificados incompleta. Resuelto con user-agent de navegador y `truststore`.
- `source_version` y `poblacion_version` iban en null en las 7.612 filas.

### Licencias
- Se investigaron DEIS y SUBDERE: **ninguna declara licencia** para el archivo que se usa.
  Se evaluó publicar bajo CC BY-NC-SA y no es legalmente posible —la cláusula 3(b) de
  CC BY-SA 4.0 del INE exige los mismos elementos de licencia—. Se mantiene CC BY-SA 4.0
  y la postura sobre uso comercial queda como norma en `USO-ACEPTABLE.md`.

### Métricas
- 337 tests. 4 de 17 fuentes verificadas con descarga real. 2 indicadores activos.

## [0.1.0] — 2026-07-26 — Andamiaje (Fase 0)

### Agregado
- Estructura del proyecto, documentación normativa (`docs/00` a `docs/09`), ADRs y
  playbook de sesiones.
- `territorio`: normalización de nombres de comuna con alias observados, códigos CUT como
  texto, vigencias regionales (caso Ñuble), tabla DPA semilla con validación de completitud.
- `cie10`: agrupadores de salud mental, suicidio, intención indeterminada, consumo,
  demencias, con política de publicación embebida.
- `quality`: supresión por umbral k con supresión complementaria, detección de filas de
  total, reconciliación contra anclas, validaciones estructurales.
- `indicators.tasas`: tasa cruda, estandarización directa (estándar OMS), suavizado
  bayesiano empírico Poisson-Gamma, AVPP, SMR.
- `ingest`: contrato base con falla ruidosa ante cambio de esquema; ingestor de defunciones
  DEIS funcional contra fixture.
- `transform`: silver (territorio, edad, clasificación) y gold (denominadores, tasas,
  supresión, procedencia).
- CLI: `sources list/verify/show`, `territorio validar/resolver`, `ingest`, `build
  silver/gold`, `qa`.
- 174 tests; CI con tests, lint y verificación de que no se versionen datos.

### Licencias
- Código MIT; datos derivados CC BY-SA 4.0; normas de uso en `USO-ACEPTABLE.md`, separadas
  de la licencia a propósito.
- La licencia de datos pasó de CC BY 4.0 a CC BY-SA 4.0 el 2026-07-27 (`docs/adr/0005`):
  el INE publica el denominador de toda tasa bajo CC BY-SA 4.0 y su CompartirIgual obliga
  al derivado. Sigue permitiendo uso comercial.

### Decisiones registradas
- ADR 0001: stack mínimo (Parquet + DuckDB + estático).
- ADR 0002: marco territorial vigente como principal.
- ADR 0003: publicación de suicidio por agrupador, nunca por método.

### Conocido y pendiente
- **Ninguna fuente verificada todavía.** Todas las URLs del catálogo están marcadas
  `no_verificada` y el pipeline de producción está bloqueado por diseño.
- Tabla DPA incompleta (16 de 346 comunas): completar desde la fuente oficial.
- Rangos CIE-10 y pesos de la población estándar pendientes de contraste con las
  publicaciones originales.
