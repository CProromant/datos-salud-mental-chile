# ADR 0005 — Los datos derivados pasan a CC BY-SA 4.0 por herencia del INE

- Fecha: 2026-07-27
- Estado: aceptada
- Supersede: la parte de datos de [ADR 0004](0004-licencias.md). La licencia del código
  (MIT) y la separación entre licencia y `USO-ACEPTABLE.md` siguen vigentes sin cambios.

## Contexto

ADR 0004 eligió CC BY 4.0 para los datos derivados razonando sobre lo que el proyecto quería
permitir. No consideró lo que las fuentes primarias **obligan**, porque en ese momento
ninguna estaba verificada.

Al verificar `ine_proyecciones` el 2026-07-27 —el denominador de toda tasa del proyecto— se
leyeron los [términos de datos abiertos del INE](https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos):
son **CC BY-SA 4.0**. Dos consecuencias, una tranquilizadora y una vinculante:

- Permiten uso comercial de forma explícita («para cualquier finalidad, incluso comercial»).
  El temor registrado antes a una cláusula no comercial era infundado para esta fuente.
- Exigen **ShareAlike**: quien modifica el material «deberá difundir sus contribuciones bajo
  la misma licencia que el original».

Publicar `gold` bajo CC BY 4.0, siendo que cada tasa se calcula sobre población del INE,
arriesga incumplir la licencia de origen.

## Decisión

Los datasets derivados que publica el proyecto (capa `gold`: CSV, Parquet, manifiestos y
reportes de calidad) pasan de CC BY 4.0 a **CC BY-SA 4.0**.

Se adopta **exactamente la misma licencia y versión que la fuente**, no una equivalente.

El código sigue bajo MIT y la documentación narrativa bajo CC BY 4.0: la obligación de
ShareAlike nace de incorporar el material del INE, y la documentación no lo incorpora.

## Justificación

1. **Adoptar la licencia idéntica elimina la pregunta de compatibilidad.** Cualquier otra
   opción con ShareAlike —ODbL, por ejemplo, que es la licencia «share-alike de bases de
   datos» más habitual— obligaría a argumentar compatibilidad entre licencias distintas.
   CC BY-SA 4.0 sobre CC BY-SA 4.0 no admite discusión. Desde la versión 4.0 la licencia
   cubre además explícitamente los derechos *sui generis* de bases de datos, que es la figura
   bajo la que podría caer una tabla de población.
2. **No cuesta lo que costaría una cláusula NC.** CC BY-SA sigue permitiendo uso comercial,
   así que se mantienen los usos que ADR 0004 quería proteger: prensa, consultoría en
   política pública, docencia pagada. Sigue siendo una licencia abierta estándar, indexable
   en catálogos de datos abiertos.
3. **Evita depender de un argumento jurídico frágil.** Se podría sostener que una tasa es un
   hecho nuevo y no una obra derivada del cuadro del INE —los hechos no son objeto de derecho
   de autor y Chile no tiene un derecho *sui generis* de bases de datos como el europeo—.
   Puede que sea correcto, pero el proyecto quedaría apostando su cumplimiento legal a una
   interpretación que nunca ha sido puesta a prueba. No es una posición defendible para un
   proyecto cuyo argumento central es la trazabilidad.
4. **Elegirla ahora es barato; cambiarla después no.** Una vez que alguien reutiliza un
   dataset bajo CC BY 4.0, esa copia queda legítimamente bajo esa licencia para siempre.
   Corregir el error más tarde significa convivir con versiones bajo licencias distintas.
5. **Es coherente con lo que el proyecto le exige al Estado.** Resulta difícil reclamar
   trazabilidad y respeto por las condiciones de publicación mientras se relicencia hacia
   términos más laxos el trabajo de otro organismo público.

## Alternativas descartadas

**Mantener CC BY 4.0 y no redistribuir nunca la tabla de población, publicando solo
indicadores.** Descartada: obliga a sostener permanentemente que ninguna salida es obra
derivada, y basta con que una versión futura publique el denominador junto al indicador
—algo natural para permitir verificación— para incumplir sin que nadie lo note. Además
empeora el producto: publicar el denominador es justamente lo que hace auditable una tasa.

**Licencia mixta con los datasets bajo CC BY-SA y algunos derivados bajo CC BY.** Descartada
por complejidad sin beneficio: obliga a rastrear qué salida tocó qué fuente, que es
exactamente el tipo de contabilidad que se rompe en silencio.

## Consecuencia aceptada

La obligación de ShareAlike se contagia a quien reutilice los datos y construya sobre ellos.
Algunos reutilizadores —sobre todo productos propietarios que quieran incorporar el dataset
sin abrir su propio derivado— quedarán fuera. Se acepta: es la condición que el INE le puso a
su material y el proyecto no está en posición de levantarla, ni le corresponde hacerlo.

## Pendientes que esta decisión no cierra

- Las licencias de `deis_defunciones` y `subdere_cut` siguen en `por_confirmar`. Si alguna
  resultara incompatible con ShareAlike, hay que reabrir esto. Fuentes bajo CC BY o dominio
  público no dan problema: se pueden incorporar a una obra CC BY-SA.
- `ine_vitales_anuario` figura como CC BY-NC 2.0, en contradicción con los términos generales
  CC BY-SA 4.0 del mismo organismo. De esa fuente solo se usan dos cifras como ancla de
  verificación y no se redistribuye el documento, así que no condiciona esta decisión, pero
  conviene aclararlo con el INE.
- Si se migra a la base Censo 2024, verificar que sus términos no cambiaron.
