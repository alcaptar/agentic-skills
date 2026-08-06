# Arquitectura y herramientas

## Los dos tipos de codigo Python de este repo

No es lo mismo y no se miden igual:

| | `src/slice_runner/` | `skills/*/scripts/*.py` |
|---|---|---|
| Que es | El programa orquestador | Los scripts deterministas que invoca una skill |
| Quien lo lanza | `uv run slice-runner` (el ejecutable que declara `[project.scripts]`) | La skill, con el `python3` de la maquina |
| Dependencias | `pydantic`, y **nada de `skills/`** | **stdlib puro**, sin excepcion |
| Convenciones | Las cumple entero | Deuda declarada (ver `CLAUDE.md`) |

Los scripts son stdlib puro **porque no hay `uv` que resuelva nada** cuando los lanza la skill: una
dependencia ahi es un fallo en la maquina de otra persona.

## Estructura del programa

```
src/slice_runner/
  domain/
    {value_object}.py     un value object por modulo (finding, verdict, judge, slice_diff...)
    {enum}.py             un vocabulario cerrado por modulo (ruling, severity, step, outcome)
    {puerto}.py           un puerto por fichero (diff_reader, verifier, skill_library)
    {politica}.py         logica pura con su configuracion inyectada (state_machine)
    exceptions.py         las excepciones del dominio
  application/
    actions/{name}.py     casos de uso que mutan estado
    queries/{name}.py     casos de uso de solo lectura, con un puerto detras
  infrastructure/
    {impl}_{puerto}.py    el adaptador se llama como su implementacion
    {payload}.py          un modelo de frontera por concepto
    slice_verifier_judge.py   el juez de este repo: su rubrica, sus herramientas, lo que puede leer
    cli.py                entrypoint
  tests/                  co-localizados, espejando las capas de arriba
    mothers/              Object Mothers
    payloads/             payloads reales grabados
  py.typed
  __main__.py
```

- **Un concepto por modulo**: un value object, un enum, un puerto, una politica o un adaptador por
  fichero. Las
  excepciones del dominio son la excepcion a la regla y viven juntas en `domain/exceptions.py`, porque
  se leen como un catalogo y quien las captura suele querer ver la jerarquia de una vez.
- **Un puerto que solo consume la infraestructura vive con su adaptador**, no en `domain/`. Es el caso
  de `infrastructure/process.py`, que declara el puerto `Process` junto a su `ProcessNotRunnableError`:
  el dominio no lanza procesos ni sabe que existen -lo necesitan `GitDiffReader` y `ClaudeVerifier`-, y
  subirlo a `domain/` metería ahí el vocabulario de subproceso, que es exactamente lo que esa capa se
  define por no tener. Consecuencia: `domain/exceptions.py` es el catalogo de las excepciones **del
  dominio**, no de todas las del programa.
- **Los tests del programa viven dentro del paquete**, no en `tests/`, y espejan la estructura de las
  capas **que se testean**: `src/slice_runner/tests/application/` y
  `src/slice_runner/tests/infrastructure/`. No hay un arbol de tests de dominio, y no es un olvido -la
  estrategia es outside-in y lo de dentro del dominio se cubre por ese camino-. El
  reparto de los dos arboles y el porque estan en `docs/conventions/testing.md`.
- El flujo de dependencias va hacia dentro: `infrastructure` conoce `application` y `domain`,
  `application` conoce `domain`, y `domain` no conoce a nadie.

## Herramientas

Python 3.11+, `dataclasses` frozen para value objects, `abc` para puertos, `StrEnum`/`IntEnum` para
vocabulario cerrado, `unittest.mock` para dobles, `pytest`, `mypy` strict, `ruff`, `uv` para el
toolchain, `argparse` para la interfaz de linea de comandos.

**`pydantic` solo en la frontera externa.** Los value objects y los DTOs internos son dataclasses
frozen; Pydantic aparece unicamente en los modelos que cruzan la frontera del proceso. El razonamiento
esta en `docs/conventions/infrastructure.md`.

### Desviacion declarada respecto a la vara secundaria

`backend-engineering:backend-best-practices` -y las convenciones de `mo.arcen-pi`, que son la
referencia de la casa- dicen **"dataclasses frozen, sin pydantic"** para dtos, params, value objects
y events. Aqui se cumple en todo eso, y se diverge en un solo sitio: **el esquema de la frontera
externa**.

El motivo es que esos proyectos son Django + Django REST Framework, donde los serializers ya validan
la entrada y generan el esquema OpenAPI. Aqui no hay capa de serializers: la frontera es el JSON de un
subproceso, y el esquema **hay que generarlo** para mandarselo al juez. Sin Pydantic eso son tres
copias del mismo contrato cosidas a mano, que es de donde se viene.

Lo que **no** autoriza esta desviacion: Pydantic en `domain/`, ni en los `Params` de un caso de uso,
ni como sustituto de un value object.

## Decisiones de configuracion que no se re-litigan

Razonadas en `pyproject.toml`:

- **`ruff` no formatea los `.md`**: aqui los `.md` son el producto (las skills y sus reference-docs),
  y sus ejemplos se escriben para leerse.
- **Las reglas `S` (bandit) estan desactivadas**: sus hallazgos viven todos en `controles.py`, donde
  lanzar procesos es el cometido del fichero, y obligarian a sembrarlo de `noqa` sin cambiar una sola
  decision.
- **`smoke/fixture/pyproject.toml` lleva el mismo `select`** que la raiz: la fixture es el sujeto que
  trocea el runner en el smoke, asi que relajarla ahi le daria al runner un aprobado que no vale. Si
  tocas uno, toca el otro.

## Antipatrones

- Una dependencia de terceros en `skills/*/scripts/`. **La lanza la skill sin `uv`: hay que resolverlo
  con stdlib.**
- Pydantic en `domain/` o en los `Params` de un caso de uso.
- `domain/` importando de `application/` o de `infrastructure/`.
- Relajar el `select` de `ruff` en `smoke/fixture/` sin tocar el de la raiz.
