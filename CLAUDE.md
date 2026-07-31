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
`slice-runner`, y el criterio de degradacion sin subagentes duplicado a proposito en
`slice-runner` y `deploy-watch`). Cada test **extrae** el vocabulario de ambos lados y los
compara, asi que reescribir las dos copias a la vez pasa y tocar solo una falla. Si editas una
skill y `make check` se pone rojo ahi, es que has movido una mitad del contrato: mueve la otra.

Lo compartido por la suite vive en `tests/conftest.py`: la fixture `repo` y los helpers de
escribir/stagear. No vuelvas a definirlos en un fichero de tests -hubo tres `_write` con firmas
distintas a la vez, y leer cualquier test obligaba a subir a la cabecera-. Ahi tambien esta
`RAMA_BASE`: los repos de prueba fijan su rama con `git init -b`, porque `init.defaultBranch` es
config de la maquina y el bloque de `diff-bundle` se cae en una que use `main`.

El mismo fichero comprueba que **toda ruta de este repo citada en los `.md` existe**. Aqui no se
enlaza con markdown: se citan rutas en backticks, asi que lo que se valida es el token, no el
enlace. Solo entran los que empiezan por un directorio de primer nivel del repo -eso deja fuera
por construccion los nombres sueltos (`controles.py`), las rutas de otros repos y los patrones de
rama (`slice/NN-name`)-. Dos ficheros no se escanean, cada uno por lo que **es**:
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

- **Cero comentarios en los `.py`.** El *por que* va en docstrings -de modulo, de funcion, o de
  atributo justo debajo de la constante que explica-, no en `#`. La unica excepcion es el shebang.
  Que el rationale viva en el docstring es lo que hace que se lea desde fuera (`help()`, el editor)
  en vez de solo al abrir el fichero por la linea correcta.
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

Dos decisiones de config que no hay que re-litigar (razonadas en `pyproject.toml`): `ruff` **no**
formatea los `.md` -aqui los `.md` son el producto- y las reglas `S` (bandit) estan **desactivadas**
porque sus hallazgos viven todos en `controles.py`, donde lanzar procesos es el cometido del fichero.

El `select` de `ruff` es el que prescriben las best-practices, y `smoke/fixture/pyproject.toml`
**lleva el mismo**: la fixture es el sujeto que trocea el runner en el smoke, asi que relajarla ahi
le daria al runner un aprobado que no vale. Si tocas uno, toca el otro.

El estado del run vive en el issue de GitHub: no hay panel ni estado local que verificar. La I/O
contra `gh` la valida el smoke real (ver `smoke/README.md`).
