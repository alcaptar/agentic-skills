# agentic-skills — instrucciones del repo

Este repo es la **fuente de verdad** de skills personales de Claude Code (`slice-spec`,
`slice-runner`, `deploy-watch`). Las skills viven aqui y `~/.claude/skills/` apunta por symlink,
asi que editar aqui cambia el comportamiento activo de Claude Code.

## Regla critica: convenciones primero

**ANTES de proponer cualquier cambio de codigo, incluidos los tests:**

1. **IDENTIFICAR** la capa afectada en la tabla de abajo.
2. **LEER** con la herramienta Read el fichero de `docs/conventions/` que le corresponde, en esta
   sesion. No vale recordarlo de otra.
3. **APLICAR** lo que dice, literalmente.
4. **NO** asumir, no improvisar, no traer patrones de otros proyectos.

Esto no es burocracia: es la unica forma que ha funcionado. La convencion del ingles llevaba meses
escrita en `docs/design-notes.md` y `src/slice_runner/` **nacio entero en castellano** de todas formas,
porque nadie la cargaba antes de escribir. Una convencion que no se lee no mide nada.

### Convenciones por capa

**Siempre**, antes de cualquier cambio de codigo: `docs/conventions/code-style.md`.

| Si vas a tocar... | Leer |
|---|---|
| Estructura de carpetas, dependencias, herramientas | `docs/conventions/architecture.md` |
| Value objects, puertos, excepciones, enums | `docs/conventions/domain.md` |
| Casos de uso | `docs/conventions/application.md` |
| Adaptadores, modelos de frontera, entrypoints | `docs/conventions/infrastructure.md` |
| Tests, mothers, dobles, marcadores, contratos entre `.md` | `docs/conventions/testing.md` |
| Ramas, commits, pull requests, merge | `docs/conventions/git-workflow.md` |
| Una convencion de `docs/conventions/` | `docs/conventions/como-se-escribe.md` |
| Una skill, un script de skill o un agente | las dos skills del apartado siguiente |

### Quien lee cada cosa

No todo lo que vive en `docs/` mide lo mismo ni se lo lee el mismo. Confundirlo es lo que hace que al
implementador le lleguen de golpe las reglas del codigo, el flujo de trabajo de una persona y la
historia del proyecto.

| Que es | Donde vive | Quien lo lee |
|---|---|---|
| **La vara del codigo** | `code-style`, `architecture`, `domain`, `application`, `infrastructure`, `testing` | El implementador antes de escribir y el juez antes de bloquear. Es lo unico que viaja en las fuentes de convencion de un issue |
| **Como se trabaja aqui** | `git-workflow.md`, este `CLAUDE.md` | Tu y yo en sesion. **No** el implementador: tiene prohibido tocar `git` |
| **Por que es asi** | `docs/design-notes.md` y las pull requests mergeadas | Quien necesita no re-derivar una decision. Nunca es vara de nada |

### Jerarquia de autoridad

1. **Las convenciones de `docs/conventions/`** — prevalecen siempre.
2. **`backend-engineering:backend-best-practices`** — completa lo que las convenciones no cubren.

En caso de contradiccion, ganan las convenciones de este repo. Las desviaciones respecto a la vara
secundaria estan **declaradas con su motivo** en el fichero de la capa que corresponda; si encuentras
una sin declarar, es un fallo y hay que declararla o corregirla, no ampliarla por precedente.

### Codigo que NO es referencia

Estos ficheros preceden a las convenciones actuales. **No los imites al escribir codigo nuevo**, ni
siquiera como "ejemplo del repo":

- `skills/slice-runner/scripts/` y `skills/deploy-watch/scripts/` — en castellano y llenos de
  docstrings.
- `tests/` — todavia function-based y en castellano.

`src/slice_runner/` es el primero que cumple las convenciones enteras: **ese es el ejemplo**. La
migracion de lo demas es deuda declarada y se hace **fichero entero o nada**: media migracion se lee
peor que ninguna, asi que lo que se anada hoy a uno de esos ficheros sigue el estilo de su modulo
anfitrion.

## Antes de tocar una skill (obligatorio)

Cuando vayas a **crear o modificar** una skill, sus scripts o los docs de este repo, carga primero
estas skills y trabaja segun ellas:

1. **`ai-patterns`** — el vocabulario y los patrones sobre los que estan construidas estas skills
   (`offload-deterministic`, `check-alignment`, `context-management`, `reference-docs`,
   `knowledge-composition`, `silent-misalignment`, `ai-slop`, `text-native`...). Usa esos nombres en el
   texto de las skills y respeta los patrones; no reinventes conceptos que ya tienen nombre.
2. **`superpowers:brainstorming`** — para cualquier cambio de diseno o de comportamiento, antes de
   editar: entiende la intencion, propon enfoques y valida el diseno. (El usuario puede saltarse el
   spec/plan si lo dice explicitamente.)

Para cambios triviales (typo, formato) no hace falta el ritual completo, pero manten la coherencia con
`ai-patterns`.

## Principios que no se rompen

Estos no son convenciones de codigo: son las invariantes del pipeline, y valen en cualquier sesion.

- **El que implementa no verifica** (subagentes distintos; el verificador es adversarial y revisa
  convenciones/arquitectura, no re-testea).
- **Control humano en los puntos de riesgo**: el merge y el rollback los decide el usuario.
- **Esperas no bloqueantes**: ninguna skill lanza shells bloqueantes largas (`--watch`, `sleep`
  largos); las esperas son ticks acotados en background + notificacion. **Y el programa no queda
  fuera**: al orquestador se le relajo sondear -un bucle de sondeo no congela ninguna sesion ni gasta
  contexto-, pero no el tope. Toda llamada a un proceso externo lleva **tope por llamada**
  (`Budgets.process_timeout_seconds`, que el entrypoint inyecta en `LocalProcess`), y agotarlo mata al
  hijo y sale con su propio codigo de salida. Una llamada sin tope cuelga el run entero sin
  diagnostico y sin coste acotado, y la vara que lo caza vive en
  `docs/conventions/infrastructure.md`.
- **No asumir worktree**: rama normal por defecto; worktree solo al paralelizar slices.
- **El estado del run vive en el issue de GitHub**: una feature es un **issue padre** y cada slice una
  **subissue** suya, que lleva su spec en el cuerpo y su estado macro en la etiqueta. Es la unica fuente
  de verdad viva y duradera: no hay estado local (`.slice-runner/`, ledger, panel). El registro duradero
  son el issue (intencion + estado) y las PRs mergeadas (codigo), no ficheros de estado en el repo.
- **La intencion se declara y viaja**: el issue abre con `## Intencion` (que esta mal hoy) y cada slice
  lleva su linea `INTENCION:` (el coste de no hacerla). De ahi sale el cuerpo de cada PR, que cuenta el
  **por que** en lugar de resumir el codigo -eso ya lo cuenta el diff-. Vara: si borras la slice, ¿que
  queda roto o imposible? Si no puedes nombrarlo, la linea es relleno. No hay exencion, a diferencia de
  `SENAL:`. Si un issue viejo no la trae, la PR la reconstruye y **declara que la infirio**.
- **La PR solo lleva el codigo de la slice**: el commit stagea unicamente los ficheros de codigo/test
  de la slice (`git add` explicito, nunca `-A`/`.`); planes y design-docs jamas entran en la PR (la spec
  vive en el issue). Conventional commits con el `name` de la slice como scope (`feat(name): ...`). Como
  referencia la PR a su issue depende del flujo: **`Part of #N`** en el viejo, donde el issue es la feature
  entera y una PR es una slice de ella, y **`Closes #<subissue>`** en el formato nuevo, donde cada slice
  tiene su propia subissue y al mergear la cierra GitHub sola (por eso `RunState.MERGED` no lleva etiqueta:
  ver `docs/conventions/domain.md`).
- **Cada slice tiene nombre**: `name` kebab-case en la spec; alimenta rama (`slice/NN-name`) y scope de
  commit de forma determinista. La skill `slice-spec` produce specs bien formadas.
- **Los controles los declara el issue**: la seccion `## Controles` (pares `nombre: comando`, por repo)
  fija con que se mide cada repo. La descubre `slice-spec` con `discover_controles.py`, la **confirma la
  persona**, y `slice-runner` solo la lee: ningun agente abre un `Makefile` en tiempo de run. Se llaman
  **controles**, no "puertas" -era un calco de *gate*-; el motivo viejo `bloqueada: puertas` se sigue
  parseando porque esta escrito en issues abiertos. Y nadie que juzgue ve output de build: con `--out`,
  la salida de un control fallido va a disco y el orquestador solo reenvia la ruta.
- **La observabilidad es parte de la slice**: cada slice que cambia comportamiento en prod declara su
  linea `SENAL:` (como se comprueba viva; la consume `deploy-watch`), y las exentas lo declaran con
  motivo. La emision de una senal nueva es un criterio de aceptacion mas (test de emision, pre-merge);
  el valor vivo se comprueba post-deploy. Alertas y paneles son **slices propias**, en su repo (`REPO:`)
  y **detras** de la slice que emite la serie. El cerebro esta en
  `skills/slice-spec/references/observabilidad.md`.
- **Una slice puede vivir en otro repo**: `REPO:` fija el repo destino y **todo** el ciclo ocurre ahi
  (comandos, rama, controles, PR, CI), medido con la vara de **ese** repo (su subseccion `### org/repo`
  en las fuentes de convencion). La feature sigue siendo un solo issue padre, con su subissue por slice.

## Donde vive la metodologia del implementador y la rubrica del juez

`agents/slice-implementer.md` y `agents/slice-verifier.md` eran agentes definidos del flujo viejo (la
skill `/slice-runner`, retirada). Se retiraron de este repo porque no les quedaba consumidor: la skill
que los citaba ya no vive aqui, y el programa nunca los leyo. Su rastro sigue vivo en
`alcaptar/agentic-skills-legacy` (ver "Instalacion" en `README.md`).

El programa lleva su propia metodologia y su propia rubrica, y es donde va cualquier regla nueva sobre
como implementar o que juzga el verificador: la metodologia del implementador en
`src/slice_runner/infrastructure/slice_implementer_brief.py` -es lo que el programa le manda a
`claude -p`- y la rubrica del juez en `slice_verifier_judge.py` (ver
`docs/conventions/infrastructure.md`). Si es un dato del run y no una regla, va en el paso 5.

## Como se mide un cambio

```bash
make check   # ruff + mypy strict + pytest; todo verde antes de dar nada por terminado
```

Cubre tambien los `.md`: hay contratos escritos dos veces a proposito y tests que los comparan. El
detalle, los targets sueltos, el marcador `integration` y el reparto de los dos arboles de test estan en
`docs/conventions/testing.md`. El estado del run vive en el issue de GitHub, asi que no hay panel ni
estado local que verificar; la entrada/salida contra `gh` la valida el smoke real (`smoke/README.md`).
