# Disenar por rondas

Reference-doc de `slice-spec`. Se carga en el paso 1 del modo autoria (`reference-docs`): el modo
`validate` no lo paga.

## Para que existe

Un diseno que se aprueba pregunta poco y decide mucho: lo que nadie pregunto lo resuelve el agente en
silencio (`silent-misalignment`), y la decision reaparece mas tarde en la pausa de alineacion de una
slice, donde cuesta una ronda de `slice-runner review` -o `-REVIEW`- o la toma el implementador sin que nadie la vea. Este proceso
no termina cuando la persona dice que si: termina cuando **no queda ninguna decision sin tomar**.

Mezcla dos cosas. Del interrogatorio toma el arbol de decisiones y las rondas; de la exploracion de
enfoques toma que una decision de diseno se presenta con alternativas, no con la primera idea
(`cast-wide`). Y anade la que ninguno de los dos hace: que alguien que no diseno intente refutar el
resultado antes de crearlo (`feedback-flip`).

## El arbol y la frontera

El diseno es un **arbol de decisiones**: cada decision abre las que cuelgan de ella. La **frontera** son
las decisiones cuyos prerrequisitos ya estan tomados, las que se pueden preguntar ahora sin adivinar
respuestas que aun no se han oido.

Se trabaja por **rondas**. Una ronda pregunta **toda la frontera** de una vez, numerada, y espera las
respuestas antes de la siguiente. Cada respuesta mueve la frontera: lo decidido desbloquea lo que
dependia de ello. Una pregunta que depende de otra abierta en la misma ronda va a una ronda posterior,
no a esta.

Formato de una ronda, sin emojis:

```
**Q1 - <titulo>**: <la pregunta, con sus enfoques si es una decision de diseno>

**Recomendacion:** <la respuesta que recomiendas, y en que se basa>

---

**Q2 - <titulo>**: ...
```

La numeracion sigue entre rondas, no vuelve a empezar: la persona contesta por numero y una Q3 tiene que
ser siempre la misma.

## Cada pregunta

- **Una decision de diseno trae al menos dos enfoques distintos**, con lo que cuesta cada uno. Un
  enfoque y su variante cosmetica no son dos. Una pregunta de hecho o de preferencia no necesita
  enfoques.
- **La recomendacion dice en que se basa**: un hecho medido, con su ruta o su numero; una convencion,
  con la ruta del fichero que la declara; o que es una preferencia. Una recomendacion sin base sesga sin
  que se vea (`answer-injection`); con la base escrita, la persona sabe cuanto pesa.
- **Las decisiones son de la persona y los hechos son tuyos.** Nunca preguntes algo que puedes mirar.

## Los hechos los busca un subagente

Cuando una pregunta necesita un hecho del entorno -que hace hoy una pieza, si se intento antes, quien
consume una interfaz-, lanza un subagente que lo busque en background y **no bloquees la ronda**: un
hecho que se esta buscando es un prerrequisito sin resolver, asi que solo esperan las preguntas que
dependen de el. El resto de la frontera se pregunta ya.

Lo que encuentren entra en una ronda como algo que la persona confirma, con la vara del paso 1b: una
ruta o un numero, nunca una impresion. Es de ahi de donde sale `## Lo que ya existe`.

## Ramas que siempre se visitan

El arbol de cada feature es suyo, pero estas ramas existen en todos, porque son las que un diseno
aprobado deja sin visitar y las que luego paga una slice. Si una no aplica, se cierra diciendo por que,
no se salta.

- **Que sustituye, y que deja ilegible de lo ya escrito**: estado persistido en issues abiertas, filas
  de los almacenes durables, ficheros que el programa relee. Un lector nuevo con el esquema estricto
  revienta sobre una fila vieja que nadie considero.
- **Quien mas consume lo que cambia**: otro equipo, otro repo, un comando que alguien invoca con sus
  valores por omision. Cambiar un default rompe a quien no lo pasaba.
- **Si alguna regla que ya existe decide esto mismo.** Escribirla otra vez deja dos sitios que acaban
  diciendo cosas distintas; el diseno decide cual se queda.
- **Donde vive cada pieza nueva**: que capa, que puerto, que modulo. Si el diseno no lo decide, lo
  decide el implementador.
- **Que numero o tope se elige, y con que motivo.** Un numero sin medicion es una preferencia, y se dice.
- **Si algun criterio pide algo que la propia slice excluye o sustituye.** Un criterio que la slice hace
  imposible no lo puede cumplir nadie, y se descubre con el presupuesto gastado.
- **Si algun criterio lo puede cumplir el implementador y lo puede medir el juez.** El implementador no
  toca git ni compone la pull request; el juez no recibe el informe.

## Cuando se acaba

Cuando la frontera esta vacia: todas las ramas visitadas, nada supuesto en silencio. Entonces se cierra
con el paso 1c de `slice-spec`, que publica lo entendido y los criterios de la feature y espera
confirmacion. No se corta nada antes.

## La refutacion

Con el borrador de la spec escrito -padre y subissues, antes de ensenarlo entero- lo recibe un
**subagente que no diseno**, solo con ese texto, y su unico trabajo es **intentar refutarlo**: quien
acaba de proponer algo tiende a defenderlo, y el que refuta no tiene nada que defender. Es la misma
regla que separa al implementador del juez.

Se le pide:

- que se rompe con lo que se propone, y a quien;
- que lineas de una misma slice se contradicen, o que criterio choca con otro;
- que criterio no puede cumplirse o no puede medirse;
- que afirmacion del diseno es falsa o no se sostiene con lo que el propio texto dice.

Sus objeciones no se aplican solas: forman **una ultima ronda** a la persona, cada una con su
recomendacion. Lo decidido se corrige en el borrador. Hay una sola pasada: la refutacion no se repite
sobre sus propias correcciones.
