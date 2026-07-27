# Cómo contribuir

## Antes de escribir código

Lee `CLAUDE.md` (aplica a personas igual que a asistentes) y el documento de la fase en la
que estás trabajando. Si tu cambio toca definiciones de indicador o política de publicación,
necesitas un ADR antes del código.

## Flujo

1. Issue que describa el problema, no la solución.
2. Rama `fuente/<id>`, `indicador/<id>` o `fix/<descripcion>`.
3. `make test` y `make lint` en verde.
4. Documentación actualizada **en el mismo commit** que el código.
5. Pull request con: qué cambia, qué se verificó realmente y qué quedó como supuesto.

## Lo que hará que tu PR sea rechazado

- Una URL de fuente marcada `verificada` sin evidencia de verificación.
- Datos descargados en el diff.
- Un test de territorio, CIE-10 o supresión relajado para hacer pasar otra cosa.
- Imputación de datos faltantes sin ADR.
- Cualquier salida que desagregue suicidio por método.
- Un indicador sin sección "qué NO significa".

## Reportar un error en los datos

Abre un issue con: dataset, versión, celda concreta, qué esperabas y por qué. Los errores en
datos publicados se corrigen con errata pública, nunca en silencio.
