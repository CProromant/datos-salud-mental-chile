# territorio_comunas.csv — DPA completa

Las **346 comunas** de Chile en 16 regiones. Esquema:
`comuna_cut,comuna_nombre,region_cut,provincia`, ordenado por `comuna_cut`.

## Procedencia

| campo | valor |
|---|---|
| fuente | `subdere_cut` en `config/sources.yml` |
| archivo | `CUT_2018_v04.xls` (SUBDERE) |
| `source_version` | CUT_2018_v04, vigente desde 2018-09-06 |
| sha256 | `d1b7fc3abb93cea3d115861579297d8bbdc9a7c762c958e646cd01b804df1ea0` |
| descargado | 2026-07-27 |

Este es el `source_version` de todo dato territorial derivado. El `.xls` vive en
`data/raw/dpa/` y **no se versiona** (ver `CLAUDE.md §2.3`); se recupera con la URL y el
hash de arriba.

## Controles que pasó

Aplicados sobre la fuente antes de escribir este archivo:

- 346 comunas, sin CUT duplicado.
- `comuna_cut[:2] == region_cut` en las 346 filas.
- Todos los CUT de 5 dígitos, como texto con ceros a la izquierda.
- 16 códigos de región distintos (`01`…`16`).
- Las 16 capitales regionales de la tabla semilla anterior coinciden exactamente.

`python -m obsm.cli territorio validar` vuelve a aplicar las reglas del proyecto y debe
seguir saliendo con código 0.

## Antes de reemplazar esta tabla por otra fuente

**Verifica que Chillán sea `16101`.** Si aparece como `8401`, la fuente arrastra la
codificación anterior a 2007 y hay que descartarla.

Es un control barato y atrapa un error caro. Las capas cartográficas que circulan bajo el
título «DPA» suelen traer los códigos previos a la creación de Los Ríos, Arica y Parinacota
y Ñuble, incluso cuando el recurso se publica con fecha reciente. Con un maestro así el join
contra DEIS o REM no falla: queda vacío, y 37 comunas aparecen con cero eventos. Ver la
anomalía A-001 en `docs/05-CALIDAD.md#anomalias`.

Los códigos son **texto**, nunca `int`: `05101` convertido a número es `5101` y rompe el
join (ver `CLAUDE.md §5`). Usa `obsm.territorio.formatear_cut_comuna` si dudas.
