# agentic-skills

Skills personales de Claude Code para automatizar el flujo **idea -> spec -> slice -> PR -> CI verde -> monitorizacion de despliegue** (loop engineering).

No es de la organizacion: de momento, uso personal.

## Estructura

```
skills/
  slice-spec/      SKILL.md   Crea/valida la spec de slices (envuelve brainstorming)
  slice-runner/    SKILL.md   Ejecuta una slice de una spec de principio a fin
    scripts/                  issue_body.py (estado en el issue), gates.py, metrics.py
  deploy-watch/    SKILL.md   Monitoriza el despliegue tras aprobar la PR
docs/
  design-notes.md             Decisiones de diseno y el porque (para seguir iterando)
  research-agent-loops.md     Research citado sobre loops autonomos de agentes
  maturity-map.md             Donde encaja el pipeline (Steps of AI Adoption, Cherny)
  superpowers/specs/          Design-docs de brainstorming (uno por cambio)
tests/                        Unit tests offline de la logica pura (issue_body, gates, metrics)
smoke/                        Smoke test real contra GitHub (ver smoke/README.md)
```

## Fuente de verdad y symlinks

**Este repo es la fuente de verdad.** Las skills viven aqui y `~/.claude/skills/` apunta a ellas por symlink, asi que se editan versionadas y siguen activas en Claude Code.

Recrear los symlinks (p. ej. en otra maquina) tras clonar:

```bash
ln -s "$PWD/skills/slice-spec" ~/.claude/skills/slice-spec
ln -s "$PWD/skills/slice-runner" ~/.claude/skills/slice-runner
ln -s "$PWD/skills/deploy-watch" ~/.claude/skills/deploy-watch
```

## El pipeline

```
idea
  -> [slice-spec]    brainstorming + crea un issue de GitHub con la spec de slices (name + AC)
issue de GitHub (1 feature = 1 issue; estado de cada slice en su linea)
  -> [slice-runner]  implementa (TDD por capa + refactor tras verde)
                     verifica (convenciones del repo + boundaries + test-desiderata)
                     abre PR (Part of #N), espera CI verde (ticks en background)
                     marca la slice "esperando-merge" en el issue y vigila la PR
  -> (tu mergeas en GitHub: el merge sigue siendo humano; la slice pasa a [x] mergeada)
  -> [deploy-watch]  se encadena AUTO al detectar el merge; arranca sola
                     baseline + 4 senales (rollout k8s, recursos, HTTP, Sentry)
                     comenta el veredicto en el issue
                     | degradado -> RCA (agente sre) + rollback redactado
```

### slice-spec

Convierte una idea en una **spec bien formada** que `slice-runner` sabe ejecutar. Envuelve
`superpowers:brainstorming` para el diseno y luego emite el formato exacto (checklist de slices)
con un **nombre kebab-case por slice** y AC. Modo `validate` para revisar una spec existente contra el
contrato. No implementa codigo: **crea el issue de GitHub** con la spec (1 feature = 1 issue).

### slice-runner

Nivel 1 (una slice por invocacion; envolver en `/loop` para Nivel 2). La spec es un **checklist de
slices**: `## Slices` con una linea `- [ ] slice-NN (name): ...` por slice y sus AC. Una feature de
una sola slice es un checklist con una unica linea.

La spec y el estado de cada slice viven en el **issue de GitHub** (unica fuente de verdad). Cada slice
tiene **nombre**: alimenta la rama (`slice/NN-name`) y el scope de conventional commit
(`feat(name): ...`). Puertas antes de abrir PR: convenciones del repo -> `backend-best-practices` ->
TDD por capa -> `test-desiderata` -> constraints/boundaries -> lint/types/tests -> CI verde. **La PR
solo lleva el codigo de la slice**: se stagean unicamente los ficheros que produjo el implementador,
nunca planes ni design-docs (la spec vive en el issue), y referencia el issue con `Part of #N`. No hace
merge. Por defecto trabaja en una **rama normal** (no asume worktree; solo lo usa si se paralelizan
slices). Tras CI verde marca la slice **esperando-merge** en el issue y vigila la PR; al detectar el
merge la marca **`[x]` mergeada** y encadena `deploy-watch`. Las esperas (CI, merge) son ticks en
background, nunca una shell bloqueante. No hay estado local que descartar: el estado vive en el issue.

### deploy-watch

Fase post-approve, read-only sobre prod. Se **encadena automaticamente** al detectar el merge (o se invoca a mano) y **arranca sola**: infiere servicio/namespace y solo pregunta si hay duda real. Compone la skill `deploy-monitor` (motor baseline+poll+CSV) + skills de observabilidad (prometheus, elasticsearch, sentry, gcloud-logs) + agente `sre`. El poll de estabilizacion son ticks en background. **Comenta su veredicto** (sano/degradado/inconcluso, con tabla vs baseline) en el issue de la feature. Nunca ejecuta rollback: lo redacta para que lo lances tu.

## Seguimiento (issue de GitHub)

El estado del run vive en el **cuerpo del issue** de la feature (1 feature = 1 issue), unica fuente
de verdad. No hay estado local (`.slice-runner/`, ledger, panel): cada slice muestra su estado en su
linea del checklist, y cualquiera con acceso al repo lo ve en todo momento.

- `- [ ] slice-NN (name): titulo [estado] PR #M` — el marcador `[estado]` va de `pendiente` a
  `en-curso`, `esperando-merge`, `mergeada` (`[x]`), o `bloqueada`/`abortada`.
- `slice-runner` reescribe solo la linea de la slice en cada transicion (`gh issue edit`);
  `deploy-watch` comenta el veredicto del deploy.
- La logica de parseo/reescritura del cuerpo es pura y testeable (`scripts/issue_body.py`); la I/O
  contra `gh` la valida el smoke real.

El consumo de tokens/$ sale de la telemetria de Claude Code (OTel -> Grafana), no de las skills. Las
metricas del loop (tasa de FALLA, reintentos...) viven fuera del repo en
`~/.claude/slice-runner/metrics.jsonl`.

## Principios comunes

- Escritor != verificador, pero el verificador **revisa convenciones/arquitectura, no re-testea** (CI + AC gobiernan la correccion).
- Puertas de parada objetivas y deterministas.
- Convenciones del repo como vara de medir principal.
- Estado del run en el **issue de GitHub**: la spec y el estado de cada slice viven en el issue (unica fuente de verdad); el registro duradero son el issue y las PRs mergeadas.
- La PR solo lleva el codigo de la slice (conventional commits, `name` como scope, `Part of #N`).
- Control humano en los puntos de riesgo: merge y rollback.

Ver `docs/design-notes.md` para el detalle y las fuentes.
