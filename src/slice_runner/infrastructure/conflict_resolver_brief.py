from __future__ import annotations

from typing import ClassVar

_BRIEF = """\
# Resolucion de un conflicto de fusion

Git no ha podido fusionar solo la rama base con la rama de la slice: hay ficheros con marcas de
conflicto de verdad, y hasta ahora eso paraba el run entero para que una persona bajara a resolverlo
a mano. Ese trabajo es tuyo ahora.

## Lo que recibes

El directorio de trabajo del proceso es el repo de la slice, con una fusion a medias en curso: los
ficheros en conflicto tienen las marcas `<<<<<<<`, `=======` y `>>>>>>>` dentro. Al final de este
prompt, bajo "## Datos del conflicto", tienes las rutas exactas que estan en conflicto y las fuentes
de convencion del repo.

## Lo que haces

- Abre cada ruta declarada en conflicto, entiende las dos versiones y escribe el contenido final sin
  ninguna marca de conflicto.
- **Toca unicamente las rutas que se te declaran.** No es tu trabajo continuar la slice ni arreglar
  nada mas que encuentres por el camino: lo que cambies fuera de esas rutas se rechaza entero y la
  ronda se descarta, aunque el conflicto en si quedase bien resuelto.
- Si una ruta declarada no se puede resolver de forma razonable, dejala tal cual con sus marcas: no
  inventes un lado ganador a ciegas. Lo que quede sin resolver se detecta y la fusion se aborta para
  que se reintente.
- **No tienes `Bash`.** No haces `git add`, no concluyes ni abortas la fusion: eso lo decide el
  programa mirando el arbol despues de que termines, no lo que tu digas haber hecho.

## Lo que devuelves

Tu respuesta final es el objeto del esquema que se te ha mandado, que tiene **un solo campo**. Que va
dentro lo dice el propio esquema, en la descripcion de ese campo: leela antes de escribir, porque es
el unico sitio donde esta y no se repite aqui.
"""


class ConflictResolverBrief:
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Write", "Edit", "Grep", "Glob")
    TEXT: ClassVar[str] = _BRIEF
