# Dataset: listas de espera por Servicio de Salud, Chile 2019–2025

Este documento acompaña a `listas_espera_servicio_salud.csv`. Léelo antes de usarlo:
**la unidad territorial NO es la comuna** y **la mediana de días no existe antes de 2022**.

- **Versión del dataset:** `2026.07.3` — el código que lo produjo es `v0.2.0`
- **Licencia:** CC BY-SA 4.0 — ver `LICENSE-DATA.md`. Permite uso comercial.
- **Cobertura:** 29 Servicios de Salud más el total nacional × 26 trimestres × 3 listas.
  2.340 filas.
- **Fuente:** visualizador de listas de espera del MINSAL (`listaesperasalud.cl`),
  Subsecretaría de Redes Asistenciales.

## Qué contiene

**Cuánta gente está esperando atención en el sistema público, por Servicio de Salud y
trimestre**, con cuánto lleva esperando.

Al 30 de junio de 2025, en todo Chile:

| Lista | Registros | Personas | Promedio | Mediana |
|---|---|---|---|---|
| Consulta nueva de especialidad (No GES) | **2.699.409** | 2.222.119 | 355 días | **264 días** |
| Intervención quirúrgica (No GES) | 412.596 | 362.373 | 414 días | 297 días |
| Garantías de oportunidad GES retrasadas | 78.374 | 76.477 | 148 días | 76 días |

Y la brecha territorial, que es lo que ningún informe publica junto:

| Servicio de Salud | Mediana de espera, consulta de especialidad |
|---|---|
| Metropolitano Norte | **437 días** |
| Tarapacá | 392 días |
| Antofagasta | 384 días |
| … | |
| Arica y Parinacota | 166 días |
| Aconcagua | **123 días** |

Un factor de 3,5 entre el mejor y el peor.

| Columna | Qué es |
|---|---|
| `servicio_clave` | Servicio de Salud, o `NACIONAL` para el total del país. |
| `periodo` | Trimestre en ISO: `2025-06` es el corte al 30 de junio. |
| `lista` / `lista_nombre` | `consulta`, `quirurgica` o `ges`, con su nombre legible. |
| `registros` | Interconsultas o garantías en espera. **Vacío si fue suprimido.** |
| `pacientes` | Personas distintas. **No es lo mismo que `registros`.** |
| `promedio_dias` / `mediana_dias` | Días de espera. Decimales legítimos. |
| `mediana_disponible` | `False` antes de 2022: la fuente no la calculaba. |
| `es_nacional` | `True` en la fila del total país. |
| `suprimido` | `True` si el conteo estaba entre 1 y 4. |
| `source_id`, `source_version`, `pipeline_version`, `fecha_calculo` | Procedencia. |

## Cómo leerlo sin equivocarse

### 1. La unidad es el Servicio de Salud, no la comuna

**No repartas estos valores entre las comunas de un Servicio.** La mediana de días describe
al Servicio completo; atribuirla a cada una de sus comunas es una inferencia ecológica y
produce un mapa que parece comunal sin serlo.

Y hay una razón más concreta: **cuatro comunas pertenecen a dos Servicios a la vez.**
Santiago tiene 18 establecimientos en Metropolitano Central y 5 en Occidente; Puente Alto
tiene 28 en Sur Oriente y 1 en Sur.

Si de todos modos necesitas bajar a comuna, `obsm.transform.silver.mapa_servicio_comuna`
construye la correspondencia desde el maestro de establecimientos de DEIS — pero es una
decisión que tomas tú, sabiendo lo anterior.

### 2. La mediana de días no existe antes de 2022

Cobertura por año: **0 % en 2019-2021, 50 % en 2022, 100 % desde 2023.** La fuente no la
calculaba. La columna `mediana_disponible` lo declara fila por fila.

Una tendencia de medianas que arranque en 2019 está comparando contra vacío. Para los años
anteriores hay `promedio_dias`, que sí existe desde 2019 pero **no es intercambiable**: el
promedio se va con la cola larga de quienes llevan años esperando.

### 3. «Registros» no es «personas»

Una persona puede tener varias interconsultas en espera al mismo tiempo. En junio de 2025
son 2.699.409 registros y 2.222.119 personas: **una diferencia de casi medio millón.**
Ambas columnas están y elegir mal infla la cifra un 21 %.

### 4. El reloj parte en la interconsulta, no en el síntoma

La espera se cuenta desde que un profesional emite la derivación. El tiempo que la persona
llevaba esperando conseguir esa consulta primera no está acá. **Subestima la espera vivida.**

### 5. Una baja puede ser depuración administrativa

Cuando un Servicio revisa su lista y da de baja registros duplicados, fallecidos o ya
atendidos fuera del sistema, la cifra baja sin que nadie se haya atendido más rápido. Los
informes trimestrales del MINSAL lo advierten y este dataset lo repite.

### 6. `registros` vacío no es cero

Es una celda suprimida: había entre 1 y 4 y publicar ese número podría identificarla. Son
**35 de 2.340 celdas (1,5 %)**, todas en garantías GES retrasadas. Doce de ellas son
supresiones **complementarias**: la fila nacional es exactamente la suma de los 29
servicios, así que suprimir una sola celda la dejaría reconstruible por resta.

> Nota: por la regla de `docs/06`, la complementaria es «la menor de las celdas restantes»,
> y cuando esa menor es un cero, el cero también se suprime. Es una tensión conocida de la
> política, registrada como [A-017](05-CALIDAD.md#a-017).

## Lo que este dataset NO es

**No tiene desglose por especialidad.** Estas cifras suman todas las especialidades. **No
se puede saber cuánto se espera por psiquiatría en una región**: el desglose por
especialidad solo lo publica el PDF de la Glosa 06, que a su vez no publica días de espera.
Las dos fuentes son complementarias y ninguna las cruza, aunque la letra b) de la propia
glosa obligue a hacerlo. Ver [I-06](04-INDICADORES.md#i-06--espera-en-psiquiatría-adulto-e-infanto-adolescente).

**No mide necesidad.** Mide demanda que llegó a registrarse. Un Servicio con lista corta
puede tener buena capacidad o puede tener gente que dejó de pedir hora.

**No es comparable con la lista de espera GES sin cuidado.** Las garantías GES retrasadas
son un universo distinto —incumplimientos de un plazo legal— y no se suman con las No GES.

## Cómo se construyó

El visualizador sirve un JSON por Servicio de Salud. El pipeline baja los 30, los junta,
verifica que los 29 servicios existan en el maestro de establecimientos de DEIS —**los 29
calzan**— y agrega procedencia y supresión.

**Se aborta si falla cualquiera de las 30 descargas.** La fila nacional es exactamente la
suma de los servicios; una serie incompleta produce un total que no cuadra con sus partes, y
eso no se ve roto, se ve como un dato.

Tres trampas de la fuente están documentadas en el ingestor: `promedio` y `mediana` son días
y traen decimales legítimos; el campo `servicio` es un slug y no el nombre de despliegue; y
el archivo de O'Higgins usa apóstrofo tipográfico U+2019, con el que responde 200 y sin el
que da 404.

## Cómo citarlo

```
Datos de Salud Mental de Chile (2026). Listas de espera por Servicio de Salud,
Chile 2019-2025, versión 2026.07.3. Licencia CC BY-SA 4.0.
Elaborado a partir del visualizador de listas de espera del Ministerio de Salud
de Chile, Subsecretaría de Redes Asistenciales.
https://github.com/CProromant/datos-salud-mental-chile
```

## Cómo reproducirlo

```bash
obsm espera        # descarga los 30 JSON, ingiere, normaliza y escribe gold
```

Un comando. Usa el archivo en caché si ya está; `--forzar-descarga` lo vuelve a bajar.

## Errores y contacto

Si un número no te cuadra, **repórtalo**: abre un issue con el Servicio, el trimestre y con
qué lo estás comparando.
