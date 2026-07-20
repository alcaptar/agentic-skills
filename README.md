# agentic-skills

Skills personales de Claude Code para automatizar el flujo **spec -> slice -> PR -> CI verde -> monitorizacion de despliegue** (loop engineering).

No es de la organizacion: de momento, uso personal.

## Estructura

```
skills/
  slice-runner/    SKILL.md   Ejecuta una slice de una spec de principio a fin
  deploy-watch/    SKILL.md   Monitoriza el despliegue tras aprobar la PR
docs/
  design-notes.md             Decisiones de diseno y el porque (para seguir iterando)
  research-agent-loops.md     Research citado sobre loops autonomos de agentes
  maturity-map.md             Donde encaja el pipeline (Steps of AI Adoption, Cherny)
smoke/                        Smoke test autocontenido para validar slice-runner (ver smoke/README.md)
```

## Fuente de verdad y symlinks

**Este repo es la fuente de verdad.** Las skills viven aqui y `~/.claude/skills/` apunta a ellas por symlink, asi que se editan versionadas y siguen activas en Claude Code.

Recrear los symlinks (p. ej. en otra maquina) tras clonar:

```bash
ln -s "$PWD/skills/slice-runner" ~/.claude/skills/slice-runner
ln -s "$PWD/skills/deploy-watch" ~/.claude/skills/deploy-watch
```

## El pipeline

```
spec.md
  -> [slice-runner]  implementa (TDD por capa + refactor tras verde)
                     verifica (convenciones del repo + boundaries + test-desiderata)
                     abre PR, espera CI verde (ticks en background, sin shell bloqueante)
                     y queda "waiting: merge" vigilando la PR
  -> (tu mergeas en GitHub: el merge sigue siendo humano)
  -> [deploy-watch]  se encadena AUTO al detectar el merge; arranca sola
                     baseline + 4 senales (rollout k8s, recursos, HTTP, Sentry)
                     veredicto sano (marca la slice validada en deploy)
                     | degradado -> RCA (agente sre) + rollback redactado
```

### slice-runner

Nivel 1 (una slice por invocacion; envolver en `/loop` para Nivel 2). Soporta dos formatos de spec:
- **A) checklist** `## Slices` con `- [ ]` por slice.
- **B) plan de una sola slice** estilo superpowers (el fichero = 1 slice).

Puertas antes de abrir PR: convenciones del repo -> `backend-best-practices` -> TDD por capa -> `test-desiderata` -> constraints/boundaries -> lint/types/tests -> CI verde. No hace merge. Por defecto trabaja en una **rama normal** (no asume worktree; solo lo usa si se paralelizan slices). Tras CI verde queda **vigilando la PR** (`waiting: merge`) y, al detectar el merge, encadena `deploy-watch` automaticamente. Las esperas (CI, merge) son ticks en background, nunca una shell bloqueante.

### deploy-watch

Fase post-approve, read-only sobre prod. Se **encadena automaticamente** al detectar el merge (o se invoca a mano) y **arranca sola**: infiere servicio/namespace y solo pregunta si hay duda real. Compone la skill `deploy-monitor` (motor baseline+poll+CSV) + skills de observabilidad (prometheus, elasticsearch, sentry, gcloud-logs) + agente `sre`. El poll de estabilizacion son ticks en background. Un veredicto `sano` marca la slice como **validada en deploy**. Nunca ejecuta rollback: lo redacta para que lo lances tu.

## Seguimiento en vivo (ledger + stream + panel)

Ambas skills escriben en `.slice-runner/` del repo objetivo:
- `runs.jsonl` (versionado): una linea por slice con estado, coste (tokens/$), PR, CI y veredicto de deploy. Es la memoria del contexto fresco y la fuente del coste-por-slice-mergeada.
- `state.json` (gitignored): estado vivo (spec_path, slice en curso, fase) para que el panel muestre las pendientes y si esta `waiting: merge`.
- `stream.log` (gitignored): stream en vivo con fecha completa. `tail -f .slice-runner/stream.log`.

Panel de estado (TUI) que agrega spec + ledger + stream en una tabla live:

```bash
python3 panel/slice-panel.py /ruta/al/repo        # live (Ctrl+C sale)
```

Muestra **todas** las slices (incluidas las pendientes de la spec), una columna **DEPLOY** (validada en prod) y un banner cuando esta **esperando una decision tuya**. Cubre el **estado**; el consumo de tokens/$ en tiempo real sale de la telemetria de Claude Code (OTel -> Grafana), no de las skills. Ver `panel/README.md`.

## Principios comunes

- Escritor != verificador, pero el verificador **revisa convenciones/arquitectura, no re-testea** (CI + AC gobiernan la correccion).
- Puertas de parada objetivas y deterministas.
- Convenciones del repo como vara de medir principal.
- Estado en el repo (el checklist de la spec es el fichero de estado).
- Control humano en los puntos de riesgo: merge y rollback.

Ver `docs/design-notes.md` para el detalle y las fuentes.
