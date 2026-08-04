# Capa de dominio

Value objects, puertos y excepciones. No conoce ninguna otra capa, no hace entrada/salida y no lleva
Pydantic.

## Value objects

- **Dataclasses `frozen=True, kw_only=True, slots=True`.** Sin excepciones: si algo se construia por
  partes y luego se mutaba, se construye una vez al final o se usa `dataclasses.replace`. Es lo que
  hizo falta en `parse_body` y en `comprueba_higiene_pr`.
- Sin sufijo `VO` ni `ValueObject`.
- Datos y, si hace falta, comportamiento propio. **Nada de serializacion**: convertir a las claves de
  un contrato externo es trabajo de la frontera (`docs/conventions/infrastructure.md`).

## Vocabulario cerrado

**`StrEnum`**, no tuplas de `str` (`Estado`, `MotivoBloqueada`, `EstadoCI`, `Severidad`, `Veredicto`,
`Modo`, `Ruling`, `Severity`...). Los miembros se serializan como su cadena, asi que ni el formato del
issue ni el JSON de salida cambian, pero las comparaciones y los `choices` de cada interfaz de linea
de comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un
  contrato** que lo fije de otra forma (`Ruling.PASS = "PASA"`).
- En `argparse`, `choices=[str(x) for x in Enum]`: con `list(Enum)` el mensaje de error muestra el
  `repr` del miembro.
- Codigos de salida de un ejecutable: `IntEnum`, y el mapeo desde el vocabulario del dominio con un
  `match` exhaustivo, para que anadir un miembro rompa en `mypy` en vez de caer en silencio en la
  rama generica.

## Puertos

- Interfaces con `ABC` y `@abstractmethod`. Nada mas: sin implementacion por defecto, sin estado.
- El puerto declara lo que el dominio necesita, no lo que el adaptador sabe hacer.

## Excepciones

- Nombradas por lo que pasa, no por donde: `InvalidVerdictError`, `EmptyIndexError`,
  `UnresolvableRepoOrBaseError`, `ProcessNotRunnableError`.
- Jerarquia cuando el consumidor necesita distinguir: `EmptyIndexError` y
  `UnresolvableRepoOrBaseError` heredan de `DiffNotReadableError` porque la interfaz de linea de
  comandos les da codigos de salida distintos, y quien no distingue captura la de arriba.
- Heredan del tipo que corresponde (`ValueError`, `OSError`), no de `Exception` a secas.

## Nada de `dict` crudo como valor de retorno de logica

Un `dict` que cruza dos funciones propias se lee con `.get()` en el consumidor, y ahi una clave mal
escrita y una ausente dan lo mismo -era el fallo de `build_scorecard` y de `_slice_info`, que ademas
obligaba a tres `assert isinstance(...)` en produccion solo para `mypy`-.

Los `dict[str, object]` que quedan son todos frontera de serializacion.

## Antipatrones

- Un dataclass del dominio sin `frozen=True, kw_only=True, slots=True`.
- Un `to_dict()` en el dominio. **La traduccion al contrato externo vive en la frontera.**
- Una tupla de `str` como vocabulario cerrado.
- `Optional[Enum]` cuando lo que se modela es un estado ausente: eso es un miembro mas del enum.
- Un `dict` como valor de retorno de una funcion de logica.
- Pydantic en cualquier fichero de `domain/`.
