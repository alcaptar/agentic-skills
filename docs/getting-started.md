# Primer arranque

Para quien no ha tocado este repo y quiere lanzar su primer run. Cubre desde los requisitos hasta el
comando concreto, y separa lo que hace falta siempre de lo que solo hace falta si vas a usar el flujo
mas antiguo con la skill `/slice-runner`.

## Antes de nada: coste y permisos

- **Coste**: cada slice ejecutada gasta harness real (las llamadas a `claude -p` que alinean, implementan
  y verifican), no una estimacion de tokens: se mide en `~/.claude/slice-runner/metrics.jsonl`, fuera de
  este repo. El run aborta una slice que supere 50 dolares de harness (`abortada:presupuesto`); las
  muestras medidas hasta hoy van de 5.14 a 27.73 dolares (`docs/design-notes.md`).
- **Permisos**: en el flujo del programa (`uv run slice-runner run`), quien implementa la slice corre con
  `--permission-mode bypassPermissions`
  (`src/slice_runner/infrastructure/implementer_invocation.py`): escribe ficheros y ejecuta comandos en la
  maquina de quien lo lanza **sin pedir permiso en cada paso**. En el flujo mas antiguo con la skill
  `/slice-runner`, el implementador es el subagente `agents/slice-implementer.md`, que no declara modo de
  permisos propio: corre con el que ya tenga la sesion que lo lanza. Si vas a dejar que otra persona use
  esto, dile las dos cosas de antemano: si no, le estas dando una sorpresa cara o un susto.

## Requisitos

- **`gh`** autenticado (`gh auth status`) con permiso para crear issues, subissues y pull requests en el
  repo destino.
- **`uv`** instalado: gestiona el entorno y las dependencias de `src/slice_runner/`, no hay que instalar
  nada a mano.
- **Claude Code** instalado y autenticado, con el ejecutable `claude` accesible desde la terminal
  (`claude --version`). El programa y las skills lo invocan por debajo con `claude -p`, sin sesion
  interactiva.
- **Un repo destino clonado en local**, con integracion continua que corra en `pull_request` los mismos
  comandos que vayas a declarar en `## Controles` del issue -si no los corre, nada frena una slice
  rota antes del merge-.
- **Las etiquetas de estado creadas en el repo destino** (siguiente seccion). Es el requisito que revienta
  primero si te lo saltas: sin la etiqueta creada de antemano no puedes ni marcarla a mano al crear la
  subissue, y si `gh issue edit` pide quitar una etiqueta que el repo no tiene, la orden entera falla y no
  la crea sola -el fallback que si crea una etiqueta ausente solo cubre la que se pide anadir, nunca la que
  se pide quitar (`src/slice_runner/infrastructure/gh_run_repository.py`)-, asi que la subissue se queda
  bloqueada sin poder avanzar de estado.
- **Solo si vas a usar el flujo del programa**: la biblioteca de skills de Claude Code (bajo `~/.claude` o
  lo que fije `CLAUDE_CONFIG_DIR`, en `skills/` o en `plugins/`) tiene que tener alcanzables
  `test-desiderata` y `backend-best-practices`. El juez que arranca `uv run slice-runner run`
  (`src/slice_runner/infrastructure/slice_verifier_judge.py`) le ordena correr ambas para dos puntos de su
  rubrica; sin ellas instaladas el run no avisa -corre igual y devuelve un veredicto limpio, porque juzgo
  esos dos puntos con la vara vacia-. El flujo mas antiguo con la skill `/slice-runner` no tiene este
  requisito aparte: usa las skills que ya tenga la sesion que lo lanza.

## Crear las etiquetas de estado en el repo destino

```bash
for etiqueta in \
  estado:pendiente \
  estado:esperando-alineacion \
  estado:en-curso \
  estado:esperando-merge \
  bloqueada:controles \
  bloqueada:higiene \
  bloqueada:verify \
  bloqueada:ci-roja \
  bloqueada:ci-indeterminada \
  abortada:presupuesto; do
  gh label create "$etiqueta" --repo <org>/<repo> --color 5319e7 \
    --description "estado de una slice, escrito por slice-runner" --force
done
```

Sustituye `<org>/<repo>` por el repo destino. `--force` lo hace repetible: si una etiqueta ya existe,
actualiza color y descripcion en vez de fallar. El vocabulario completo vive en
`src/slice_runner/domain/issue_label.py`, y `tests/test_skill_contracts.py` compara este bucle contra ese
enum: si uno cambia sin el otro, `make check` lo dice antes de que una subissue se quede sin etiqueta.

## Que instalar: flujo del programa vs flujo de las skills

Los dos flujos parten del mismo primer paso -la skill `/slice-spec` disena la feature y crea el issue-, y
los dos encadenan `deploy-watch` al mergear una slice cuya senal no este exenta. Eso hace falta
**siempre**, sea cual sea el flujo con el que despues conduzcas la slice:

```bash
ln -s "$PWD/skills/slice-spec" ~/.claude/skills/slice-spec
ln -s "$PWD/skills/deploy-watch" ~/.claude/skills/deploy-watch
```

Lo que sigue **solo** hace falta si vas a conducir la slice con el flujo mas antiguo, la skill
`/slice-runner` orquestando a mano en tu sesion en vez de `uv run slice-runner run`. Si solo quieres el
flujo del programa, no lo instales:

```bash
ln -s "$PWD/skills/slice-runner" ~/.claude/skills/slice-runner
ln -s "$PWD/agents/slice-implementer.md" ~/.claude/agents/slice-implementer.md
ln -s "$PWD/agents/slice-verifier.md" ~/.claude/agents/slice-verifier.md
```

## Primer run, paso a paso

1. Clona este repo y el repo destino en local. Cumple los requisitos de arriba y crea las etiquetas de
   estado en el repo destino.
2. Instala los symlinks que hagan falta segun el flujo que vayas a usar (seccion anterior).
3. Dentro de una sesion de Claude Code, invoca `/slice-spec` y describe la idea. La skill hace
   brainstorming del diseno, trocea en slices y crea el issue padre con sus subissues -confirma contigo
   las fuentes de convencion y los controles del repo destino antes de crear nada-.
4. Desde **este repo** (`uv run` resuelve el programa por el `pyproject.toml` de aqui, no por el del repo
   destino), lanza la primera slice:

   ```bash
   uv run slice-runner run <numero-de-issue> --repo <org>/<repo> --base <rama-base> \
     --worktree <ruta-local-al-repo-destino>
   ```

   Omite `--worktree` solo si el repo destino es este mismo repo (el valor por defecto es `.`).
5. El programa para en la pausa de alineacion y te muestra su entendimiento de la slice. Contesta en la
   subissue con `-GO` para que arranque, o `-REVIEW <correccion>` para corregirlo antes de que toque
   codigo.
6. Cuando abra la pull request y la integracion continua se ponga verde, el programa para esperando el
   merge. Revisala y mergeala tu -eso no lo hace el pipeline-.
7. Al detectar el merge, si la senal de la slice no esta exenta, encadena `deploy-watch` solo, sin que
   tengas que invocar nada.
8. Repite el paso 4 para la siguiente slice del mismo issue -el estado vive en el, asi que una sesion
   nueva no pierde nada-.

El detalle completo del ciclo, los codigos de salida de cada subcomando y el ejemplo con el flujo
anterior de la skill estan en `README.md`.
