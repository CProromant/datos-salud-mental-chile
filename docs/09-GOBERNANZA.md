# 09 — Gobernanza

## El problema que resuelve

Un observatorio sin gobernanza produce cifras que nadie respalda y que, ante la primera
disputa pública, no tienen quién las defienda. Y un observatorio sin dueño institucional
muere cuando su desarrollador cambia de trabajo.

## Roles mínimos

| Rol | Responsabilidad | Poder de veto |
|---|---|---|
| **Coordinación** | Prioridades, relación institucional, releases | Sobre el alcance |
| **Ingeniería de datos** | Pipeline, calidad, infraestructura | Sobre publicar con reconciliación fallida |
| **Revisión epidemiológica** | Fichas de indicador, métodos, límites de interpretación | Sobre definiciones y sobre publicar un indicador mal especificado |
| **Revisión clínica en salud mental** | Todo lo que toque suicidio, niñez y poblaciones vulnerables | Sobre publicaciones sensibles |
| **Revisión jurídica** (puede ser externa y puntual) | Datos personales, licencias, redistribución | Antes de v1.0 |

Los roles pueden recaer en pocas personas, pero **los vetos no se acumulan en una sola**.
Quien construye el indicador no es quien aprueba su publicación.

## Cómo se decide

- **Cambios de código:** pull request, tests en verde, revisión de una persona distinta.
- **Cambios de definición de indicador:** ADR en `docs/adr/` con alternativas consideradas,
  más visto bueno de revisión epidemiológica.
- **Cambios en la política de publicación (`docs/06`):** decisión del comité completo,
  registrada. No se cambia para resolver un caso puntual.
- **Errata:** se publica. Nunca se corrige una serie en silencio.

## Dueño institucional

Requisito de la Fase 1, no del final. Candidatos naturales: un centro académico de salud
pública, una sociedad científica, la Defensoría de la Niñez, o un Servicio de Salud
dispuesto a usarlo internamente primero.

Lo que se le pide: alojar el proyecto o respaldarlo públicamente, aportar revisión
epidemiológica y clínica, y usar los datos en al menos un producto propio. Lo que no se le
pide: financiar infraestructura, porque la arquitectura está diseñada para no requerirla.

## Transparencia

Metodología, código, catálogo de fuentes y anomalías conocidas son públicos. Las decisiones
que afectan interpretación quedan en ADRs con fecha. La lista de quiebres de serie se
publica junto con los datos, no en un anexo que nadie abre.
