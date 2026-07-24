# deploy-watch: colector de senales por tick (subagente)

Fecha: 2026-07-24
Estado: aprobado (a slicing + implementacion; sin fase de plan)

## Problema

En `deploy-watch`, la recogida de senales por tick corre en el **hilo principal**: el agente compone
las `query-*` (Prometheus, ES, Sentry, Keycloak, gcloud, postgres), lee su **salida cruda y verbosa**
(logs, respuestas de PromQL, issues de Sentry) y de ahi destila una muestra plana `{senal: valor}`
que pasa a `deploy_core`. Sobre una ventana de deploy (baseline + N ticks separados minutos), esa
salida cruda se **acumula en el contexto principal** tick a tick: `excess-verbosity` + `limited-focus`.
El hilo que ademas orquesta el loop, decide hitos y redacta rollback pierde foco enterrado en logs.

Ademas hoy la evidencia que aflora es la tabla vs baseline, pero **no las queries exactas** que la
produjeron: un humano no puede reproducir un hallazgo sin reconstruir la query a mano.

## Decision

Introducir un **subagente colector de senales**, efimero, **uno por tick** (y en el baseline). Absorbe
en su propio contexto la salida cruda de las `query-*` y devuelve algo compacto: la muestra plana para
`deploy_core` **mas** una tabla de hallazgos con las **queries reproducibles**. `deploy_core` no cambia:
sigue recibiendo la misma muestra; solo cambia **quien la produce**.

Se elige "un colector por tick" (no fan-out por fuente) porque de las tres motivaciones -aislamiento,
foco, paralelismo- las dos que pagan aqui (aislamiento y foco) ya se consiguen con un solo colector, y
el paralelismo entre fuentes apenas ahorra reloj en ticks separados minutos, a cambio de multiplicar
spawns/tokens (`no sobredimensiones`). El fan-out por fuente queda como upgrade acotado si un tick se
hace lento o crecen las fuentes (`chain-of-small-steps`).

## Diseno

### El componente: colector de senales

- Subagente efimero con **una sola responsabilidad** (`focused-agent`): recoger las senales elegidas
  componiendo las `query-*`, absorber su salida cruda, y devolver muestra + tabla + queries. **No**
  orquesta el loop, **no** decide veredicto, **no** redacta rollback, **no** lanza a `sre`.
- Contexto **fresco** en cada tick (nace y muere); no crece a lo largo de la ventana.
- Se lanza **inline** con el Agent tool (`subagent_type: general-purpose`), como hace `slice-runner`
  con sus subagentes. **No** se introduce `.claude/agents/`: las skills siguen autocontenidas y
  portables al repo destino.

### Contrato de entrada (que recibe el colector)

El **hilo principal** sigue eligiendo **que** senales por blast radius (juicio; vive en
`references/monitoring.md`) y le pasa al colector:

- contexto del deploy: workload / servicio / namespace / release / `merge_sha` / t0
- lista de *specs* de senal: `{name, fuente (que query-* usar), descripcion, critical|advisory}`

El colector **construye la query concreta** (PromQL/KQL/SQL) el mismo, no se la pasa el hilo principal:
ese conocimiento vive dentro de la `query-*` que el colector carga. Si el hilo principal tuviera que
saber la query, tendria que invocar la `query-*` y se rompe el aislamiento. El hilo principal habla en
terminos de negocio ("p95 del workload X"); el colector traduce a query.

### Contrato de salida (que devuelve)

Por cada senal, una fila: `valor` (float), `estado` (ok/warn/breach a ojo del dato crudo, informativo),
`hallazgo` (una linea) y la **query reproducible** (el comando exacto ejecutado). Agregado, el colector
devuelve:

- la **muestra plana** `{senal: valor}` -> el hilo principal la mete en `tick_history` /
  `baseline_samples` y se la da a `deploy_core` (contrato intacto).
- la **tabla de hallazgos + queries reproducibles** -> para el informe humano (`text-native`,
  "evidencia siempre").

### Donde aflora la tabla (sin re-ensuciar el contexto)

Imprimir la tabla completa **cada tick** volveria a llenar el contexto que el colector limpio. Por eso:

- Por tick, el hilo principal **solo consume la muestra** (a `deploy_core`) y **guarda** la ultima tabla
  sin imprimirla.
- La tabla con queries reproducibles **aflora solo en hitos**: (a) baseline listo, (b) veredicto final
  (`go` / `inconclusive`), (c) anomalia (`no-go`).
- El comentario en el issue lleva la tabla **del hito**, no una por tick.

### Rama de anomalia, sin anidar

El colector es subagente; si lanzara a `sre` seria anidamiento (bloqueado por defecto). Se mantiene la
separacion actual: **`sre` lo lanza el hilo principal**, no el colector. Ante `no-go`, el hilo principal:

1. ya tiene la tabla del colector con las **queries reproducibles de las senales en breach** -mejor
   punto de partida del RCA-;
2. lanza `sre` (desde el hilo principal, sin anidar) pasando esas senales + queries como pista;
3. redacta el rollback (sin ejecutar) y para.

## Que se toca

- `skills/deploy-watch/SKILL.md`: reescribir paso 2 (baseline) y paso 3 (poll loop) para que la
  recogida vaya via colector por tick; documentar contrato entrada/salida del colector; ajustar
  "Integracion con el issue" y "Fin" para tabla + queries en hitos; anadir el colector a la lista de
  subagentes que orquesta.
- `skills/deploy-watch/references/monitoring.md`: nota de que la **eleccion** de senales (juicio) sigue
  en el hilo principal y la **ejecucion** en el colector.
- `deploy_core.py`: **sin cambios** (contrato de muestra intacto). Tests siguen verdes tal cual.

## No-objetivos

- No fan-out por fuente (opcion 1) de dia uno; upgrade posterior si hace falta.
- No colector reutilizado entre ticks (su contexto creceria y mataria el aislamiento).
- No `.claude/agents/`: el colector se define inline.
- No tocar la logica de decision (`deploy_core`) ni el modelo de esperas no bloqueantes.

## Patrones aplicados

`focused-agent`, `context-management` / `excess-verbosity` (aislar salida cruda), `offload-deterministic`
(la decision sigue en `deploy_core`), `text-native` (queries reproducibles), `chain-of-small-steps`
(empezar por 1 colector/tick), `no sobredimensiones`.
