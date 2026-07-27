# 08 — Registro de riesgos

Probabilidad e impacto en escala baja/media/alta. Un riesgo sin dueño no es un riesgo
gestionado, es un riesgo anotado.

| # | Riesgo | Prob. | Impacto | Mitigación | Dueño |
|---|---|---|---|---|---|
| R-01 | **Nadie usa la herramienta.** El modo de muerte más probable | Alta | Alta | Dueño institucional comprometido en Fase 1, no al final; construir primero el indicador que alguien pidió | Coordinación |
| R-02 | Cambio de formato de una fuente rompe el pipeline en silencio | Alta | Media | Contrato de esquema con falla ruidosa; verificación semanal de URLs; test de reconciliación | Ingeniería |
| R-03 | Re-base de proyecciones de población tras el Censo 2024 mueve todas las tasas | Alta | Media | Denominador versionado y declarado en cada fila; recálculo completo, nunca parche | Ingeniería |
| R-04 | Los datos se usan para rankear y estigmatizar comunas | Media | Alta | Suavizado por defecto, publicación de incertidumbre, prohibición de formato ranking, notas de interpretación | Comité editorial |
| R-05 | Publicación que causa daño en materia de suicidio | Baja | Muy alta | Política de `docs/06` implementada en código; revisión clínica obligatoria; sin desglose por método | Revisor clínico |
| R-06 | Error metodológico publicado y citado | Media | Alta | Anclas de reconciliación; verificación manual por muestreo; versiones inmutables y erratas públicas | Revisor epidemiológico |
| R-07 | Problema legal por datos personales | Baja | Alta | Solo agregados públicos; sin datos identificables; revisión jurídica antes de v1.0 | Coordinación |
| R-08 | El proyecto depende de una sola persona | Alta | Alta | Documentación normativa, tests, `CLAUDE.md`; nada de conocimiento tácito | Coordinación |
| R-09 | Un organismo cierra el acceso a una fuente pública | Baja | Alta | Archivar cada corte descargado con su hash; solicitudes por Ley de Transparencia como respaldo | Coordinación |
| R-10 | Parser de PDF se rompe con cada rediseño del informe | Alta | Baja | Fixture por layout; el parser declara el layout detectado y falla si no reconoce ninguno | Ingeniería |
| R-11 | Interpretación política del observatorio como herramienta de un sector | Media | Media | Metodología abierta, código auditable, gobernanza plural, cero recomendaciones de política en las publicaciones de datos | Comité |
| R-12 | Costos de infraestructura insostenibles | Baja | Media | Archivos estáticos y DuckDB; sin servidores permanentes | Ingeniería |
