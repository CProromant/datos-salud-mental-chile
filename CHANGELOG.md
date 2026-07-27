# CHANGELOG

Formato: [Keep a Changelog]. Versionado de datos `AAAA.MM.N`, de código SemVer.
Un cambio metodológico que altere series ya publicadas exige versión mayor y mantener
disponible la versión anterior.

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
