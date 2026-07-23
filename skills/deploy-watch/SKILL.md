---
name: deploy-watch
description: Monitoriza un despliegue en produccion tras aprobar y mergear una PR. Usar cuando el usuario diga "monitoriza el deploy", "vigila el despliegue", "deploy-watch", o acabe de mergear/desplegar y quiera confirmar que todo va bien. Fase post-approve, invocacion manual, read-only sobre prod: captura baseline, poll-ea por tick las senales relevantes al cambio (rollout k8s, recursos, errores/latencia HTTP, Sentry, y segun el blast radius auth/DB) contra baseline, emite un veredicto go/no-go, y ante anomalia lanza el agente sre para RCA y redacta (sin ejecutar) el rollback. Orquesta las skills de observabilidad ya existentes y el agente sre, y decide con un core puro; no reinventa el acceso a datos.
---

# Deploy Watch

STARTER_CHARACTER = [deploy-watch]

Emite `[deploy-watch]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Fase **post-approve** del flujo spec -> slice -> PR -> CI: una vez el usuario aprueba y mergea la PR y el despliegue arranca, esta skill confirma que la nueva version esta sana en produccion. Se invoca **automaticamente al detectar el merge** (encadenada desde `slice-runner`) o a mano; en ambos casos **arranca sola**. Read-only sobre prod. No es un motor nuevo: **el agente orquesta** piezas que ya existen.

- **Datos**: se componen las **skills de observabilidad** disponibles (catalogo abierto): `query-prometheus`, `query-elasticsearch`, `query-gcloud-logs`, `query-sentry`, `query-keycloak`, `query-postgres-readonly`. El agente recoge las muestras por tick; no hay HTTP directo.
- **Decision**: la logica (baseline, umbrales relativos, confirmacion sostenida, scorecard, veredicto go/no-go) la ejecuta `scripts/deploy_core.py` (puro, testeable). El juicio de **que senales elegir** esta en `references/monitoring.md`.
- **RCA ante anomalia**: agente `sre` (read-only). Postmortem formal opcional: `incident-postmortem`.

El agente orquesta el flujo (recoge senales -> `deploy_core` decide -> evidencia en el issue) y emite el veredicto.

## Principios no negociables

- **Read-only sobre prod.** Nunca ejecuta el rollback ni toca backends. El merge y el rollback los decide siempre el usuario.
- **Arranque sin friccion.** Se invoca automaticamente tras el merge (desde `slice-runner`) y **arranca sola**: infiere servicio/workload/namespace del repo y empieza. Solo para y pregunta si la inferencia es ambigua o de baja confianza (`check-alignment` solo cuando hay duda real, no un gate por defecto). No espera a que le digas "revisa el deploy".
- **Componer, no reinventar.** Los datos vienen de las **skills de observabilidad** (catalogo abierto; anadir una nueva no debe requerir tocar esta skill); la decision la hace `deploy_core.py`; el RCA lo hace el agente `sre`. Nada de HTTP directo a Prometheus/ES ni de reimplementar acceso a datos.
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

- Elige las senales segun el **blast radius** del cambio (ver `references/monitoring.md`: RED en el edge + USE del recurso; toca auth -> `query-keycloak`; toca DB/migracion -> `query-gcloud-logs`/`query-postgres-readonly`). Marca cada senal `critical` o `advisory`.
- Toma varias muestras **pre-cambio** componiendo las `query-*` elegidas y agregalas con `deploy_core.aggregate_baseline` (media + std). Comprueba el **gate de baseline ruidoso**; si avisa, alarga el baseline.
- El baseline es la vara contra la que se comparan los ticks posteriores.

### 3. Poll loop (el agente orquesta por tick)

Se ejecuta con **ticks acotados en background + notificacion** (o `Monitor`), no como una shell bloqueante que se quede toda la ventana colgada. En cada tick, el agente **recoge las senales elegidas componiendo las `query-*`**, arma la muestra y se la pasa a `deploy_core` (clasifica vs baseline con umbrales relativos y acumula el scorecard con confirmacion sostenida). Senales tipicas (elige por blast radius, **no es lista fija**):

| Senal | Fuente | breach si... |
|---|---|---|
| Rollout k8s | `query-prometheus` (`rollout_info_*`, `kube_deployment_status_*`) | rollout no Healthy, replicas no listas, CrashLoop |
| Recursos | `query-prometheus` (`container_memory_*`, restarts, `container_cpu_*` throttling) | OOMKills, restarts anomalos, throttling alto |
| Errores/latencia HTTP | `query-prometheus` (`http_server_duration_*`) + `query-elasticsearch` (5xx nginx/akamai) | 5xx o p95/p99 se desvian del baseline mas alla del umbral |
| Sentry | `query-sentry` | issues nuevas o regresiones ligadas al release |
| Auth (si aplica) | `query-keycloak` | pico de `LOGIN_ERROR`/`CODE_TO_TOKEN_ERROR` del release |
| DB (si aplica) | `query-gcloud-logs` (Cloud SQL) + `query-postgres-readonly` | deadlocks/lock timeouts; efecto de datos incorrecto |

### 4. Veredicto (deploy_core)

`deploy_core.verdict` da `go` / `no-go` / `inconclusive` a partir del scorecard y las ventanas:

- **go** (sano): ninguna senal `critical` en breach **sostenido** y cubierta la ventana `min_observe` -> reporte verde, la slice queda **validada en deploy** (veredicto en vivo, no se persiste) y **para**.
- **no-go** (degradado): una senal `critical` en breach sostenido -> rama de anomalia (paso 5).
- **inconclusive**: dentro del warm-up, o agotado `max_runtime` sin converger -> reporte con datos y **para**.

### 5. Rama de anomalia

1. Lanza el agente `sre` para un **RCA read-only**, cruzando las fuentes de observabilidad, con el impacto de negocio. (`incident-postmortem` opcional si se quiere un postmortem formal.)
2. **Redacta (sin ejecutar) el rollback**: `git revert <merge_sha>` + redeploy, con los comandos listos para que los lance el usuario. Si el cambio iba tras un feature flag, apagar el flag es el rollback preferido (reversible en runtime, sin redeploy).
3. Para y presenta: senal(es) en breach + evidencia (scorecard vs baseline), RCA del `sre`, y el rollback preparado.

## Integracion con el issue

Comparte la trazabilidad del pipeline con `slice-runner` a traves del **issue de GitHub** de la feature:

- Al arrancar y en el veredicto, **comenta en el issue** (`gh issue comment`) el resultado del deploy de esa slice: `deploy start`, senales `ok|degradada`, `verdict sano|degradado|inconcluso`, y -si aplica- `rca` + `rollback redactado`, con la tabla vs baseline. Asi el issue reune diseno, implementacion y despliegue en un solo hilo.
- **No cambia el estado (marcador/checkbox) de la slice**: ya quedo `mergeada` en el paso 9 de `slice-runner`. El veredicto del deploy es informativo y se registra como comentario, no como estado.

## Fin

Al parar, reporta siempre: servicio y release vigilados, ventana observada, veredicto (sano / degradado / inconcluso), tabla de las 4 senales vs baseline, y -si aplica- RCA + rollback redactado. Recuerda que el rollback lo ejecuta el usuario.
