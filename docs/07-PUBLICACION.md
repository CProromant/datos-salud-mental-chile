# 07 — Publicación, versionado y licencias

## Versionado

**Datos:** `AAAA.MM.N` (año, mes, corte del mes). Un cambio de metodología que altera series
publicadas obliga a **nuevo número mayor y a mantener disponible la versión anterior**.
Reescribir en silencio una serie ya citada es inaceptable: rompe la trazabilidad de quien
citó la cifra.

**Código:** SemVer. `pipeline_version` viaja dentro de cada fila de `gold`.

## Qué se publica en cada release

1. `datos/` en parquet y CSV, un archivo por indicador.
2. `manifiesto.json` por archivo: fuentes, versiones, fecha de extracción, hashes.
3. `quiebres.csv`: discontinuidades de serie conocidas.
4. `reporte_calidad.md`: validaciones, reconciliaciones, anomalías abiertas.
5. `CHANGELOG.md`: qué cambió y si afecta series previas.
6. Notas metodológicas por indicador (extraídas de `docs/04`).

## Checklist de release

- [ ] `make test` y `make lint` en verde
- [ ] Todas las anclas de reconciliación pasan
- [ ] Checklist ético de `docs/06` completo
- [ ] Revisión clínica firmada si hay indicadores de suicidio
- [ ] Recursos de ayuda verificados en la fecha del release
- [ ] Comparación contra el release anterior: diferencias explicadas, no solo observadas
- [ ] CHANGELOG actualizado, incluyendo cambios metodológicos
- [ ] DOI generado y ficha de citación actualizada

## Licencias

- **Código:** MIT.
- **Datos derivados:** CC BY 4.0, sin cláusulas añadidas. Los usos que el proyecto rechaza
  están en `USO-ACEPTABLE.md` como **norma del proyecto, no como condición de licencia**:
  agregar restricciones a una licencia Creative Commons produce un texto que ya no es CC,
  que nadie sabe cumplir y que excluye al dataset de los estándares de datos abiertos que
  este mismo proyecto le exige al Estado. Donde la restricción sí es exigible es en el
  acceso controlado al detalle por método (acuerdo de uso firmado, ver ADR 0003).
- **Fuentes primarias:** conservan sus propias condiciones. Antes de redistribuir datos
  derivados hay que revisar los términos de cada portal; está en los pendientes de Fase 1.

## Citación

Formato sugerido, con DOI de Zenodo por release:

```
Observatorio de Salud Mental de Chile (AAAA). <Nombre del dataset>, versión AAAA.MM.N.
DOI: 10.xxxx/zenodo.xxxxxxx
```

Toda salida pública incluye la atribución a la fuente primaria correspondiente (DEIS, INE,
MINSAL, DIPRES, Superintendencia de Salud, según el caso).

## Estabilidad de la API de archivos

Las rutas de descarga son estables dentro de una versión mayor. Un cambio de nombre de
columna o de ruta es un cambio mayor. Quien construya algo encima necesita esa garantía,
y este proyecto existe justamente porque nadie se la da.
