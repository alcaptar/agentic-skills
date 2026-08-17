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
src/{paquete}/
  domain/
    {value_object}.py     un value object por modulo
    {enum}.py             un vocabulario cerrado por modulo
    {puerto}.py           un puerto por fichero
    {politica}.py         logica pura con su configuracion inyectada
    exceptions.py         las excepciones del dominio
  application/
    actions/{name}.py     casos de uso que mutan estado
    queries/{name}.py     casos de uso de solo lectura, con un puerto detras
  infrastructure/
    {impl}_{puerto}.py    el adaptador se llama como su implementacion
    {payload}.py          un modelo de frontera por concepto
    {agente}_{rol}.py     lo que define un agente invocado: su rubrica, sus herramientas, lo que lee
    cli.py                entrypoint
  tests/                  co-localizados, espejando las capas de arriba
    mothers/              Object Mothers
    payloads/             sobres reales grabados (su regla, en docs/conventions/testing.md)
  py.typed
  __main__.py
```

- **Un concepto por modulo, y con el lo que no existe sin el.** La regla no cuenta clases -contarlas es
  un censo con otra cara, y obliga a partir en dos ficheros lo que solo se lee junto-: pregunta por la
  dependencia. **La vara es dura a proposito: si borras el concepto principal, ¿el otro tipo se queda sin
  ningun consumidor y sin sentido propio?** Solo entonces comparten fichero. El caso claro es el
  vocabulario cerrado que solo clasifica un campo de ese value object, o la carga que un puerto recibe y
  que nadie mas construye.

  **Y al reves: un tipo con vida propia es un concepto y va a su modulo**, aunque hoy se use al lado del
  otro. Tiene vida propia si lo construye otro sitio, si lo consume otra capa o si lleva su propia
  algebra. Sin esa mitad, "no existe sin el" se estira hasta justificar cualquier agrupacion por
  costumbre.

  Las excepciones del dominio son la excepcion a la regla y viven juntas en `domain/exceptions.py`, porque
  se leen como un catalogo y quien las captura suele querer ver la jerarquia de una vez.
- **Un puerto que solo consume la infraestructura vive con su adaptador**, no en `domain/`, junto a la
  excepcion que lanza. El caso tipico es el que lanza subprocesos: el dominio no los lanza ni sabe que
  existen, y subirlo metería ahí ese vocabulario, que es exactamente lo que esa capa se define por no
  tener. Consecuencia: `domain/exceptions.py` es el catalogo de las excepciones **del dominio**, no de
  todas las del programa.

  **Y la premisa se comprueba cada vez, porque caduca**: en cuanto un caso de uso necesita ese puerto,
  vuelve a `domain/`, que es donde vive por defecto todo lo que el dominio necesita.
- **Los tests del programa viven dentro del paquete**, no en `tests/`, y espejan la estructura de las
  capas **que se testean**. No hay un arbol de tests de dominio, y no es un olvido -la estrategia es
  outside-in y lo de dentro del dominio se cubre por ese camino-. El reparto de los dos arboles y el
  porque estan en `docs/conventions/testing.md`.
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

`backend-engineering:backend-best-practices` dice **"dataclasses frozen, sin pydantic"** para dtos,
params, value objects y events. Aqui se cumple en todo eso, y se diverge en un solo sitio: **el esquema de la frontera
externa**.

El motivo es que esa vara asume Django + Django REST Framework, donde los serializers ya validan
la entrada y generan el esquema OpenAPI. Aqui no hay capa de serializers: la frontera es el JSON de un
subproceso, y el esquema **hay que generarlo** para mandarselo al juez. Sin Pydantic eso son tres
copias del mismo contrato cosidas a mano, que es de donde se viene.

Lo que **no** autoriza esta desviacion: Pydantic en `domain/`, ni en los `Params` de un caso de uso,
ni como sustituto de un value object.

## Decisiones de configuracion que no se re-litigan

Razonadas en `pyproject.toml`:

- **`ruff` no formatea los `.md`**: aqui los `.md` son el producto (las skills y sus reference-docs),
  y sus ejemplos se escriben para leerse.
- **Las reglas `S` (bandit) estan desactivadas**: sus hallazgos son inherentes al cometido de los
  scripts de `skills/` que lanzan procesos externos, y obligarian a sembrarlos de `noqa` sin cambiar
  una sola decision.
- **`smoke/fixture/pyproject.toml` lleva el mismo `select`** que la raiz: la fixture es el sujeto que
  trocea el runner en el smoke, asi que relajarla ahi le daria al runner un aprobado que no vale. Si
  tocas uno, toca el otro.

## Antipatrones

- Una dependencia de terceros en `skills/*/scripts/`. **La lanza la skill sin `uv`: hay que resolverlo
  con stdlib.**
- Pydantic en `domain/` o en los `Params` de un caso de uso.
- `domain/` importando de `application/` o de `infrastructure/`.
- Relajar el `select` de `ruff` en `smoke/fixture/` sin tocar el de la raiz.
