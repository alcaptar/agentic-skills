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
- **La PR solo lleva el codigo de la slice**: el commit stagea unicamente los ficheros de
  codigo/test de la slice (`git add` explicito, nunca `-A`/`.`); planes y design-docs jamas entran
  en la PR (la spec vive en el issue). Conventional commits con el `name` de la slice como scope
  (`feat(name): ...`); la PR referencia el issue con `Part of #N`.
- **Cada slice tiene nombre**: `name` kebab-case en la spec; alimenta rama (`slice/NN-name`) y
  scope de commit de forma determinista. La skill `slice-spec` produce specs bien formadas.

## Verificacion tras tocar los scripts

```bash
python3 -m pytest   # logica pura del cuerpo del issue + gates + metrics; debe estar verde
```

El estado del run vive en el issue de GitHub: no hay panel ni estado local que verificar. La I/O
contra `gh` la valida el smoke real (ver `smoke/README.md`).
