# Notas de diseno

Decisiones tomadas al construir estas skills y el porque, para poder seguir iterando sin re-derivarlo.

## Contexto

Flujo de trabajo objetivo: escribo specs; cada slice de la spec quiero que se implemente sola, se valide, se abra PR y se confirme CI verde; y tras aprobar, monitorizar el despliegue. Encaja con "loop engineering" (assess -> act -> verify -> stop) y spec-driven development.

## slice-runner

### Decisiones clave

- **Nivel 1 por defecto** (una slice por invocacion, para maximo control). Nivel 2 = envolver en `/loop`. Nivel 3 = Workflow fan-out (no construido; solo para slices independientes).
- **Dos formatos de spec**: checklist (`## Slices`) y plan de una slice estilo superpowers. Detectados en el paso 1. Surgio al probar con `docs/superpowers/plans/*.md` de un repo real, donde el fichero entero era una sola slice.
- **Autodeteccion de comandos con Makefile primero.** Muchos repos corren todo en Docker via `make` (`make test`, `make check-types`, `make fastapi-migrate`...); lanzar `pytest`/`ruff` directos falla.
- **Convenciones del repo como vara de medir principal**, `backend-best-practices` como secundaria, default generico al final. No es invento: replica la jerarquia de autoridad que declara el `CLAUDE.md` de los repos (convenciones > skill > default). Implementador y verificador cargan ambas.
- **TDD consciente de capa.** Test-first por AC en capas con test; en capas eximidas por convencion (modelos ORM, migraciones alembic) la puerta es "suite intacta + efecto verificado", no test-first. El repo decide.
- **Gate de check-alignment** antes de implementar (mostrar entendimiento, esperar go/no-go). Evita transcribir a ciegas el codigo pre-horneado de una spec. En un dry-run real este gate detecto que una slice ya estaba mergeada y aborto antes de romper la cadena de alembic.
- **Verificador reenfocado a review de convenciones/arquitectura, no re-testeo.** Ejecuta las puertas deterministas pero su juicio va a convenciones, boundaries y constraints.
- **test-desiderata** en el verificador: bloquea solo lo grave (no determinista, no aislado, test que no verifica comportamiento); lo menor informa. Se salta en slices sin tests.
- **Refactor tras cada verde** en el implementador.
- **No hace merge.** Para en "PR abierto + CI verde". Merge humano.

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
- **Compone, no reinventa**: `deploy-monitor` (baseline+poll+CSV+stream) + observabilidad + agente `sre`.
- **Veredicto por 4 senales**: rollout k8s, recursos (OOM/restarts/CPU), errores/latencia HTTP vs baseline, Sentry (issues nuevas del release). Sano solo si las 4 estan ok toda la ventana de estabilizacion.
- **Ante anomalia**: agente `sre` para RCA read-only + rollback redactado (git revert del merge + redeploy segun slicing.md), sin ejecutar.
- **Seguridad**: nunca ejecuta rollback ni toca backends; max_runtime + circuit breaker; merge y rollback los decide el usuario.

## Preferencias transversales

- Respuestas y skills sin emojis (preferencia del usuario) -> el testigo de contexto es un marcador de texto `[skill-name]`, no un emoji.
- Idioma: cuerpo de las skills y comunicacion en castellano; codigo/commits/PRs en ingles (convencion de los repos).
