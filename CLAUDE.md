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

## Tras tocar el agente verificador

`agents/slice-verifier.md` no se relee en caliente: el registro de agentes se cachea al primer load de la
sesion, al contrario que las skills. Si lo editas, **la sesion en curso sigue usando la version vieja**.
Para probarlo hace falta sesion nueva; si no, el smoke valida la definicion equivocada en silencio.

## Verificacion tras tocar los scripts

```bash
make check   # linting (ruff check + format) + mypy strict + pytest; todo debe estar verde
```

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`. El toolchain lo gestiona `uv` (grupo `dev` de `pyproject.toml`), asi que no
hay que instalar nada a mano: `uv run` lo resuelve la primera vez. `python3 -m pytest` tambien
funciona si tienes pytest global, pero `make check` es la vara completa.

Dos decisiones de config que no hay que re-litigar (razonadas en `pyproject.toml`): `ruff` **no**
formatea los `.md` -aqui los `.md` son el producto- y las reglas `S` (bandit) estan **desactivadas**
porque sus hallazgos viven todos en `controles.py`, donde lanzar procesos es el cometido del fichero.

El estado del run vive en el issue de GitHub: no hay panel ni estado local que verificar. La I/O
contra `gh` la valida el smoke real (ver `smoke/README.md`).
