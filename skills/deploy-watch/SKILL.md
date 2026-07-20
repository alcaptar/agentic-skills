---
name: deploy-watch
description: Monitoriza un despliegue en produccion tras aprobar y mergear una PR. Usar cuando el usuario diga "monitoriza el deploy", "vigila el despliegue", "deploy-watch", o acabe de mergear/desplegar y quiera confirmar que todo va bien. Fase post-approve, invocacion manual, read-only sobre prod: captura baseline, poll-ea 4 senales de salud (rollout k8s, recursos, errores/latencia HTTP, Sentry) contra baseline, emite veredicto, y ante anomalia lanza el agente sre para RCA y redacta (sin ejecutar) el rollback. Compone las skills deploy-monitor y de observabilidad y el agente sre; no reinventa el motor.
---

# Deploy Watch

STARTER_CHARACTER = [deploy-watch]

Emite `[deploy-watch]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Fase **post-approve** del flujo spec -> slice -> PR -> CI: una vez el usuario aprueba y mergea la PR y el despliegue arranca, esta skill confirma que la nueva version esta sana en produccion. Se invoca **automaticamente al detectar el merge** (encadenada desde `slice-runner`) o a mano; en ambos casos **arranca sola**. Read-only sobre prod. No es un motor nuevo: **compone** los que ya existen.

- Motor de comparacion viva (baseline + poll + CSV + stream compartido): skill `deploy-monitor`.
- Fuentes de datos: skills de observabilidad (`query-prometheus`, `query-elasticsearch`, `query-sentry`, `query-gcloud-logs`).
- RCA ante anomalia: agente `sre` (read-only).

Esta skill solo orquesta el flujo y emite el veredicto.

## Principios no negociables

- **Read-only sobre prod.** Nunca ejecuta el rollback ni toca backends. El merge y el rollback los decide siempre el usuario.
- **Arranque sin friccion.** Se invoca automaticamente tras el merge (desde `slice-runner`) y **arranca sola**: infiere servicio/workload/namespace del repo y empieza. Solo para y pregunta si la inferencia es ambigua o de baja confianza (`check-alignment` solo cuando hay duda real, no un gate por defecto). No espera a que le digas "revisa el deploy".
- **Componer, no reinventar.** El baseline+poll+CSV lo hace `deploy-monitor`; los datos vienen de las skills de observabilidad; el RCA lo hace el agente `sre`. Esta skill no duplica esa logica.
- **Veredicto por las 4 senales.** El despliegue es sano solo si las 4 estan `ok` durante toda la ventana de estabilizacion. Cualquier senal `degradada` dispara la rama de anomalia.
- **Esperas no bloqueantes.** El poll de estabilizacion se hace con **ticks acotados en background + notificacion** (o `Monitor`), devolviendo el control entre ticks. Prohibido una unica shell bloqueante que se quede colgada toda la ventana (30-60 min): es trabajo deterministico del harness, no la IA poll-eando (`offload-deterministic`).
- **Sin loop infinito.** `max_runtime` (timeout de ventana) + circuit breaker: si no converge, reporte inconcluso con datos, nunca poll eterno.
- **Evidencia siempre.** Cada veredicto (sano, degradado, inconcluso) va acompanado de los datos que lo sostienen (tabla vs baseline).

## Steps

### 1. Setup (arranque automatico)

- Identifica el **servicio / workload de k8s** desplegado infiriendolo del repo (nombre del repo -> workload en prod) y su namespace. **Si la inferencia es de alta confianza, arranca sin preguntar.** Solo para y pregunta si es ambigua (p. ej. varios namespaces candidatos: `¿shop o shop-staging?`).
- Identifica el **release** y el **`merge_sha`** de la PR (para correlacionar Sentry y para redactar el rollback).
- Fija **t0** = momento del deploy ("acabo de desplegar"). Fija la ventana de rollout y la ventana de estabilizacion (rollout completo + N minutos limpios).

### 2. Baseline

- Captura la ventana **pre-deploy** (p. ej. 30-60 min antes de t0) para errores, latencia y recursos, usando la skill `deploy-monitor` como motor.
- El baseline es la vara contra la que se comparan los ticks posteriores.

### 3. Poll loop (motor deploy-monitor)

Se ejecuta con **ticks acotados en background + notificacion** (o `Monitor`), no como una shell bloqueante que se quede toda la ventana colgada. En cada tick, recoge las 4 senales, tabula vs baseline (CSV + stream compartido de `deploy-monitor`) y devuelve el control:

| Senal | Fuente | `ok` si... |
|---|---|---|
| Rollout k8s | `query-prometheus` (`rollout_info_*`, `kube_deployment_status_*`) + k8s | rollout Healthy, replicas listas, sin CrashLoop |
| Recursos | `query-prometheus` (`container_memory_*`, restarts, `container_cpu_*` throttling) | sin OOMKills, sin restarts anomalos, CPU en rango |
| Errores/latencia HTTP | `query-prometheus` (`http_server_duration_*`) + `query-elasticsearch` (5xx nginx/akamai) | 5xx y p95/p99 no se desvian del baseline mas alla del margen |
| Sentry | `query-sentry` | sin issues nuevas ni regresiones ligadas al release |

### 4. Veredicto por tick

- Cada senal es `ok` o `degradada`.
- **Sano**: las 4 `ok` durante toda la ventana de estabilizacion -> reporte verde, **marca la slice como validada en deploy** (ver ledger abajo) y **para**.
- **Degradada**: cualquier senal fuera de rango -> rama de anomalia (paso 5).
- **Timeout**: agotada la ventana sin converger -> reporte inconcluso con datos y **para**.

### 5. Rama de anomalia

1. Lanza el agente `sre` para un **RCA read-only**, cruzando las fuentes de observabilidad, con el impacto de negocio.
2. **Redacta (sin ejecutar) el rollback** segun `slicing.md`: `git revert <merge_sha>` + redeploy, con los comandos listos para que los lance el usuario.
3. Para y presenta: senal(es) degradada(s) + evidencia, RCA del `sre`, y el rollback preparado.

## Integracion con el ledger / stream

Comparte la observabilidad del pipeline con `slice-runner` via `.slice-runner/` del repo:

- Anexa al **stream en vivo** (`.slice-runner/stream.log`) una linea por transicion, con **fecha completa** `YYYY-MM-DD HH:MM:SS` (igual que `slice-runner`): `deploy start`, `signal <nombre> ok|degradada`, `verdict sano|degradado|inconcluso`, `rca ...`, `rollback drafted`. Asi el mismo `tail -f` cubre implementacion y despliegue.
- Al cerrar, anexa una entrada al **ledger** (`.slice-runner/runs.jsonl`) enlazada al `pr_url` y al `slice_id`: `{"pr_url":"...","slice_id":"slice-NN","fase":"deploy","veredicto":"sano|degradado|inconcluso","senales":{...},"ts":"..."}`. El `slice_id` permite al panel unir la slice con su validacion en deploy y pintar la columna DEPLOY. Un veredicto `sano` es lo que marca la slice como **validada en deploy** (no solo mergeada).

## Fin

Al parar, reporta siempre: servicio y release vigilados, ventana observada, veredicto (sano / degradado / inconcluso), tabla de las 4 senales vs baseline, y -si aplica- RCA + rollback redactado. Recuerda que el rollback lo ejecuta el usuario.
