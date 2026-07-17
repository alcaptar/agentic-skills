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
                     abre PR, espera CI verde, y para
  -> (tu apruebas y mergeas: el merge es humano)
  -> [deploy-watch]  baseline + 4 senales (rollout k8s, recursos, HTTP, Sentry)
                     veredicto sano | RCA (agente sre) + rollback redactado
```

### slice-runner

Nivel 1 (una slice por invocacion; envolver en `/loop` para Nivel 2). Soporta dos formatos de spec:
- **A) checklist** `## Slices` con `- [ ]` por slice.
- **B) plan de una sola slice** estilo superpowers (el fichero = 1 slice).

Puertas antes de abrir PR: convenciones del repo -> `backend-best-practices` -> TDD por capa -> `test-desiderata` -> constraints/boundaries -> lint/types/tests -> CI verde. No hace merge.

### deploy-watch

Fase post-approve, manual, read-only sobre prod. Compone la skill `deploy-monitor` (motor baseline+poll+CSV) + skills de observabilidad (prometheus, elasticsearch, sentry, gcloud-logs) + agente `sre`. Nunca ejecuta rollback: lo redacta para que lo lances tu.

## Principios comunes

- Escritor != verificador, pero el verificador **revisa convenciones/arquitectura, no re-testea** (CI + AC gobiernan la correccion).
- Puertas de parada objetivas y deterministas.
- Convenciones del repo como vara de medir principal.
- Estado en el repo (el checklist de la spec es el fichero de estado).
- Control humano en los puntos de riesgo: merge y rollback.

Ver `docs/design-notes.md` para el detalle y las fuentes.
