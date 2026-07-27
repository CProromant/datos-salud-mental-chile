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

*(Sin entradas todavía: no se ha ingerido ninguna fuente real.)*

## Pendientes de verificación heredados del andamiaje

1. Contrastar los rangos CIE-10 de `cie10.py` contra la lista tabular oficial vigente.
2. Verificar los pesos de la población estándar OMS contra la publicación original.
3. Confirmar el número oficial de comunas (`N_COMUNAS_ESPERADO`) contra la DPA vigente.
4. Completar `config/territorio_comunas.csv` desde la fuente oficial.
5. Verificar todas las URLs del catálogo y promover estados.
