# agentic-skills — instrucciones del repo

Este repo es la **fuente de verdad** de skills personales de Claude Code (`slice-spec`,
`slice-runner`, `deploy-watch`). Las skills viven aqui y `~/.claude/skills/` apunta por symlink,
asi que editar aqui cambia el comportamiento activo de Claude Code.

## Antes de hacer cambios (obligatorio)

Cuando vayas a **crear o modificar** una skill, sus scripts o los docs de este repo, carga
primero estas skills y trabaja segun ellas:

1. **`ai-patterns`** — el vocabulario y los patrones sobre los que estan construidas estas
   skills (`offload-deterministic`, `check-alignment`, `context-management`,
   `silent-misalignment`, `ai-slop`, `text-native`...). Usa esos nombres en el texto de las
   skills y respeta los patrones; no reinventes conceptos que ya tienen nombre.
2. **`superpowers:brainstorming`** — para cualquier cambio de diseno o de comportamiento,
   antes de editar: entiende la intencion, propon enfoques y valida el diseno. (El usuario
   puede saltarse el spec/plan si lo dice explicitamente.)

Para cambios triviales (typo, formato) no hace falta el ritual completo, pero manten la
coherencia con `ai-patterns`.

## Como se entrega un cambio: rama, pull request, merge

**Nada se commitea directamente en `master`**, ni siquiera un typo: hay un hook que bloquea el push
sobre la rama protegida, asi que descubrirlo tarde cuesta rehacer el trabajo de sacarlo de `master`.

```bash
git switch -c <type>/<slug>          # refactor/contexto-del-orquestador, docs/flujo-rama-pr-merge
git push -u origin <type>/<slug>
gh pr create                          # cuerpo con la intencion: que estaba mal y deja de estarlo
gh pr merge <N> --merge --delete-branch
git switch master && git pull --ff-only
```

- **`--merge`, no `--squash` ni `--rebase`**: los dos ultimos reescriben los hashes y dejan tu
  `master` local divergido de `origin/master`, con lo que el `git pull --ff-only` de despues falla y
  hay que resolverlo a mano justo cuando crees que has terminado.
- **El cuerpo de la pull request cuenta el por que**, no el diff -misma vara que las PRs que abre
  `slice-runner`: si borras el cambio, ¿que queda roto o imposible?-.
- `make check` en verde **antes** de abrir la pull request. `.github/workflows/check.yml` lo corre
  tambien en **toda** PR, sin filtro de `paths`, asi que la vara se mide donde se decide mergear; el
  local es para no descubrirlo en la CI. `.github/workflows/smoke-fixture.yml` sigue aparte porque
  mide otro proyecto (`smoke/fixture/`, con su propio lockfile) y si esta filtrado por `paths`.
- Esto es para el trabajo **sobre este repo**. Las ramas de una slice (`slice/NN-name`) las gestiona
  `slice-runner`, que ya trabajaba asi.

## Principios que no se rompen

- **El que implementa no verifica** (subagentes distintos; el verificador es adversarial y
  revisa convenciones/arquitectura, no re-testea).
- **Control humano en los puntos de riesgo**: el merge y el rollback los decide el usuario.
- **Esperas no bloqueantes**: ninguna skill lanza shells bloqueantes largas (`--watch`,
  `sleep` largos); las esperas son ticks acotados en background + notificacion.
- **No asumir worktree**: rama normal por defecto; worktree solo al paralelizar slices.
- **El estado del run vive en el issue de GitHub**: la spec y el estado de cada slice viven en el
  cuerpo de un issue (una feature = un issue), unica fuente de verdad viva y duradera. No hay estado
  local (`.slice-runner/`, ledger, panel). El registro duradero son el issue (intencion + estado) y
  las PRs mergeadas (codigo), no ficheros de estado en el repo.
- **La intencion se declara y viaja**: el issue abre con `## Intencion` (que esta mal hoy) y cada
  slice lleva su linea `INTENCION:` (el coste de no hacerla). De ahi sale el cuerpo de cada PR, que
  cuenta el **por que** en lugar de resumir el codigo -eso ya lo cuenta el diff-. Vara: si borras la
  slice, ¿que queda roto o imposible? Si no puedes nombrarlo, la linea es relleno. No hay exencion,
  a diferencia de `SENAL:`. Si un issue viejo no la trae, la PR la reconstruye y **declara que la
  infirio**.
- **La PR solo lleva el codigo de la slice**: el commit stagea unicamente los ficheros de
  codigo/test de la slice (`git add` explicito, nunca `-A`/`.`); planes y design-docs jamas entran
  en la PR (la spec vive en el issue). Conventional commits con el `name` de la slice como scope
  (`feat(name): ...`); la PR referencia el issue con `Part of #N`.
- **Cada slice tiene nombre**: `name` kebab-case en la spec; alimenta rama (`slice/NN-name`) y
  scope de commit de forma determinista. La skill `slice-spec` produce specs bien formadas.
- **Los controles los declara el issue**: la seccion `## Controles` (pares `nombre: comando`, por repo)
  fija con que se mide cada repo. La descubre `slice-spec` con `discover_controles.py`, la **confirma
  la persona**, y `slice-runner` solo la lee: ningun agente abre un `Makefile` en tiempo de run. Se
  llaman **controles**, no "puertas" -era un calco de *gate*-; el motivo viejo `bloqueada: puertas` se
  sigue parseando porque esta escrito en issues abiertos. Y nadie que juzgue ve output de build: con
  `--out`, la salida de un control fallido va a disco y el orquestador solo reenvia la ruta.
- **La observabilidad es parte de la slice**: cada slice que cambia comportamiento en prod declara
  su linea `SENAL:` (como se comprueba viva; la consume `deploy-watch`), y las exentas lo declaran
  con motivo. La emision de una senal nueva es un criterio de aceptacion mas (test de emision,
  pre-merge); el valor vivo se comprueba post-deploy. Alertas y paneles son **slices propias**, en
  su repo (`REPO:`) y **detras** de la slice que emite la serie. El cerebro esta en
  `skills/slice-spec/references/observabilidad.md`.
- **Una slice puede vivir en otro repo**: `REPO:` fija el repo destino y **todo** el ciclo ocurre ahi
  (comandos, rama, controles, PR, CI), medido con la vara de **ese** repo (su subseccion `### org/repo` en
  las fuentes de convencion). El issue sigue siendo uno: una feature = un issue.

## Tras tocar un agente definido

`agents/slice-implementer.md` y `agents/slice-verifier.md` no se releen en caliente: el registro de
agentes se cachea al primer load de la sesion, al contrario que las skills. Si editas uno, **la sesion en
curso sigue usando la version vieja**. Para probarlo hace falta sesion nueva; si no, el smoke valida la
definicion equivocada en silencio.

Los dos son la mitad de "el que implementa no verifica", asi que la metodologia del implementador vive en
su system prompt y **no** se relata desde `slice-runner`: el orquestador solo le pasa los datos del run.
Si anades una regla de como implementar, va en el agente; si es un dato del run, va en el paso 5.

## Verificacion tras tocar los scripts o las skills

```bash
make check   # linting (ruff check + format) + mypy strict + pytest; todo debe estar verde
```

**`make check` tambien cubre los `.md`**, no solo el codigo: `tests/test_skill_contracts.py`
compara los contratos que hoy estan escritos dos veces (motivos de `bloqueada:` en `SKILL.md`
vs `issue_body.py`, veredictos de `metrics.py`, el JSON del verificador en `agents/` y en
`slice-runner`, las herramientas que `src/slice_runner/` concede al juez vs las que declara su
prompt, las claves del hallazgo en la rubrica vs el mapeo `FINDING_CONTRACT_KEYS` del programa, los
veredictos y las severidades de la rubrica vs los que el programa acepta, y el criterio de
degradacion sin subagentes duplicado a proposito en `slice-runner` y `deploy-watch`). Cada test
**extrae** el vocabulario de ambos lados y los compara, asi que reescribir las dos copias a la vez
pasa y tocar solo una falla. Si editas una
skill y `make check` se pone rojo ahi, es que has movido una mitad del contrato: mueve la otra.

Lo compartido por la suite de `tests/` vive en `tests/conftest.py`: la fixture `repo` y los helpers
de escribir/stagear. No vuelvas a definirlos en un fichero de tests -hubo tres `_write` con firmas
distintas a la vez, y leer cualquier test obligaba a subir a la cabecera-.

Lo que comparten **los dos** arboles de test vive en `src/slice_runner/tests/git_repo.py`:
`BASE_BRANCH`, el helper de `git` y el repo recien inicializado, que `tests/conftest.py` importa de
ahi. La direccion es esa porque `src` entra en el `pythonpath` y el directorio de `conftest` no, asi
que `src/slice_runner/tests/` no puede consumir de `tests/` y al reves si. `BASE_BRANCH` se fija
explicitamente (`git init -b`) porque `init.defaultBranch` es config de la maquina y el bloque de
`diff-bundle` se cae en una que use `main`.

`tests/test_skill_contracts.py` comprueba ademas que **toda ruta de este repo citada en los `.md`
existe**, en `test_every_repo_path_cited_in_the_docs_still_exists`. Aqui no se enlaza con markdown:
se citan rutas en backticks, asi que lo que se valida es el token, no el enlace. Solo entran los que
empiezan por un directorio de primer nivel del repo -eso deja fuera por construccion los nombres
sueltos (`controles.py`), las rutas de otros repos y los patrones de rama (`slice/NN-name`)-. Dos
ficheros no se escanean, cada uno por lo que **es**:
`docs/superpowers/specs/` (registro fechado, describe el arbol de su dia) y
`skills/slice-spec/references/observabilidad.md` (documenta rutas de repos ajenos).

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`. El toolchain lo gestiona `uv` (grupo `dev` de `pyproject.toml`), asi que no
hay que instalar nada a mano: `uv run` lo resuelve la primera vez. `python3 -m pytest` tambien
funciona si tienes pytest global, pero `make check` es la vara completa. Para acortar el feedback
loop en una sesion con agente, `make test PYTEST_ARGS="--nf -x --tb=short --disable-warnings
--color=no --no-header"`.

## Convenciones del codigo Python

Las prescribe `backend-engineering:backend-best-practices`, y este repo las cumple entero salvo una
desviacion declarada (`S`, ver abajo). Lo que hay que saber antes de escribir una linea:

- **Cero prosa en los `.py`: ni comentarios ni docstrings.** Nada de `#`, y tampoco docstring de
  modulo, de clase, de funcion ni de atributo. La unica excepcion es el shebang. Si un trozo de
  codigo no se entiende sin un parrafo al lado, **el arreglo es el codigo y no el parrafo**: nombres
  que digan lo que hacen, funciones pequenas con una responsabilidad, tipos que hagan imposible el
  mal uso, constantes con nombre en vez de literales -un `if` que necesitaba tres lineas de
  explicacion es casi siempre una funcion con nombre esperando a nacer, y un invariante que se
  explicaba en prosa es casi siempre un test que falta-. El *por que* va al registro duradero, que
  aqui son el **cuerpo de la pull request** y `docs/`: es lo que se sigue leyendo cuando el fichero
  ya se ha reescrito tres veces.
- **El codigo va en ingles**, no solo los commits y las pull requests: nombres de fichero y de
  modulo, clases, funciones, metodos, variables, parametros, constantes, miembros de enum,
  excepciones, nombres de test, nombres de subcomando, y los mensajes de error que ve una persona.
  Se queda en castellano solo lo que es **dato de un contrato** y no codigo: los valores del
  veredicto del juez (`PASA`/`FALLA`, `alta`/`media`/`baja`) y las claves de su JSON (`regla`,
  `evidencia`...), porque los fija la rubrica de `agents/slice-verifier.md`, los valida
  `skills/slice-runner/scripts/controles.py` y traducirlos rompe el contrato en vez de renombrar
  una variable. **Clave del contrato no es nombre de campo**: los campos del dataclass van en
  ingles y la traduccion vive en un unico mapeo (`FINDING_CONTRACT_KEYS`), que es tambien de donde
  sale el `--json-schema` y lo que el test de contrato compara contra la rubrica -asi el contrato
  se lee en un sitio en vez de estar repartido por cada `to_dict` y cada `from_dict`-. Esto ya
  estaba dicho en `docs/design-notes.md` y aun asi
  `src/slice_runner/` nacio entero en castellano: una convencion escrita donde nadie la carga antes
  de escribir no mide nada, por eso vive aqui.
- **Los dataclasses son `frozen=True, kw_only=True, slots=True`.** Sin excepciones: si algo se
  construia por partes y luego se mutaba, se construye una vez al final o se usa
  `dataclasses.replace`. Es lo que hizo falta en `parse_body` y en `comprueba_higiene_pr`.
- **Nada de `dict` crudo como valor de retorno de logica.** Los `dict[str, object]` que quedan son
  todos frontera de serializacion, y viven en un `to_dict()`. Un `dict` que cruza dos funciones
  propias se lee con `.get()` en el consumidor, y ahi una clave mal escrita y una ausente dan lo
  mismo -era el fallo de `build_scorecard` y de `_slice_info`, que ademas obligaba a tres
  `assert isinstance(...)` en produccion solo para mypy-.
- **El vocabulario cerrado es `StrEnum`**, no tuplas de `str` (`Estado`, `MotivoBloqueada`,
  `EstadoCI`, `Severidad`, `Veredicto`, `Modo`...). Los miembros se serializan como su cadena, asi
  que ni el formato del issue ni el JSON de salida cambian, pero las comparaciones y los `choices`
  de cada CLI salen de un solo sitio. En `argparse`, `choices=[str(x) for x in Enum]`: con
  `list(Enum)` el mensaje de error muestra el `repr` del miembro.
- **Lo que llega de fuera se valida al entrar.** El payload de `deploy_core` y las filas del log de
  `metrics` se convierten a dataclass en un `from_dict`/`from_row` que rechaza clave desconocida y
  tipo equivocado. Nada de `cast`: un `cast` no comprueba, solo calla a mypy.

**Las dos primeras reglas son nuevas y los scripts viejos no las cumplen todavia**: los `.py` de
`skills/` estan en castellano y llenos de docstrings -y una de esas docstrings,
`skills/slice-runner/scripts/controles.py`, es una de las dos copias declaradas del numero de la
ventana de gracia de la CI, asi que borrarla a ciegas tira un contrato-. Rigen para el codigo nuevo,
y `src/slice_runner/` es el primero que las cumple entero. La migracion de los scripts es deuda
declarada y se hace **fichero entero o nada**: media migracion se lee peor que ninguna, asi que lo
que se anada hoy a uno de esos ficheros sigue el estilo de su modulo anfitrion.

Dos decisiones de config que no hay que re-litigar (razonadas en `pyproject.toml`): `ruff` **no**
formatea los `.md` -aqui los `.md` son el producto- y las reglas `S` (bandit) estan **desactivadas**
porque sus hallazgos viven todos en `controles.py`, donde lanzar procesos es el cometido del fichero.

El `select` de `ruff` es el que prescriben las best-practices, y `smoke/fixture/pyproject.toml`
**lleva el mismo**: la fixture es el sujeto que trocea el runner en el smoke, asi que relajarla ahi
le daria al runner un aprobado que no vale. Si tocas uno, toca el otro.

El estado del run vive en el issue de GitHub: no hay panel ni estado local que verificar. La I/O
contra `gh` la valida el smoke real (ver `smoke/README.md`).
