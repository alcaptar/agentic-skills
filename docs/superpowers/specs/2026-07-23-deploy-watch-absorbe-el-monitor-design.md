# deploy-watch absorbe el motor de monitorizacion (fin de deploy-monitor)

Fecha: 2026-07-23
Estado: aprobado (a slicing + implementacion; sin fase de plan)

## Problema

`deploy-watch` (en `agentic-skills`) delega el motor de monitorizacion en la skill
`deploy-monitor`, que vive **suelta** en `~/.claude/skills/deploy-monitor` (sin versionar, sin
tests). Analizada, esa skill:

- **Reinventa el acceso a datos**: `monitor_template.py` hace HTTP directo a Prometheus/ES en vez
  de componer las skills de observabilidad (`query-*`) que ya existen.
- **Es bloqueante**: `while True: sleep()` lanzado con `&` + `tail -F` — una shell colgada toda la
  ventana, justo lo que `deploy-watch` prohibe (esperas no bloqueantes).
- **Hardcodea infra Mercadona** (`prometheus.prod.monline`, `elasticsearch.prod.monline`, TZ).
- **Persiste estado local** (CSV/log), cuando la direccion nueva es evidencia en el issue.
- Promete en su doc "umbral = 3x std del baseline" pero implementa **umbrales absolutos
  hardcodeados** (brecha doc-codigo).

Ademas, un research de la industria (Argo Rollouts, Flagger, Kayenta, Keptn, SRE Workbook) confirma
que el modelo mental "baseline -> comparar senales acotadas -> puntuar pass/fail -> parar si un
umbral se sostiene" es el correcto para un monitor ligero, y que la mayor parte de la maquinaria de
las herramientas grandes (traffic-shifting, auto-rollback, comparacion estadistica, burn-rate,
webhooks) **no** merece replicarse aqui.

## Decision

**Fundir el motor en `deploy-watch` y eliminar la skill `deploy-monitor`.** El motor deja de ser un
script autonomo: **el agente orquesta por tick**, componiendo el catalogo de skills de
observabilidad que ya existe (no reinventa acceso a datos) y el agente `sre` (RCA). La logica de
decision se aisla en un **modulo puro testeable**; el "cerebro" de patrones pasa a un reference-doc.

## Diseno

### Motor: el agente orquesta, componiendo lo que ya hay

- **Datos por senal**: se compone el **catalogo de observabilidad disponible** (extensible, NO una
  lista cerrada). Hoy: `query-prometheus`, `query-elasticsearch`, `query-gcloud-logs`,
  `query-sentry`, `query-keycloak`, `query-postgres-readonly`. Anadir una skill nueva de
  observabilidad no debe requerir tocar `deploy-watch`.
- **Eleccion de senales por blast radius** del cambio (en el setup): caso general -> prometheus +
  elasticsearch + sentry (+ gcloud-logs para el LB); toca **auth** -> `query-keycloak`; toca
  **DB/migracion** -> `query-gcloud-logs` (Cloud SQL) + `query-postgres-readonly` (verificar efecto).
- **RCA ante anomalia**: agente `sre`. `incident-postmortem` como composicion **opcional** si se
  quiere un postmortem formal.
- **Esperas no bloqueantes**: ticks acotados en background + notificacion (o `Monitor`). Nunca una
  shell colgada toda la ventana.
- **Evidencia**: comentarios en el **issue** de la feature (no CSV local).

### Core de decision puro — `skills/deploy-watch/scripts/deploy_core.py`

Modulo puro (patron `issue_body.py`): sin I/O, opera sobre muestras que el agente arma a partir de
las `query-*`. Testeable offline. Funciones (nombres orientativos):

- `aggregate_baseline(samples)` -> por senal `{mean, std}`.
- `baseline_quality(samples)` -> avisos de **baseline ruidoso** (coef. de variacion alto).
- `evaluate_tick(sample, baseline, config)` -> estado por senal (`ok|warn|breach`) con **umbrales
  relativos** (`mean + N*std` o `*factor`); absolutos solo para senales con baseline ~0 (errores).
- **confirmacion sostenida**: un breach cuenta como no-go solo si persiste `failure_limit` ticks
  seguidos (default 2) — mata falsos positivos por picos vecinos.
- `scorecard(history, config)` -> por senal: peor estado + nº de breaches.
- `verdict(scorecard, config)` -> `go | no-go | inconclusive`. Solo senales **criticas** fuerzan
  no-go; las **advisory** informan. Respeta **warm-up** (grace tras el cambio) y **min-observe**
  (no declarar `go` hasta cubrir la ventana de rollout+drain).
- Config por senal: `{tier: critical|advisory, mode: relative|absolute, warn, crit, n_std|factor}`;
  global: `warmup_secs`, `min_observe_secs`, `failure_limit`, `baseline_secs`, `poll_secs`.
- Se expone tambien como **CLI JSON in/out** (como `gates.py --json`) para que el agente lo invoque
  por tick / al cierre sin parsear prosa.

### Reference-doc — `skills/deploy-watch/references/monitoring.md`

El "cerebro" que se carga solo al monitorizar (`reference-docs`):

- Filosofia: mirar las senales correctas en el momento correcto; **medir donde el usuario ve el
  error, no donde el proceso lo emite**.
- **Catalogo de observabilidad (abierto)** + mapeo senal->skill.
- Eleccion de senales: **RED en el edge** (rate/errors/duration en ingress/LB) + **USE** para el
  recurso que se toca; una senal de estado (ready), una de flapping, una de recursos, una de errores
  externos, minimo.
- Parametros por defecto y cuando ajustarlos (baseline 120s, poll 30s, `failure_limit` 2, `N*std`,
  warm-up = duracion del rollout, min-observe = rollout + drain).
- Errores tipicos (heredados del `SKILL.md` viejo): medir la capa equivocada; baseline corto/ruidoso;
  umbrales sacados del aire; poll mas largo que el evento; olvidar los 5xx del proxy frontal;
  confundir "pod not ready" con "clientes afectados".
- **Marcador del instante del cambio** en la evidencia (para el triaje posterior).
- Descartes (y por que): traffic-shifting, auto-rollback (choca con "el rollback lo decide el
  humano"), comparacion Mann-Whitney (n insuficiente: ~4 muestras), burn-rate completo, webhooks.

### `deploy-watch/SKILL.md` reescrito

- El motor es **el propio `deploy-watch`** (compone catalogo de observabilidad + `sre` + `deploy_core`);
  desaparece la dependencia de la skill `deploy-monitor`.
- Pasos: **setup** (inferir servicio/namespace + elegir fuentes por blast radius) -> **baseline**
  (ticks componiendo las `query-*` elegidas; `aggregate_baseline` + gate de ruido) -> **marcar el
  instante del cambio** -> **poll por tick** (`query-*` -> `deploy_core.evaluate` -> scorecard, con
  warm-up y min-observe) -> **veredicto go/no-go** + evidencia (comentario en el issue con el
  scorecard vs baseline) -> **anomalia**: `sre` para RCA + **rollback redactado** (nunca ejecutado).
- Mantiene: read-only sobre prod, `max_runtime` + circuit breaker, control humano del merge/rollback.

### Tests — `tests/test_deploy_core.py`

Sobre `deploy_core` (offline, muestras sinteticas): `aggregate_baseline` (mean/std), gate de baseline
ruidoso, umbrales relativos vs absolutos, confirmacion sostenida (N ticks), tiers critical/advisory,
scorecard + verdict (incl. warm-up y min-observe), inconclusive por timeout.

### Limpieza

- Eliminar `~/.claude/skills/deploy-monitor/` (skill suelta, ya sin uso).

## No incluido (YAGNI / descartado)

- Traffic-shifting / canary weight; auto-rollback; comparacion estadistica no parametrica;
  aritmetica de burn-rate; webhooks/gates externos (del research).
- CSV/estado local (evidencia va al issue).
- CI para los tests (se documenta `python3 -m pytest`).

## Verificacion

- `python3 -m pytest` verde (incluye `test_deploy_core`).
- `deploy-watch/SKILL.md` no referencia la skill `deploy-monitor` ni HTTP directo a Prometheus/ES;
  el catalogo de observabilidad se describe como abierto.
- `~/.claude/skills/deploy-monitor/` eliminado.
- Busqueda de `deploy-monitor`, `monitor_template`, `prometheus.prod.monline` en el repo sin
  resultados fuera de design-docs historicos.
