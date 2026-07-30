---
name: deploy-watch
description: Monitoriza un despliegue en produccion tras aprobar y mergear una PR. Usar cuando el usuario diga "monitoriza el deploy", "vigila el despliegue", "deploy-watch", o acabe de mergear/desplegar y quiera confirmar que todo va bien. Fase post-approve, invocacion manual, read-only sobre prod: captura baseline, poll-ea por tick las senales relevantes al cambio (rollout k8s, recursos, errores/latencia HTTP, Sentry, y segun el blast radius auth/DB) contra baseline, emite un veredicto go/no-go, y ante anomalia lanza el agente sre para RCA y redacta (sin ejecutar) el rollback. Orquesta las skills de observabilidad ya existentes y el agente sre, y decide con un core puro; no reinventa el acceso a datos.
---

# Deploy Watch

STARTER_CHARACTER = [deploy-watch]

Emite `[deploy-watch]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Fase **post-approve** del flujo spec -> slice -> PR -> CI: una vez el usuario aprueba y mergea la PR y el despliegue arranca, esta skill confirma que la nueva version esta sana en produccion. Se invoca **automaticamente al detectar el merge** (encadenada desde `slice-runner`) o a mano; en ambos casos **arranca sola**. Read-only sobre prod. No es un motor nuevo: **el agente orquesta** piezas que ya existen.

- **Datos**: se componen las **skills de observabilidad** disponibles (catalogo abierto): `query-prometheus`, `query-elasticsearch`, `query-gcloud-logs`, `query-sentry`, `query-keycloak`, `query-postgres-readonly`. Un **subagente colector** recoge las muestras por tick (aisla la salida cruda de las `query-*`); no hay HTTP directo.
- **Decision**: la logica (baseline, umbrales relativos, confirmacion sostenida, scorecard, veredicto go/no-go) la ejecuta `scripts/deploy_core.py` (puro, testeable). El juicio de **que senales elegir** esta en `references/monitoring.md`.
- **RCA ante anomalia**: agente `sre` (read-only). Postmortem formal opcional: `incident-postmortem`.

El agente orquesta el flujo (lanza el **colector** por tick -> `deploy_core` decide -> evidencia en el issue) y emite el veredicto.

## Principios no negociables

- **Read-only sobre prod.** Nunca ejecuta el rollback ni toca backends. El merge y el rollback los decide siempre el usuario.
- **Arranque sin friccion.** Se invoca automaticamente tras el merge (desde `slice-runner`) y **arranca sola**: infiere servicio/workload/namespace del repo y empieza. Solo para y pregunta si la inferencia es ambigua o de baja confianza (`check-alignment` solo cuando hay duda real, no un gate por defecto). No espera a que le digas "revisa el deploy".
- **Componer, no reinventar.** Los datos vienen de las **skills de observabilidad** (catalogo abierto; anadir una nueva no debe requerir tocar esta skill); la decision la hace `deploy_core.py`; el RCA lo hace el agente `sre`. Nada de HTTP directo a Prometheus/ES ni de reimplementar acceso a datos.
- **Recogida aislada en un colector (`focused-agent`, `context-management`).** La salida cruda y verbosa de las `query-*` no se acumula en el hilo principal: un **subagente colector efimero (uno por tick, y en el baseline)** la absorbe en su contexto y devuelve solo la muestra plana `{senal: valor}` mas una tabla de hallazgos con las **queries reproducibles**. El hilo principal elige QUE senales (juicio, por blast radius) y decide/orquesta; el colector solo ejecuta y extrae. `deploy_core` no cambia: sigue recibiendo la misma muestra.
- **Si el entorno veta los subagentes, degrada y declaralo.** Invocar esta skill **cuenta como pedir** el colector y el `sre`: no es iniciativa del agente, asi que no pidas permiso para lanzarlos. Si una restriccion los impide (veto global al Agent tool, politica de la organizacion), **dilo siempre** y decide con este criterio: **¿se puede declarar la degradacion en el artefacto que produces?** Si se puede, degrada y declaralo **ahi**, no solo en el chat; si el artefacto entero significa justo la garantia que has perdido, para. Esta skill cae del lado de **degradar**: su artefacto -el veredicto comentado en el issue- **puede declarar su propia procedencia**, y ademas lo calcula `deploy_core.py` y no la impresion del agente, asi que la afirmacion sigue siendo verdadera si dice como se obtuvo. Lo que se pierde es higiene de contexto, no validez. Por eso **declararlo no es cortesia, es la condicion que autoriza a degradar**: al arrancar **y** en el informe final, con cuantos ticks se acumularon y el aviso de que una ventana larga pierde fiabilidad (si es larga, propon acortarla o vigilar menos senales). Lo que **no** se degrada nunca: `deploy_core.py` decide siempre. Y quedarte sin monitorizar un deploy ya mergeado seria peor: perderias la vigilancia sin ganar ninguna garantia. (`slice-runner` aplica el **mismo criterio** y para, porque su PR con PASA no puede declararlo: artefacto distinto, no incoherencia.)
- **La senal declarada por la slice manda.** Si la slice trae una linea `SENAL:` en el issue, esa senal
  entra **siempre** en el set vigilado, con la criticidad que declara, **por delante** de las inferidas
  por blast radius (que siguen entrando como complemento). Es la diferencia entre afirmar "el servicio
  esta sano" -lo unico que permite la inferencia generica- y afirmar "el comportamiento que introdujo
  esta slice esta pasando en produccion". Y si la senal declarada **no se puede medir** (la serie no
  existe, la query no devuelve nada, la fuente no responde), el veredicto de esa senal es
  **`inconclusive`, nunca `go`**: tragarselo devolveria el veredicto generico por la puerta de atras, que
  es justo lo que la senal declarada viene a corregir. Dilo en el informe y en el comentario del issue.
- **Veredicto por senales criticas, sostenido.** Solo las senales `critical` fuerzan `no-go`, y solo si el breach **persiste** (`failure_limit` ticks); las `advisory` informan sin bloquear. `deploy_core` respeta warm-up (grace tras el cambio) y min-observe (no declara `go` antes de cubrir rollout+drain). Un pico aislado no dispara anomalia.
- **Esperas no bloqueantes.** El poll de estabilizacion se hace con **ticks acotados en background + notificacion** (o `Monitor`), devolviendo el control entre ticks. Prohibido una unica shell bloqueante que se quede colgada toda la ventana (30-60 min): es trabajo deterministico del harness, no la IA poll-eando (`offload-deterministic`).
- **Sin loop infinito.** `max_runtime` (timeout de ventana) + circuit breaker: si no converge, reporte inconcluso con datos, nunca poll eterno.
- **Evidencia siempre.** Cada veredicto (sano, degradado, inconcluso) va acompanado de los datos que lo sostienen (tabla vs baseline).

## Steps

### 1. Setup (arranque automatico)

- Identifica el **servicio / workload de k8s** desplegado infiriendolo del repo (nombre del repo -> workload en prod) y su namespace. **Si la inferencia es de alta confianza, arranca sin preguntar.** Solo para y pregunta si es ambigua (p. ej. varios namespaces candidatos: `¿shop o shop-staging?`).
- Identifica el **release** y el **`merge_sha`** de la PR (para correlacionar Sentry y para redactar el rollback).
- Fija **t0** = momento del deploy ("acabo de desplegar"). Fija la ventana de rollout y la ventana de estabilizacion (rollout completo + N minutos limpios).

### 2. Baseline

- **Empieza por la `SENAL` declarada en el issue** para la slice recien mergeada (si `slice-runner` te
  la paso, o leela con `issue_body.parse_body`): entra en el set con su criticidad, tal cual. Si dice
  `exenta`, no hay senal propia y vigilas solo lo generico.
  Marcala en la config de `deploy_core` con **`declarada: true`** (y su `critical`): es lo que hace que
  el core la trate distinto -si no llega ninguna muestra suya, el veredicto es `inconclusive` en vez de
  `go`-. Sin ese flag, la regla seria prosa que el core no aplica.
- Completa con las senales que pide el **blast radius** del cambio (ver `references/monitoring.md`: RED en el edge + USE del recurso; toca auth -> `query-keycloak`; toca DB/migracion -> `query-gcloud-logs`/`query-postgres-readonly`). Marca cada senal `critical` o `advisory`.
- **Si la slice vino de otro repo** (`REPO:`: una alerta o un panel), lo desplegado no es el workload de
  la app: no hay rollout que vigilar y las senales de recursos no dicen nada. El veredicto se apoya en la
  senal declarada (p. ej. que la regla de alerta cargo y no dispara falsos positivos).
- Toma varias muestras **pre-cambio lanzando el colector** (mismo mecanismo que el poll, ver paso 3) y agregalas con `deploy_core.aggregate_baseline` (media + std). Comprueba el **gate de baseline ruidoso**; si avisa, alarga el baseline.
- El baseline es la vara contra la que se comparan los ticks posteriores.

### 3. Poll loop (el agente orquesta por tick)

Se ejecuta con **ticks acotados en background + notificacion** (o `Monitor`), no como una shell bloqueante que se quede toda la ventana colgada. En cada tick, el hilo principal **lanza el colector** (Agent tool, `subagent_type: general-purpose`) con las senales elegidas; el colector compone las `query-*`, absorbe su salida cruda y devuelve la muestra + la tabla (ver contrato abajo). El hilo principal mete la muestra en `tick_history` y se la pasa a `deploy_core` (clasifica vs baseline con umbrales relativos y acumula el scorecard con confirmacion sostenida), y **guarda la tabla sin imprimirla**: aflora solo en hitos (baseline listo, veredicto, anomalia), para no re-ensuciar el contexto que el colector limpio. Senales tipicas (elige por blast radius, **no es lista fija**):

| Senal | Fuente | breach si... |
|---|---|---|
| Rollout k8s | `query-prometheus` (`rollout_info_*`, `kube_deployment_status_*`) | rollout no Healthy, replicas no listas, CrashLoop |
| Recursos | `query-prometheus` (`container_memory_*`, restarts, `container_cpu_*` throttling) | OOMKills, restarts anomalos, throttling alto |
| Errores/latencia HTTP | `query-prometheus` (`http_server_duration_*`) + `query-elasticsearch` (5xx nginx/akamai) | 5xx o p95/p99 se desvian del baseline mas alla del umbral |
| Sentry | `query-sentry` | issues nuevas o regresiones ligadas al release |
| Auth (si aplica) | `query-keycloak` | pico de `LOGIN_ERROR`/`CODE_TO_TOKEN_ERROR` del release |
| DB (si aplica) | `query-gcloud-logs` (Cloud SQL) + `query-postgres-readonly` | deadlocks/lock timeouts; efecto de datos incorrecto |

**Contrato del colector (entrada / salida).** El **hilo principal** elige QUE senales (juicio por blast radius; ver `references/monitoring.md`) y lanza un colector por tick con:

- **entrada**: contexto del deploy (workload / servicio / namespace / release / `merge_sha` / t0) + lista de specs de senal `{name, fuente (que query-* usar), descripcion, critical|advisory}`.
- El colector **construye la query concreta** (PromQL/KQL/SQL) el mismo -ese conocimiento vive en la `query-*` que carga-; el hilo principal habla en terminos de negocio ("p95 del workload X"), no en query.
- **salida**: por senal una fila `{valor, estado (ok/warn/breach informativo), hallazgo (una linea), query reproducible}`. Agregado devuelve (a) la **muestra plana** `{senal: valor}` para `deploy_core` y (b) la **tabla de hallazgos con las queries reproducibles** para el informe.
- El colector **no** decide veredicto, **no** redacta rollback, **no** lanza a `sre` (seria anidar): solo recoge y extrae (`focused-agent`).

### 4. Veredicto (deploy_core)

`deploy_core.verdict` da `go` / `no-go` / `inconclusive` a partir del scorecard y las ventanas:

- **go** (sano): ninguna senal `critical` en breach **sostenido** y cubierta la ventana `min_observe` -> reporte verde, la slice queda **validada en deploy** (veredicto en vivo, no se persiste) y **para**.
- **no-go** (degradado): una senal `critical` en breach sostenido -> rama de anomalia (paso 5).
- **inconclusive**: dentro del warm-up, agotado `max_runtime` sin converger, **o una senal declarada por
  la slice que no se ha podido medir** -> reporte con datos y **para**. Una senal declarada que nadie
  pudo leer no es un `go`: es un fallo de la senal, y se dice.

**Exit 2 no es un veredicto: es tu payload mal escrito.** El script rechaza una clave que no
conoce (`declarado` por `declarada`, `warmup_seconds` por `warmup_secs`) y un `signals` que no sea
un objeto, en vez de ignorarlos. Ignorarlos era peor que petar: una senal declarada degradada a
inferida en silencio, o cero senales configuradas, devuelven el `go` generico que esta skill existe
para no dar. Si sale 2, **corrige el payload y reinvoca**; no lo leas como `inconclusive`.

### 5. Rama de anomalia

1. **El hilo principal** lanza el agente `sre` para un **RCA read-only** (no lo lanza el colector: seria anidar), cruzando las fuentes de observabilidad, con el impacto de negocio, y le pasa como pista las **senales en breach + sus queries reproducibles** que el colector ya devolvio -mejor punto de partida del triaje-. (`incident-postmortem` opcional si se quiere un postmortem formal.)
2. **Redacta (sin ejecutar) el rollback**: `git revert <merge_sha>` + redeploy, con los comandos listos para que los lance el usuario. Si el cambio iba tras un feature flag, apagar el flag es el rollback preferido (reversible en runtime, sin redeploy).
3. Para y presenta: senal(es) en breach + evidencia (scorecard vs baseline), RCA del `sre`, y el rollback preparado.

## Integracion con el issue

Comparte la trazabilidad del pipeline con `slice-runner` a traves del **issue de GitHub** de la feature:

- Al arrancar y en el veredicto, **comenta en el issue** (`gh issue comment`) el resultado del deploy de esa slice: `deploy start`, senales `ok|degradada`, `verdict sano|degradado|inconcluso`, y -si aplica- `rca` + `rollback redactado`, con la **tabla de hallazgos vs baseline y las queries reproducibles del hito** (no una por tick).
- **Di siempre de donde salio la senal**: si la slice declaro `SENAL`, cita su linea y el resultado; si
  no la declaro (o estaba `exenta`), dilo -el veredicto es entonces la salud generica del servicio, no una
  comprobacion de *este* cambio-. Es la misma logica que el modo degradado sin subagentes: se puede
  degradar porque el artefacto **declara** su procedencia. Asi el issue reune diseno, implementacion y despliegue en un solo hilo.
- **No cambia el estado (marcador/checkbox) de la slice**: ya quedo `mergeada` en el paso 10 de `slice-runner`. El veredicto del deploy es informativo y se registra como comentario, no como estado.

## Fin

Al parar, reporta siempre: servicio y release vigilados, ventana observada, veredicto (sano / degradado / inconcluso), tabla de senales vs baseline **con las queries reproducibles**, y -si aplica- RCA + rollback redactado. Recuerda que el rollback lo ejecuta el usuario.

Si el run fue **en modo degradado** (sin subagentes, ver principios), dilo tambien aqui, no solo al arrancar: que la recogida fue inline, cuantos ticks se acumularon en el contexto, y que eso resta fiabilidad al final de una ventana larga. El usuario tiene que poder ponderar el veredicto sabiendo con que se obtuvo.
