# Disenar preguntando lo que importa

Reference-doc de `slice-spec`. Se carga en el paso 1 del modo autoria (`reference-docs`): el modo
`validate` no lo paga.

## Para que existe

Un diseno que nadie interroga deja decisiones que luego toma el implementador sin que nadie lo vea
(`silent-misalignment`). Pero preguntar todo lo que se puede preguntar falla al reves: la persona acaba
contestando a destajo casos que no se van a dar, y una respuesta a destajo no informa mas que una
pregunta que no se hizo (`cognitive-overload`).

Por eso la profundidad la pone el agente investigando, y a la persona solo le llega lo que solo ella
puede decidir. Lo demas lo decide el agente y lo deja escrito, para que la persona lo vete en el paso 1c.

## Primero se investiga

Antes de la primera pregunta corre la investigacion del paso 1b de `slice-spec`. **Nunca preguntes algo
que puedes mirar.**

## Que llega a la persona

Una pregunta llega a la persona solo si pasa **los dos filtros**:

1. **Es ambigua de verdad**: el codigo, las fuentes de convencion y los precedentes no deciden entre dos
   caminos razonables.
2. **Cambia lo que se construye**: segun la respuesta, salen distintas las slices, sus criterios o sus
   contratos.

**Un caso raro solo entra con un puntero** que diga que aplica aqui: un consumidor que existe, una fila
que ya esta escrita, un precedente con su numero. "Podria pasar que..." sin puntero no se pregunta ni se
decide: se descarta.

Lo que no pasa los filtros lo decide el agente, y cada una de esas decisiones va a la lista de
**decisiones del agente** que publica el paso 1c. Lo que solo se cierra con su motivo no va a la lista.

## Como se pregunta

- **Sin cupo y sin rondas fijas.** Lo mas importante primero, unas pocas cada vez, y espera la
  respuesta: lo que una respuesta desbloquea va despues, no en el mismo mensaje.
- **Una decision de diseno trae al menos dos caminos distintos** con lo que cuesta cada uno (`cast-wide`);
  un camino y su variante cosmetica no son dos.
- **Cada pregunta lleva tu recomendacion y en que se basa**: un hecho con su ruta o su numero, una
  convencion con el fichero que la declara, o que es una preferencia. Sin la base, la recomendacion sesga
  sin que se vea (`answer-injection`).
- **La numeracion es continua** (`Q1`, `Q2`...) y no vuelve a empezar, para que la persona conteste por
  numero.
- **Llevale la contraria con evidencia** (`active-partner`): si lo que pide la persona choca con lo que
  dice el codigo o una convencion, dilo con el puntero en vez de acatarlo.

## Lo que el agente recorre siempre

No son preguntas: es lo que el agente revisa antes de cerrar, porque es lo que un diseno deja sin mirar
y luego paga una slice. Cada punto acaba decidido -por la persona si pasa los filtros, por el agente si
no- o cerrado con su motivo.

- **Que sustituye, y que deja ilegible de lo ya escrito**: estado persistido, filas de un almacen
  durable, ficheros que el programa relee.
- **Quien mas consume lo que cambia**: otro repo, un comando que alguien invoca con sus valores por
  omision.
- **Si alguna regla que ya existe decide esto mismo**: dos sitios acaban diciendo cosas distintas.
- **Los conceptos de dominio**: aggregates, value objects, vocabularios cerrados, y que nombra cada uno.
- **La arquitectura**: que capa, que puerto y que modulo para cada pieza nueva, y el flujo de
  dependencias.
- **Los contratos con sus firmas**: lo que cruza una frontera, con la firma exacta. Es lo que deja
  construir sus dos lados a la vez.
- **Que numero o tope se elige**: sin medicion es una preferencia, y se dice.
- **Si algun criterio choca con lo que la slice excluye o sustituye, o no lo puede cumplir el
  implementador ni medir el juez**: el implementador no toca git ni compone la pull request, y el juez no
  recibe su informe.

Nombres de ficheros y clases y estrategia de tests: solo se preguntan si las fuentes de convencion del
repo destino no los cubren. Si las cubren, se cita la fuente y no se pregunta.

## Cuando se acaba

Cuando no queda abierta ninguna pregunta que pase los filtros y todo lo de la lista esta decidido o
cerrado. Entonces se cierra con el paso 1c de `slice-spec`.

## La refutacion

Con el borrador de la spec escrito, lo recibe un **subagente que no diseno**, solo con ese texto, y su
unico trabajo es **intentar refutarlo** (`feedback-flip`): quien acaba de proponer algo tiende a
defenderlo, y el que refuta no tiene nada que defender.

Se le pide:

- que se rompe con lo que se propone, y a quien;
- que lineas de una misma slice se contradicen, o que criterio choca con otro;
- que criterio no puede cumplirse o no puede medirse;
- que afirmacion del diseno no se sostiene con lo que el propio texto dice.

Sus objeciones pasan **los mismos dos filtros**. Las que si, y cualquiera que contradiga una decision
de la persona, van a ella con su recomendacion. Las
que no, las corrige el agente en el borrador y las nombra al cerrar (paso 6), una linea cada una, para
que la persona sepa que cambio despues de confirmar el troceo. Si una correccion cambia el troceo, la
lista corta del paso 2d se vuelve a ensenar. Hay una sola pasada: la refutacion no se repite sobre sus
propias correcciones.
