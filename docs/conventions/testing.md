# Tests

## Como se mide todo

```bash
make check   # ruff check + ruff format + mypy strict + pytest; todo verde
```

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`.

**Lanzalo siempre con `uv`.** El programa de `src/` depende de `pydantic`, asi que un
`python3 -m pytest` con el interprete del sistema pasa o falla segun lo que tengas instalado, y eso no
es una vara.

Para acortar el ciclo:

```bash
make test PYTEST_ARGS="-m 'not integration' --nf -x --tb=short --disable-warnings --color=no --no-header"
```

## El marcador `integration`

Un solo marcador, con un criterio que no se discute en review: **el test lanza un subproceso de
verdad** (`git`, un comando declarado, un ejecutable). Es lo que cuesta tiempo y lo que depende de la
maquina. Escribir en `tmp_path` no entra.

- Se aplica a la **clase** cuando el arbol nuevo la agrupa, y a la funcion en `tests/`, que todavia
  es function-based.
- `-m "not integration"` es el subconjunto rapido para el ciclo; **la suite entera sigue siendo la vara
  al cerrar una slice y en la integracion continua**. El marcador acorta el bucle, no lo que se exige.

## Los dos arboles, y por que

| | Que cubre |
|---|---|
| `src/slice_runner/tests/` | El programa. Co-localizado dentro del paquete, espejando las capas. |
| `tests/` | Los scripts de `skills/` y los **contratos entre `.md`**, que no tienen paquete donde vivir. |

Lo compartido por los dos arboles vive en `src/slice_runner/tests/git_repo.py`: la clase `Git`, con la
rama base, el helper de `git` y el repo recien inicializado. **La direccion es esa** porque `src` entra
en el `pythonpath` y el directorio de `conftest` no, asi que `src/slice_runner/tests/` no puede consumir
de `tests/` y al reves si.

`Git.BASE_BRANCH` se fija explicitamente (`git init -b`) porque `init.defaultBranch` es config de la
maquina y el bloque de `diff-bundle` se cae en una que use `main`.

Lo compartido por la suite de `tests/` vive en `tests/conftest.py`: la fixture `repo` y los helpers de
escribir/stagear. No vuelvas a definirlos en un fichero de tests -hubo tres `_write` con firmas
distintas a la vez, y leer cualquier test obligaba a subir a la cabecera-.

## Forma de un test

- **Dentro de una clase**, agrupados por el comportamiento que fijan. Nunca funciones sueltas en el
  arbol nuevo.
- **Cero prosa**, igual que el codigo de produccion: el nombre del test es la frase.
- El nombre dice **que se garantiza y por que**, no que metodo se llama:
  `test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null`.
- Los helpers de un test son `@staticmethod` de su clase de test, o viven en un modulo compartido
  (`argv.py`), pero **nunca sueltos a nivel de modulo**.

## Object Mothers

**Los objetos de un test los construye un mother**, no el propio test:
`src/slice_runner/tests/mothers/{cosa}_mother.py`.

Un mother da defaults sensatos y deja que cada test nombre **solo lo que su caso cambia**, que es lo que
hace legible el assert. Sin ellos, el mismo diccionario de hallazgo se copiaba en dos ficheros de test
con valores distintos y ninguno decia por que.

Los metodos son **escenarios con nombre** (`without_line`, `passing`, `high_severity_finding`), no un
`create(...)` con todo por defecto: asi el test dice de que caso va sin leer los argumentos.

## Dobles

- **`create_autospec(X, spec_set=True, instance=True)`** para puertos sin estado.
- **Dobles con estado a mano**, en `src/slice_runner/tests/doubles.py`: `RecordedProcess` graba el
  `argv` y el `stdin` que recibio, `UnrunnableProcess` levanta. Un `Mock` no sirve cuando el test
  necesita preguntar por lo que se le paso.
- **Nada de mockear value objects**: se usan instancias reales.
- El arrange **no se construye con la pieza bajo prueba**. El repo de un test de `GitDiffWriter` se
  monta con `git` de verdad, no con el propio `GitDiffWriter`.

## Que se testea y que no

- **No hay tests unitarios de dominio** salvo un value object con validacion propia. El dominio queda
  cubierto por los tests de aplicacion y de frontera; un test que solo comprueba que un dataclass
  guarda lo que le pasas mide el lenguaje, no el codigo.
- **Aplicacion**: puertos mockeados por constructor, y el assert sobre el **efecto observable** (que
  recibio el puerto, que devolvio el caso de uso), no sobre la llamada.
- **Frontera**: el assert es la **carga literal** que se envia o se recibe, no un modelo de ella
  reimplementado en el test. Comparar contra un modelo propio del formato es reescribir el mapeo y
  aprobarlo por construccion.
- **Antes de anadir un test, comprobar si el comportamiento ya esta cubierto.** Solo entra si aporta
  una dimension distinta.

## Los contratos entre los `.md`

`make check` **tambien cubre los `.md`**, no solo el codigo. `tests/test_skill_contracts.py` compara los
contratos que hoy estan escritos dos veces:

- motivos de `bloqueada:` en `SKILL.md` vs `issue_body.py`
- veredictos de `metrics.py`
- el JSON del verificador en `agents/` y en `slice-runner`
- las herramientas que `src/slice_runner/` concede al juez vs las que declara su prompt
- las claves del hallazgo en la rubrica vs los `alias` de `FindingPayload`
- los veredictos y las severidades de la rubrica vs los que el programa acepta
- el criterio de degradacion sin subagentes, duplicado a proposito en `slice-runner` y `deploy-watch`

Cada test **extrae** el vocabulario de ambos lados y los compara, asi que reescribir las dos copias a la
vez pasa y tocar solo una falla. Si editas una skill y `make check` se pone rojo ahi, es que has movido
una mitad del contrato: mueve la otra.

Comprueba ademas que **toda ruta de este repo citada en los `.md` existe**
(`test_every_repo_path_cited_in_the_docs_still_exists`). Aqui no se enlaza con markdown: se citan rutas
en backticks, asi que lo que se valida es el token. Solo entran los que empiezan por un directorio de
primer nivel del repo, lo que deja fuera por construccion los nombres sueltos (`controles.py`), las
rutas de otros repos y los patrones de rama (`slice/NN-name`). Dos ficheros no se escanean, cada uno por
lo que **es**: `docs/superpowers/specs/` (registro fechado, describe el arbol de su dia) y
`skills/slice-spec/references/observabilidad.md` (documenta rutas de repos ajenos).

## Antipatrones

- Un test como funcion suelta en el arbol nuevo.
- Un comentario o un docstring en un test.
- Un test que lanza un subproceso y no lleva `@pytest.mark.integration`.
- Construir un objeto de dominio a mano en el test cuando hay mother, o duplicar en el test las
  constantes del mother.
- Un helper de test suelto a nivel de modulo, o repetido en dos ficheros.
- Arrange construido con la pieza bajo prueba.
- Assert contra un modelo del formato reimplementado en el test, en vez de contra la carga literal.
- Un test de dominio que solo comprueba que un dataclass guarda sus campos.
