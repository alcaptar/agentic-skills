# Notas de diseno

Decisiones tomadas al construir estas skills y el porque, para poder seguir iterando sin re-derivarlo.

## Contexto

Flujo de trabajo objetivo: escribo specs; cada slice de la spec quiero que se implemente sola, se valide, se abra PR y se confirme CI verde; y tras aprobar, monitorizar el despliegue. Encaja con "loop engineering" (assess -> act -> verify -> stop) y spec-driven development.

## slice-runner

### Decisiones clave

- **Nivel 1 por defecto** (una slice por invocacion, para maximo control). Nivel 2 = envolver en `/loop`. Nivel 3 = Workflow fan-out (no construido; solo para slices independientes).
- **Un formato de spec**: checklist (`## Slices`, una linea `- [ ] slice-NN (name): ...` por slice). Hubo un segundo formato (plan de una slice estilo superpowers, el fichero entero = 1 slice) para consumir `docs/superpowers/plans/*.md` de un repo real; se **elimino** porque el flujo canonico (slice-spec -> slice-runner) siempre emite el checklist, y el Formato B no aportaba poder expresivo pero si superficie transversal (deteccion, derivacion de AC, contrato duplicado en 3 sitios). Ver `docs/superpowers/specs/2026-07-22-formato-unico-y-tests-deterministas-design.md`.
- **Autodeteccion de comandos con Makefile primero.** Muchos repos corren todo en Docker via `make` (`make test`, `make check-types`, `make fastapi-migrate`...); lanzar `pytest`/`ruff` directos falla.
- **Convenciones del repo como vara de medir principal**, `backend-best-practices` como secundaria, default generico al final. No es invento: replica la jerarquia de autoridad que declara el `CLAUDE.md` de los repos (convenciones > skill > default). Implementador y verificador cargan ambas.
- **TDD consciente de capa.** Test-first por AC en capas con test; en capas eximidas por convencion (modelos ORM, migraciones alembic) la puerta es "suite intacta + efecto verificado", no test-first. El repo decide.
- **Gate de check-alignment** antes de implementar (mostrar entendimiento, esperar go/no-go). Evita transcribir a ciegas el codigo pre-horneado de una spec. En un dry-run real este gate detecto que una slice ya estaba mergeada y aborto antes de romper la cadena de alembic.
- **El ciclo TDD se delega en superpowers, los deltas se quedan** (decision 2026-07-27): `slice-runner` reescribia de su cuenta el ciclo red-green-refactor y la integridad de tests, que `superpowers:test-driven-development` ya cubre; esa prosa duplicada se desincroniza (superpowers lo mantiene un tercero, va por la 6.2.0). Ahora el implementador **invoca** esa skill y en `slice-runner` viven solo los deltas: exencion por capa, integridad de tests **preexistentes**, refactor tras cada verde, y el esfuerzo en la calidad del test. Como su Iron Law ("no production code without a failing test") contradice la exencion de capa, se declara la precedencia explicita **convenciones del repo > exencion de capa > Iron Law** (sin eso, `selective-hearing`: gana la regla que mas suena en el entrenamiento). Se anade el principio **"los tests son ciudadanos de primera categoria"**, que cita los checks de severidad alta del paso 6 en vez de repetirlos. Fuera de alcance: `verification-before-completion` (las puertas ya son deterministas con exit code autoritativo; anadir su prosa no cambiaria comportamiento). Ver `docs/superpowers/specs/2026-07-27-desduplicar-slice-runner-superpowers-design.md`.
- **Verificador reenfocado a review de convenciones/arquitectura, no re-testeo.** Ejecuta las puertas deterministas pero su juicio va a convenciones, boundaries y constraints.
- **test-desiderata** en el verificador: bloquea solo lo grave (no determinista, no aislado, test que no verifica comportamiento); lo menor informa. Se salta en slices sin tests.
- **Refactor tras cada verde** en el implementador.
- **No hace merge.** Para en "PR abierto + CI verde". Merge humano.
- **Contexto fresco por slice** (patron Ralph): cada slice arranca limpia; el **issue de GitHub** (spec + estado) es lo que persiste y se re-lee al empezar. Hace seguro el Nivel 2.
- **Estado del run en el issue de GitHub** (decision 2026-07-23): la spec y el estado de cada slice viven en el cuerpo de un issue (1 feature = 1 issue), unica fuente de verdad viva y duradera. Sustituye al estado local anterior (`.slice-runner/` con `runs.jsonl`/`state.json`/`stream.log` + un panel TUI), que se **elimino**: el seguimiento pasa a ser publico y colaborativo, sin infra local. `slice-runner` reescribe la linea de la slice en cada transicion (logica pura en `scripts/issue_body.py`, I/O en `gh`); `deploy-watch` comenta su veredicto. Ver `docs/superpowers/specs/2026-07-23-specs-como-issues-de-github-design.md`.
- **Metricas durables fuera del repo**: `~/.claude/slice-runner/metrics.jsonl` (append-only, no versionado, sobrevive al descarte) para medir "cuando subir de nivel". Lo escribe/agrega `scripts/metrics.py`.
- **Coste**: presupuesto de tokens/$ por slice como circuit breaker adicional; metrica = coste por slice mergeada (no por intentada). Motivado por el research (coste hasta 30x impredecible, Stanford). El coste vive en las metricas durables (`~/.claude/slice-runner/metrics.jsonl`), fuera del repo.

### Por que estas decisiones (fuentes)

- **Loop engineering** (Boris Cherny, Addy Osmani, LangChain): assess-act-verify-stop, worktrees para aislar, estado fuera del contexto, escritor != verificador, puertas de parada objetivas, circuit breaker.
  - https://addyosmani.com/blog/loop-engineering/
  - https://www.langchain.com/blog/the-art-of-loop-engineering
- **ai-patterns** (Lada Kesseler et al.): check-alignment (evita silent-misalignment), reference-docs (cargar convenciones on-demand), offload-deterministic (make/gh en vez de juicio del modelo), context-markers (el testigo `[slice-runner]`), feedback-flip / focused-agent (verificador adversarial), reminders (lista de no negociables).
- **Bryan Finster, "Agentic Workflows: Do Agents Work?"** (empirico, 5 experimentos con coste medido):
  - Small batches ganan; requisitos claros son innegociables (valida check-alignment).
  - **Refactor tras cada verde** es el driver de calidad, no el orden test-first -> por eso se anadio como paso explicito.
  - Test-first no aporta medible en agentes -> ANOTADO, pero se mantiene TDD estricto porque el `CLAUDE.md` del repo lo manda (gana la convencion). Revisable si el repo cambia.
  - Split authorship costo 3x sin ganancia consistente porque los AC ocultos ya gobernaban -> por eso el verificador se reenfoca a convenciones/arquitectura (que Finster no midio) en vez de re-testear.
  - No sobre-testear (mutation scores altos en los peores workflows) -> respalda test-desiderata "bloquea solo lo grave".
  - https://bryanfinster.substack.com/p/agentic-workflows-do-agents-work

### Ideas para iterar (no construidas)

- Chequeo de independencia entre slices (solape de ficheros/migraciones) para habilitar paralelo seguro.
- Nivel 3 con Workflow fan-out: N implementadores en worktrees, aislamiento de entorno de test por worktree (COMPOSE_PROJECT_NAME/puertos), estrategia de orden de merge (serializar quien toque alembic).
- Convencion para archivar/marcar planes ya entregados y que el selector de "siguiente slice" no tropiece con specs stale.

## deploy-watch

### Decisiones clave

- **Fase post-approve, invocacion manual, read-only sobre prod.** Disparador manual elegido para cero polling en vacio.
- **Compone, no reinventa**: el agente orquesta por tick las skills de observabilidad (catalogo abierto) + agente `sre`; la decision la hace un core puro (`deploy_core.py`: umbrales relativos, confirmacion sostenida, scorecard, veredicto). Antes delegaba en una skill `deploy-monitor` suelta (script HTTP bloqueante), **absorbida en 2026-07-23**; ver `docs/superpowers/specs/2026-07-23-deploy-watch-absorbe-el-monitor-design.md`.
- **Veredicto por 4 senales**: rollout k8s, recursos (OOM/restarts/CPU), errores/latencia HTTP vs baseline, Sentry (issues nuevas del release). Sano solo si las 4 estan ok toda la ventana de estabilizacion.
- **Ante anomalia**: agente `sre` para RCA read-only + rollback redactado (git revert del merge + redeploy segun slicing.md), sin ejecutar.
- **Seguridad**: nunca ejecuta rollback ni toca backends; max_runtime + circuit breaker; merge y rollback los decide el usuario.

## Roadmap de autonomia (pendiente)

Estado actual: **Nivel 1** — una slice por invocacion, todo bajo control manual. Subir de nivel solo cuando el anterior sea fiable; el cuello de botella nunca es implementar, es la calidad del gate de verificacion.

- **Nivel 2 — semi-autonomo con `/loop`.** Envolver slice-runner en `/loop`: al terminar una slice (PR + CI verde), coge la siguiente pendiente sola. Guardrails a anadir antes de activarlo:
  - Circuit breaker: `max_consecutive_failures` (parar tras N slices bloqueadas seguidas).
  - `max_runtime` / tope de slices por sesion (evitar loop eterno).
  - Checkpoint humano opcional entre slices.
  - Requisito previo: confianza en el verificador; es lo que sostiene el loop sin supervision.
- **Nivel 3 — Workflow fan-out (paralelo).** Solo para slices independientes. Requiere: chequeo de independencia (solape de ficheros/migraciones), aislamiento de entorno de test por worktree (`COMPOSE_PROJECT_NAME`/puertos), y orden de merge (serializar quien toque el head de alembic).
- **Encadenar slice-runner -> deploy-watch.** Tras el merge, disparar deploy-watch automaticamente. Hoy deploy-watch es manual por decision (cero polling en vacio); la version encadenada poll-earia el estado del PR/merge para arrancar sola.
- **deploy-watch autonomo.** Opcion descartada de momento: un `/loop` que vigila el merge y arranca la monitorizacion solo. Reconsiderar si el volumen de slices crece.

## Preferencias transversales

- Respuestas y skills sin emojis (preferencia del usuario) -> el testigo de contexto es un marcador de texto `[skill-name]`, no un emoji.
- Idioma: cuerpo de las skills y comunicacion en castellano; codigo/commits/PRs en ingles (convencion de los repos).
