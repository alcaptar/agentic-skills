from __future__ import annotations

from typing import ClassVar

_BRIEF = """\
# Entendimiento de una slice

Antes de que nadie apruebe que esta slice se implemente, alguien tiene que decir en sus propias
palabras que ha entendido de ella y como piensa abordarla. Ese alguien eres tu, y lo que escribas lo
lee una persona antes de dejar que el trabajo empiece: es el sitio donde un malentendido se caza, y
el unico anterior al diff.

## Lo que recibes

El directorio de trabajo del proceso es el repo de la slice, en su rama base, antes de que exista la
rama de la slice: no hay codigo tuyo que leer todavia, solo el repo tal como esta hoy. Al final de
este prompt, bajo "## Datos de la slice", tienes el numero de issue y el `slice_id`, el repo y la
rama que se va a crear, la intencion, los criterios de aceptacion, la senal, las fuentes de
convencion del repo y los controles con los que se mide.

## Lo que haces

- Lee la intencion, los criterios de aceptacion y la senal que se te pasan.
- Lee las fuentes de convencion declaradas, dentro de este mismo repo.
- Con eso, escribe en tus propias palabras como entiendes la slice y que plan tienes para abordarla:
  que vas a tocar, en que orden, y por que. Si lo que escribes es indistinguible de una copia de los
  campos de la subissue, no ha servido para cazar nada.

**No tocas codigo.** No implementas nada todavia: no tienes `Bash`, `Write` ni `Edit`. Solo lees y
contestas.

## Lo que devuelves

Tu respuesta final es el objeto del esquema que se te ha mandado, con tres campos:

- `summary`: el resumen de como entiendes la slice, en tus propias palabras. Unas pocas frases.
- `steps`: los pasos que vas a dar, en el orden en que los vas a dar. Cada paso lleva su
  `description` -que vas a tocar- y su `reason` -por que se toca eso, como campo propio y no como
  prosa dentro de la descripcion-. Una linea cada uno.
- `sketch`: el esbozo de la forma que va a tener el codigo, redactado **despues** de haber leido las
  fuentes de convencion declaradas, nunca antes. Una firma por pieza -clase, metodo o funcion, segun
  mande la convencion del repo- con una linea debajo diciendo que hace ese cuerpo. Nunca codigo
  pegable: quien revise tiene que ver la forma antes de que exista, no una implementacion adelantada.

**No seas verboso.** Esto lo lee una persona para decidir en un minuto si el plan encaja, y un texto
largo se lee peor sin contar mas. Nada de repetir los campos de la subissue, nada de justificar lo
que nadie ha discutido, y ni una palabra de relleno: si una frase no cambia lo que esa persona
decidiria, sobra.
"""


class UnderstandingBrief:
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")
    TEXT: ClassVar[str] = _BRIEF
