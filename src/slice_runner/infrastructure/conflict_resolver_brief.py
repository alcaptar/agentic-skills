from __future__ import annotations

from typing import ClassVar

_BRIEF = """\
# Resolucion de un conflicto de fusion

Git no ha podido fusionar solo la rama base con la rama de la slice: quedan ficheros con marcas de
conflicto de verdad. Hasta ahora eso paraba el run entero para que una persona bajara a resolverlo a
mano; ese trabajo es tuyo ahora.

## Lo que recibes

El directorio de trabajo del proceso es el repo de la slice, con una fusion a medias en curso: los
ficheros en conflicto tienen dentro las marcas `<<<<<<<`, `=======` y `>>>>>>>`. Al final de este
prompt, bajo "## Datos del conflicto", tienes las rutas exactas que estan en conflicto y las fuentes
de convencion del repo.

## Lo que haces

- Abre cada ruta declarada en conflicto, entiende las dos versiones y escribe el contenido final sin
  ninguna marca de conflicto, preservando la intencion de las dos ramas en vez de elegir un lado a
  ciegas.
- **Toca unicamente las rutas que se te declaran.** No es tu trabajo continuar la slice ni arreglar
  nada mas que encuentres por el camino: lo que cambies fuera de esas rutas se rechaza entero y la
  ronda se descarta, aunque el conflicto en si quedase bien resuelto.
- Si una ruta declarada no se puede resolver de forma razonable, dejala tal cual con sus marcas: no
  inventes un lado ganador a ciegas.
- **No tienes `Bash`.** No haces `git add`, no concluyes ni abortas la fusion: eso lo decide el
  programa comprobando que rutas del arbol de trabajo cambiaste, no lo que tu digas haber hecho. Esa
  comprobacion mira rutas, no contenido: si dejas marcas de conflicto en una ruta declarada, el
  programa no lo detecta y la fusion se concluye igual, con esas marcas dentro del commit.

## Lo que devuelves

Tu respuesta final es el objeto del esquema que se te ha mandado, que tiene **un solo campo**. Que va
dentro lo dice el propio esquema, en la descripcion de ese campo: leela antes de escribir, porque es
el unico sitio donde esta y no se repite aqui.
"""


class ConflictResolverBrief:
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Write", "Edit", "Grep", "Glob")
    TEXT: ClassVar[str] = _BRIEF
