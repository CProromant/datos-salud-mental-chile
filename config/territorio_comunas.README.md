# territorio_comunas.csv — TABLA SEMILLA, INCOMPLETA A PROPÓSITO

Este archivo contiene **16 de las 346 comunas**: solo las capitales regionales, cuyos
códigos CUT son de verificación trivial. No es la DPA completa.

**Por qué está incompleta.** Escribir 346 códigos CUT de memoria es fabricar datos con
apariencia de autoridad: exactamente lo que prohíbe `CLAUDE.md §2.1`. Un CUT equivocado no
produce un error visible, produce un dato mal agregado que nadie detecta.

**Cómo completarla (tarea bloqueante de Fase 1).**

1. Descargar la División Político-Administrativa vigente publicada por el INE
   (o el maestro territorial de SUBDERE, que trae los mismos códigos CUT).
2. Convertir a este esquema: `comuna_cut,comuna_nombre,region_cut,provincia`.
3. Verificar: 346 filas, sin CUT duplicado, `comuna_cut[:2] == region_cut` en todas.
4. Correr `python -m obsm.cli territorio validar`, que aplica esas tres reglas.
5. Registrar en el commit la versión y fecha de la DPA usada; queda como
   `source_version` de todo dato territorial derivado.

Mientras la tabla esté incompleta, `obsm build gold` falla en modo estricto. Es
intencional: mejor no publicar que publicar un país al que le faltan 330 comunas.
