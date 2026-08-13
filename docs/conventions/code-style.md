# Estilo de codigo

Rige para **todo `.py` nuevo**. Los scripts viejos de `skills/` no la cumplen todavia: ver la lista
de lo que no es referencia en `CLAUDE.md`.

## Reglas criticas

- **Cero prosa: ni comentarios ni docstrings.** Nada de `#`, y tampoco docstring de modulo, de
  clase, de funcion ni de atributo. La unica excepcion es el shebang.
- **Ninguna funcion suelta a nivel de modulo: toda funcion cuelga de una clase.** Metodo,
  `@classmethod` o `@staticmethod`, incluido el `main` de un ejecutable.
- **El codigo va en ingles.** Nombres de fichero y de modulo, clases, funciones, metodos, variables,
  parametros, constantes, miembros de enum, excepciones, nombres de test, nombres de subcomando, y
  los mensajes de error que ve una persona.
- **Sin imports relativos.** Lo mide `TID` en `ruff`.

## Por que cero prosa

Si un trozo de codigo no se entiende sin un parrafo al lado, **el arreglo es el codigo y no el
parrafo**: nombres que digan lo que hacen, funciones pequenas con una responsabilidad, tipos que
hagan imposible el mal uso, constantes con nombre en vez de literales. Un `if` que necesitaba tres
lineas de explicacion es casi siempre una funcion con nombre esperando a nacer, y un invariante que
se explicaba en prosa es casi siempre un test que falta.

El *por que* va al **registro duradero**: el cuerpo de la pull request y `docs/`. Es lo que se sigue
leyendo cuando el fichero ya se ha reescrito tres veces.

## Por que ninguna funcion suelta

Lo que era una funcion privada de modulo mas un punado de constantes sueltas es casi siempre una
clase esperando a nacer, y ponerle nombre es lo que dice **de quien** es esa logica.

Ejemplo real: `verifier_argv` + `_prompt` + `_readable_dirs` + dos constantes de modulo se leian como
cinco cosas independientes, y eran una sola (`JudgeInvocation`). No es cosmetica -mientras fueron
funciones sueltas nadie noto que a la invocacion le faltaba el `--add-dir` sin el que el juez no ve
el diff-.

## Imports

- `from __future__ import annotations` primero, antes de cualquier otro import.
- Siempre al inicio del fichero, **nunca** dentro de funciones, metodos o clases.
- Agrupados: (1) stdlib, (2) terceros, (3) modulos del proyecto. Separados por linea en blanco. Lo
  ordena `I` (isort) en `ruff`, y `known-first-party` declara los scripts que se importan por nombre
  (`metrics`, `discover_conventions`...) para que no se mezclen con las dependencias de terceros.
- Los imports usados solo en anotaciones van en un bloque `if TYPE_CHECKING:` al final del bloque,
  con el mismo orden interno. El bloque solo se introduce si hay imports que sean solo-tipos.

## Formato

- Linea en blanco antes del `return` y entre bloques logicos de un metodo.
- `line-length = 120`, comillas dobles, formateado por `ruff format`.

## Antipatrones

- Un comentario o un docstring explicando codigo que se podria renombrar. **Hay que reescribir el
  codigo.**
- Una funcion a nivel de modulo. **Hay que buscarle la clase.**
- Un import dentro de una funcion o de un metodo.
- Un bloque `if TYPE_CHECKING:` vacio, o con imports que se usan en runtime.
- Un identificador en castellano que no sea dato de un contrato.
