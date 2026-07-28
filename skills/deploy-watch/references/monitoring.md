# Cerebro de monitorizacion de deploys

Reference-doc de `deploy-watch`. Se carga **solo cuando toca monitorizar** (`reference-docs` +
`context-management`). Es el conocimiento que antes vivia en la skill `deploy-monitor` (ya
absorbida), destilado con un research de la industria (Argo Rollouts, Flagger, Kayenta, Keptn, SRE
Workbook). La logica de decision la ejecuta `scripts/deploy_core.py`; esto es el juicio de **que
medir** y **como leerlo**.

## Filosofia

El operador necesita mirar **las senales correctas en el momento correcto**, no cualquier metrica.
Principio central: **medir donde el usuario siente el error, no donde el proceso lo emite**. Un RST
TCP no aparece en metricas del proceso; un 502 del ingress no aparece en la app. Instrumentar la
capa adecuada.

## Componer, no reinventar: catalogo de observabilidad (abierto)

Las senales NO se recogen con HTTP directo: se componen las **skills de observabilidad** que ya
existen. La lista es un **catalogo abierto** — anadir una skill nueva no debe requerir tocar
`deploy-watch`. Hoy:

| Skill | Cubre |
|---|---|
| `query-prometheus` | metricas: rollout (`rollout_info_*`, `kube_deployment_status_*`), recursos (`container_memory_*`, restarts, `container_cpu_*` throttling), HTTP (`http_server_duration_*`), trafico/ingress |
| `query-elasticsearch` | logs: 5xx de Akamai/nginx, upstream_response_time, logs de app, Argo |
| `query-gcloud-logs` | Load Balancer, Cloud Armor, **Cloud SQL/Postgres** (deadlocks, lock timeouts, statement timeouts) |
| `query-sentry` | issues/regresiones nuevas ligadas al release |
| `query-keycloak` | **auth**: errores de login/OIDC/SSO del release |
| `query-postgres-readonly` | estado de datos en prod (verificar el efecto de una migracion) |

RCA ante anomalia: agente `sre`. Postmortem formal (opcional): `incident-postmortem`.

**Quien elige vs quien ejecuta.** La **eleccion** de senales (que medir por blast radius) es juicio y se queda en el **hilo principal**, guiada por este doc. La **ejecucion** (construir la query concreta, componer la `query-*`, absorber la salida cruda y extraer el valor) la hace el **subagente colector**, uno por tick, que devuelve la muestra plana + una tabla con las queries reproducibles. Asi la salida verbosa no ensucia el contexto principal (`focused-agent`, `context-management`).

## La senal declarada por la slice va primero

Antes de inferir nada: si la slice trae una linea `SENAL:` en el issue, **esa es la senal principal** y
entra con la criticidad que declara. La inferencia por blast radius de abajo es lo que se anade
**alrededor**, no lo que la sustituye.

El motivo es lo que la inferencia **no puede** hacer: el blast radius mira el diff y elige senales
genericas del servicio, asi que su veredicto solo puede afirmar "el servicio esta sano". La senal
declarada la eligio quien diseno la slice sabiendo que comportamiento introducia, asi que permite
afirmar "el comportamiento de esta slice esta pasando en produccion". Son afirmaciones distintas.

Como leerla: la linea tiene la forma `<fuente> <serie/expresion>; <assert vivo con ventana>;
critical|advisory`. La fuente dice que `query-*` compone el colector; el assert, cuando cuenta como
cumplida; la ultima parte, si frena el `go`. Ejemplos:

```
SENAL: prometheus rate(application_stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
SENAL: prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory
SENAL: exenta - refactor puro
```

**Si no se puede medir, es `inconclusive`, no `go`.** Serie inexistente, query vacia o fuente caida
significan que la senal no cumplio su cometido; darla por buena devolveria el veredicto generico por la
puerta de atras. Una serie que **existe y vale 0** es otra cosa: eso es un dato, y se juzga contra el
assert.

Eso **lo decide el core, no el criterio del agente**: marca la senal con `declarada: true` en la config
de `deploy_core`, y si no llega ninguna muestra suya, `verdict` devuelve `inconclusive` con la senal en
`blocking`. Las inferidas sin muestras no frenan el `go` (son best-effort), pero el scorecard expone
`measured` de todas para que el informe no confunda "sana" con "no medida".

**Slices de otro repo** (`REPO:`, alertas o paneles): no hay rollout de la app ni recursos que mirar; el
veredicto se apoya solo en la senal declarada.

## Eleccion de senales por blast radius

Elige 4-8 senales segun **que toca el cambio** (no siempre las mismas), **ademas** de la declarada:

- **Caso general**: prometheus (rollout + recursos) + elasticsearch/prometheus (5xx + latencia en el
  edge) + sentry. Anade `query-gcloud-logs` para los 5xx del Load Balancer.
- **Toca auth** (login, tokens, SSO): anade `query-keycloak` (`LOGIN_ERROR`, `CODE_TO_TOKEN_ERROR`...).
- **Toca DB / migracion**: `query-gcloud-logs` (Cloud SQL: deadlocks, connection slots) +
  `query-postgres-readonly` (comprobar el efecto en datos).

Cobertura minima recomendada (RED en el edge + USE del recurso):
- **RED** medido en el **edge/ingress** (donde lo ve el usuario): rate, errors (5xx), duration (p95/p99).
- **USE** del recurso que tocas: utilization/saturation (CPU throttling, memoria, restarts).
- Al menos: una senal de estado (ready), una de flapping (`changes(ready[5m])`), una de recursos,
  una de errores externos.

## Como leer las senales (lo ejecuta deploy_core.py)

- **Umbrales relativos al baseline** (`mean + N*sigma`), no numeros al aire. Absolutos solo para
  senales cuyo baseline es ~0 (errores): ahi cualquier aparicion es sospechosa.
- **Confirmacion sostenida**: un breach cuenta como no-go solo si persiste `failure_limit` ticks
  seguidos (default 2). Un pico aislado (rollout vecino, crawler) no dispara no-go.
- **Criticas vs advisory**: solo las senales `critical` fuerzan no-go (los 5xx/refused que ven los
  clientes). Las advisory (p. ej. CPU) informan pero no bloquean.
- **Gate de baseline ruidoso**: si el coef. de variacion del baseline es alto, el baseline no sirve
  de vara — sube `baseline_secs` o no te fies del delta de esa senal.

## Ventanas de tiempo

- **Baseline**: 120 s por defecto; 300 s si la senal tiene varianza alta.
- **Poll**: 30 s; baja a 10-15 s si el evento a observar es corto (rollout de 1 replica ~30 s).
- **Warm-up**: grace tras el cambio (= duracion esperada del rollout, ~60-90 s) donde los breaches se
  ven pero no deciden — la rotacion de pods emite 5xx/latencia transitorios esperados. Corto y
  explicito: si tapa un fallo real es peor que no tenerlo.
- **Min-observe**: no declarar `go` hasta cubrir rollout + drain de conexiones. "No te vayas tranquilo
  hasta que roten todas las replicas."

## Marcador del instante del cambio

Registra en la evidencia (comentario del issue) el momento exacto en que se aplico el cambio
(merge/deploy). "Algo se desplego justo antes de esta regresion?" es la primera pregunta del triaje.

## Errores tipicos

- **Medir donde no se ve el sintoma**: `http_server_duration_count` de la app no ve RSTs ni 502s del
  ingress. Pregunta "donde exactamente aparece el error que vemos?" y mide en esa capa.
- **Baseline demasiado corto**: 30 s dejan que un pico natural envenene el delta. 120 s minimo.
- **Umbrales del aire**: ">=5 err/min" sin saber que el baseline es 0.02/min es ruido. Derivalos del
  baseline.
- **Poll mas largo que el evento**: con poll de 60 s te pierdes un `ready=0` de 30 s. Baja el poll o
  confia en `changes()` de Prometheus.
- **Olvidar los 5xx del proxy frontal**: el proceso sano y el ingress emitiendo 502s durante la
  rotacion. Incluye siempre la capa inmediatamente anterior al servicio.
- **Confundir "pod not ready" con "clientes afectados"**: si el pod comparte Service, su NotReady lo
  absorbe kube-proxy. Mide `ready` (advisory) y 5xx/refused (critical) por separado; la decision
  go/no-go depende de la segunda.

## Descartado (y por que)

Del research, lo que NO merece replicar en un monitor ligero de una persona:

- **Traffic-shifting / canary weight** (Flagger/Argo): esto observa, no enruta.
- **Auto-rollback** (Flagger/Argo): choca con el principio del repo — **el rollback lo decide el
  humano**. El monitor emite no-go + evidencia, nunca revierte.
- **Comparacion estadistica no parametrica** (Kayenta, Mann-Whitney): necesita ~50 muestras por
  metrica; un baseline de 2 min a 30 s son ~4 muestras. El techo pragmatico es `mean + N*sigma`.
- **Aritmetica de burn-rate multi-ventana**: asume un SLO y ventanas de horas/dias; un deploy dura
  10-15 min. Lo unico transplantable es la idea de dos ventanas para matar el flapping (ya en
  `failure_limit`).
- **Webhooks / suites de aceptacion como gates**: sobredimensiona un monitor de consola.

## Fuentes

- Google SRE Workbook — Alerting on SLOs (multi-window multi-burn-rate).
- Argo Rollouts — Analysis (successCondition/failureCondition, failureLimit).
- Netflix — Automated Canary Analysis with Kayenta.
- Spinnaker — Best practices for configuring canary.
- Flagger — How it works. Keptn — quality gates. Google SRE Book — golden signals.
