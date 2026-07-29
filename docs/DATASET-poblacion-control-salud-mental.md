# Dataset: población en control de salud mental, Chile 2014–2025

Este documento acompaña a `poblacion_control_salud_mental.csv`. Léelo antes de usar el
archivo.

- **Versión del dataset:** `2026.07.1` — el código que lo produjo es `v0.2.0`
- **Licencia:** CC BY-SA 4.0 — ver `LICENSE-DATA.md`. Permite uso comercial.
- **Cobertura:** 345 comunas × 24 cortes semestrales (2014-06 a 2025-12) × 70 conceptos.
- **Fuente:** REM Serie P, sección P6 — DEIS/MINSAL.

## Qué contiene

**Cuántas personas están en control por cada diagnóstico de salud mental, en cada comuna.**
Es el dato que la mortalidad no puede dar: en 22 años de defunciones la depresión son once
muertes al año en todo Chile, porque casi nadie muere de depresión. Acá son más de cien mil
personas en tratamiento.

| Columna | Qué es |
|---|---|
| `comuna_cut` | Código Único Territorial, **5 dígitos como texto**. `01101` no es `1101`. |
| `periodo` | Corte semestral en ISO: `2023-06` o `2023-12`. |
| `etiqueta` | El diagnóstico o concepto, en la grafía más frecuente de la fuente. |
| `etiqueta_norm` | La misma etiqueta normalizada. **Úsala para filtrar y unir**, no la anterior. |
| `personas` | Personas en control. **Vacío si la celda fue suprimida.** |
| `suprimido` | `True` si el conteo estaba entre 1 y 4. |
| `source_id`, `source_version`, `pipeline_version`, `fecha_calculo` | Procedencia. |

## Cómo leerlo sin equivocarse

**Es un stock, no un flujo. No sumes los períodos.** «Personas en control» es una foto de
quién estaba en tratamiento en ese momento. Sumar junio con diciembre cuenta dos veces a
quien siguió en tratamiento todo el año.

**Filtra por `etiqueta_norm`, no por `etiqueta`.** La fuente escribe el mismo concepto con
distinta grafía según el año —`DEPRESIÓN MODERADA` y `Depresión moderada`— y hasta con
erratas propias. La columna normalizada resuelve eso; la otra es solo para leer.

**Dos filas del archivo no son diagnósticos, son totales del formulario:**
`NUMERO DE PERSONAS EN CONTROL EN EL PROGRAMA` y `PERSONAS CON DIAGNOSTICOS DE TRASTORNOS
MENTALES`. Si sumas todas las etiquetas, cuentas a la misma gente varias veces.

**`personas` vacío no es cero.** Es una celda suprimida: había entre 1 y 4 personas y
publicar ese número podría identificarlas en una comuna chica. Son **51.079 de 228.572
celdas**.

## Lo que este dataset NO es

**No es una cobertura.** Son conteos. Calcular un porcentaje contra la población comunal
del INE incluiría a quien se atiende en el sistema privado y daría un número que parece
cobertura y no lo es. El denominador correcto es la población **inscrita** en atención
primaria (FONASA), que este proyecto todavía no tiene verificada.

**No mide prevalencia.** Mide quién llegó al sistema público y quedó en control. Una comuna
con pocos casos puede tener poca enfermedad o poca capacidad de atención, y estos datos no
distinguen entre las dos.

**No permite comparar comunas sin cuidado.** Sin denominador, una comuna grande siempre
tendrá más personas en control que una chica.

## Cambios de definición en la serie

La fuente cambió qué mide, y hay que saberlo antes de leer una tendencia:

| Cuándo | Qué cambió |
|---|---|
| 2019–2020 | Los **trastornos de ansiedad** pasaron de un concepto único a un desglose de seis (generalizada, pánico, fobias sociales, estrés postraumático, otros). Comparar el antes con el después exige sumar los nuevos. |
| desde 2020 | Aparecen **ideación e intento suicida** como conceptos. Antes no se registraban acá. |
| desde 2022 | Aparece **autismo**. |

Además, la serie **no puede empezar antes de 2014**: los diccionarios de códigos de 2009 y
2012 están protegidos con contraseña y el de 2013 no trae la sección. Sin diccionario, las
columnas del archivo de origen no tienen significado.

## Serie nacional, para contrastar

Corte de diciembre, celdas publicables:

| Año | En el programa | Depresión moderada | Ansiedad |
|---|---|---|---|
| 2014 | 756.956 | 140.320 | 191.940 |
| 2018 | 857.085 | 123.715 | 257.266 |
| 2021 | 876.847 | 113.049 | 250.951 |
| 2025 | **1.048.618** | 108.496 | 257.391 |

Si tus cifras no se parecen a estas, algo se rompió en el camino.

## Cómo se construyó

El archivo de origen trae columnas **genéricas** —`Col01` a `Col38`— cuyo significado
depende del código de la fila y del año. El mapeo vive en `config/rem_secciones.yml`,
generado desde los diccionarios oficiales con `obsm rem mapear`, y es lo que convierte un
número anónimo en «personas con depresión moderada, mujeres de 20 a 24 años».

Tres defectos encontrados y corregidos al construir esta serie están documentados en
`docs/05-CALIDAD.md` como A-010, A-011 y A-012. Los tres eran invisibles procesando un solo
año.

## Cómo citarlo

```
Datos de Salud Mental de Chile (2026). Población en control de salud mental,
Chile 2014-2025, versión 2026.07.1. Licencia CC BY-SA 4.0.
Elaborado a partir del REM del Departamento de Estadísticas e Información
de Salud (DEIS), Ministerio de Salud de Chile.
https://github.com/CProromant/datos-salud-mental-chile
```

## Cómo reproducirlo

```bash
obsm rem mapear      # regenera el mapeo desde los diccionarios oficiales
obsm rem ingerir     # descarga y procesa los doce años (~35 min)
obsm rem gold        # arma esta tabla
```

## Errores y contacto

Si un número no te cuadra, **repórtalo**: abre un issue con la comuna, el período y con qué
lo estás comparando. Los tres defectos que se corrigieron en esta serie salieron de mirar
con desconfianza resultados que parecían correctos.
