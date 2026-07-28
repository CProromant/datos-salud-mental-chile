# Declaración de uso aceptable

Este documento expresa las **normas del proyecto**, no cláusulas de licencia. Los datos se
publican bajo CC BY-SA 4.0 y jurídicamente permiten cualquier uso que esa licencia
permita, incluido el comercial. Lo
que sigue es lo que el proyecto pide, y lo que hará públicamente si observa lo contrario.

## Usos para los que existe este proyecto

Diagnóstico territorial, evaluación de política pública, priorización de recursos,
investigación académica, fiscalización, docencia y periodismo especializado.

## Usos que el proyecto rechaza

1. **Puntuación o predicción de riesgo individual.** Los datos son agregados y no lo
   permiten técnicamente; construir un sistema de este tipo invocando este proyecto como
   fuente es una tergiversación de lo que los datos pueden decir.
2. **Evaluación de desempeño de profesionales o equipos identificables.** La unidad de
   análisis es el territorio y el sistema.
3. **Focalización comercial:** tarificación de seguros, marketing farmacéutico dirigido,
   scoring crediticio o laboral basado en la salud mental de un territorio.
4. **Rankings de comunas por tasa de suicidio.** Con eventos raros, un ranking ordena ruido
   y estigmatiza territorios. El dataset incluye la medida de incertidumbre justamente para
   que no se haga.
5. **Presentación de las cifras sin sus advertencias metodológicas**, en particular sin
   marcar años preliminares ni quiebres de serie.

## Lo que se pide a quien haga uso comercial

La licencia permite el uso comercial y el proyecto no quiere impedirlo: prensa, consultoría
en política pública y docencia pagada son usos legítimos y buscados. Pero se **pide** —como
norma, no como condición legal— lo siguiente:

1. **Avisar.** Un correo diciendo qué se está haciendo con los datos. No para autorizar
   nada, sino porque saber quién los usa es lo único que permite avisar de una corrección
   o de un quiebre de serie a quien le importa.
2. **Citar a la fuente primaria, no solo a este proyecto.** Los datos vienen de DEIS/MINSAL
   y del INE. Este proyecto no genera datos primarios: los limpia, los cruza y los documenta.
3. **Arrastrar las advertencias.** Un producto comercial que muestre estas cifras sin decir
   que los últimos dos años son preliminares, o que las diferencias entre comunas pequeñas
   son mayormente ruido, está vendiendo precisión falsa.

**Por qué esto vive acá y no en la licencia.** Se evaluó publicar bajo CC BY-NC-SA para
restringir el uso comercial, y **no es legalmente posible**: el INE publica las proyecciones
de población bajo CC BY-SA 4.0, cuya cláusula 3(b) exige que toda obra derivada lleve una
licencia con *los mismos elementos*. Agregar «no comercial» a material que no lo traía viola
esa condición. Restringir acá habría cambiado un riesgo hipotético por un incumplimiento
cierto. El razonamiento completo está en `docs/adr/0005-licencia-datos-sharealike.md`.

## Qué hará el proyecto

Ante un uso que contravenga lo anterior y sea de conocimiento público, el proyecto publicará
una aclaración técnica señalando qué dicen realmente los datos. No es una amenaza legal: es
la única herramienta apropiada para un proyecto cuyo valor es la exactitud.
