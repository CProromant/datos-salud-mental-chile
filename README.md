# Datos de Salud Mental de Chile (`obsm`)

> Infraestructura de datos abierta sobre salud mental en Chile. Proyecto independiente:
> no representa ni cuenta con el respaldo de ningún organismo del Estado.

Infraestructura de datos abierta que consolida, normaliza y publica indicadores de salud
mental de Chile a nivel comunal y mensual, a partir de fuentes públicas hoy dispersas,
inconsistentes entre años y en buena parte atrapadas en PDF.

**El problema que ataca:** Chile no tiene una línea base utilizable de salud mental. Sin
ella no hay evaluación posible de política pública, y las decisiones de presupuesto,
brechas y priorización se toman con anécdota o con cifras de hace una década. Ver
`docs/00-PROBLEMA.md`.

**Lo que NO es:** no es una app clínica, no hace triage, no procesa datos de pacientes
identificables, no reemplaza el juicio profesional.

## Qué produce

| Salida | Formato | Frecuencia |
|---|---|---|
| Datasets normalizados (comuna × período × indicador) | Parquet + CSV, versionados | mensual |
| API de solo lectura sobre el almacén | DuckDB / archivos estáticos | mensual |
| Manifiesto de procedencia por dataset | JSON | cada corrida |
| Reporte de calidad y anomalías | Markdown | cada corrida |
| Alertas de desviación de series | JSON + issue automático | semanal |

## Quickstart

```bash
make setup
make test
obsm sources list          # ver catálogo y estado de verificación
obsm sources verify        # comprobar que las URLs siguen vivas (requiere red)
obsm ingest deis_defunciones
obsm build silver && obsm build gold
obsm qa
```

En entornos sin acceso a dominios `.cl` de gobierno, todo lo anterior corre igual contra
los fixtures sintéticos de `tests/fixtures/`.

## Índice de documentación

| Documento | Contenido |
|---|---|
| `PLAN.md` | Fases, hitos, criterios de término, orden de ataque |
| `CLAUDE.md` | Instrucciones operativas para trabajo asistido con Claude Code |
| `docs/00-PROBLEMA.md` | Teoría de cambio, usuarios, qué se decide con esto |
| `docs/01-FUENTES.md` | Catálogo de fuentes con fichas detalladas y trampas conocidas |
| `docs/02-ARQUITECTURA.md` | Capas raw/bronze/silver/gold, contratos, almacén |
| `docs/03-DICCIONARIO.md` | Esquema canónico y diccionario de variables |
| `docs/04-INDICADORES.md` | Fichas de indicador: fórmula, límites, qué NO significan |
| `docs/05-CALIDAD.md` | Reglas de validación, anclas de reconciliación, anomalías |
| `docs/06-ETICA-Y-DATOS.md` | Ley 21.719, secreto estadístico, publicación segura de suicidio |
| `docs/07-PUBLICACION.md` | Versionado, licencias, releases, citación |
| `docs/08-RIESGOS.md` | Registro de riesgos con mitigación y dueño |
| `docs/09-GOBERNANZA.md` | Dueño institucional, comité, cómo se aprueban cambios |
| `docs/PROMPTS.md` | Playbook de sesiones con Claude Code |
| `docs/adr/` | Decisiones de arquitectura y licenciamiento con su justificación |

## Estado

Fase 0 (andamiaje). Ninguna fuente está verificada en producción todavía: el catálogo
distingue explícitamente entre fuentes verificadas y no verificadas, y el código se niega
a tratar una URL no verificada como si lo estuviera.

## Licencia

- **Código:** MIT (`LICENSE`).
- **Datos derivados:** CC BY-SA 4.0 (`LICENSE-DATA.md`), con atribución al proyecto y a
  la fuente primaria correspondiente. El CompartirIgual es heredado: el INE publica bajo
  esa licencia el denominador de toda tasa (ver `docs/adr/0005`). Permite uso comercial.
- **Normas de uso:** `USO-ACEPTABLE.md`. Son normas del proyecto, no cláusulas de licencia,
  y el documento explica por qué esa distinción es deliberada.
- Las fuentes primarias conservan sus propias condiciones de uso.
