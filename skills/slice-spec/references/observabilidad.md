# Cerebro de observabilidad de la slice

Reference-doc de `slice-spec`. Se carga **solo cuando el slicing detecta que hay senal que
disenar** (`reference-docs` + `context-management`), y tambien lo carga el **implementador** de
`slice-runner` cuando la slice tiene que instrumentar algo.

Dos partes: la **escalera** (universal, vale para cualquier repo) y el **stack concreto** (la
libreria de monitoring, el repo de alertas y el de paneles). Si trabajas en un repo que no usa ese
stack, la escalera sigue valiendo; la segunda parte se sustituye por lo que ese repo tenga.

## Filosofia

Un cambio no esta hecho cuando pasa la CI: esta hecho cuando **puedes ver en produccion que hace lo
que pretendia**. Eso es *observability-driven development*: decides la telemetria **antes** de
implementar, la instrumentacion viaja **con** el codigo (no en una slice "de telemetria" futura), y
la usas para confirmar el cambio vivo.

**La senal tiene dos asserts, y por eso no basta con un criterio de aceptacion:**

| | assert | quien lo verifica | cuando |
|---|---|---|---|
| **Emision** | el codigo emite la metrica/log/span con sus labels | test + `slice-verifier` | pre-merge |
| **Valor vivo** | el contador sube / el error no aparece tras el deploy | `deploy-watch` | post-deploy |

La emision es un **criterio de aceptacion normal** y falsable (borra la instrumentacion y el test
cae). El valor vivo **no es testeable**: por eso vive en su propia linea `SENAL:`, que consume
`deploy-watch`.

## Cuando procede (y cuando no)

**Exige `SENAL`** si la slice cambia **comportamiento observable en produccion**: endpoint, consumer,
job/cronjob, flag que conmuta un camino, cambio de regla de negocio con efecto visible.

**Exenta** (declarandolo y justificandolo, `SENAL: exenta - <motivo>`):

- refactor puro sin cambio de comportamiento;
- value object o helper interno sin efecto observable propio;
- migracion de schema cuyo efecto aun no se usa (su verificacion es el `SELECT` del plan);
- panel de Grafana (no emite serie: se comprueba renderizando).

La exencion **se escribe**. Ausencia silenciosa no es exencion: es la senal que nadie penso.

**Vara de falsabilidad, mirando a prod:** *nombra la senal que cambiaria si esto se rompe vivo*. Si
no puedes nombrarla, la slice no es observable — y eso es un defecto de diseno que se arregla **aqui**,
en el slicing, no en el incidente.

## Escalera de senal

Baja un escalon **solo si el anterior no basta**. El escalon 1 existe para no instrumentar de mas:
la mayoria de las slices ya tienen senal y solo hay que **apuntar** a ella.

1. **¿Ya existe la senal gratis?** Si el codigo que tocas ya esta instrumentado por el framework o la
   libreria del repo, la serie ya existe. La `SENAL` apunta a ella: **cero codigo nuevo**.
2. **¿Basta enriquecer lo que ya emite?** Anadir un atributo al log, un label existente, un span
   extra. Coste minimo, sigue siendo la libreria.
3. **¿Hace falta senal de negocio nueva?** Metrica propia inyectada por DI, con su **test de
   emision**. Es codigo de produccion de **esta** slice, no de una futura.
4. **¿La libreria no lo expresa idiomaticamente?** Es un **gap de la libreria**: se declara y se
   resuelve o se acota **ahi**. Nunca una instrumentacion ad-hoc paralela a la libreria: duplicar el
   mecanismo es peor que el gap, porque el gap se arregla una vez y la duplicacion se hereda.

## Stack de Mercadona

### La libreria: `mo.pypi.monitoring`

Lo que ya emite **sin escribir una linea** (escalon 1):

| Primitiva | Emite |
|---|---|
| `@instrumented_action` (clase con `execute`) | `application_action_executed_total{action_name,component,service}`, `application_action_duration_seconds`, span APM `application.action`, logs JSON de inicio/fin |
| `@instrumented_command` (clase con `handle`, cronjobs) | `application_command_executed_total`, `application_command_duration_seconds`, transaccion APM, errores a Sentry (push gateway: requiere `MONITORING_METRICS_PUSH_GATEWAY`) |
| middlewares Django / FastAPI | `application_http_requests_total{method,path,status}`, `application_http_request_duration_seconds`, `application_http_request_latency_seconds` (histograma **opt-in** via `MONITORING_HTTP_LATENCY_HISTOGRAM_ENABLED`, con buckets pensados para `histogram_quantile()` y **ratios de good-events para SLI**), tamanos, `application_http_queue_duration_seconds` |
| `contrib/rele`, `contrib/kafka_connector` | metricas de consumers/producers |
| `Instrumentation().logger` | logger JSON configurado; los `extra` van namespaced por `APPLICATION_NAME` |

Escalon 2 — enriquecer sin metrica nueva:

```python
@instrumented_action(log_attributes=["order_id", "center_code"])
class AjustarStock:
    def execute(self, params: AjustarStockParams) -> None: ...
```

```python
with SpanContext(name="recalculo_stock", span_type="application.action.recalculo"):
    ...
```

Escalon 3 — metrica de negocio propia. `MetricRepository` es un **puerto abstracto**: se inyecta, no
se instancia dentro del dominio.

```python
AJUSTES = Counter(
    "application_stock_ajustado_total",
    "Ajustes de stock aplicados.",
    ["motivo", "component", "service"],
)

class AjustarStock:
    def __init__(self, metrics: MetricRepository) -> None:
        self._metrics = metrics

    def execute(self, params: AjustarStockParams) -> None:
        ...
        self._metrics.increment(AJUSTES, motivo=params.motivo)
```

Y su **test de emision** — el "observability test": no testea logica de negocio, testea que la
telemetria cumple el contrato. Sin mocks: la libreria trae el doble in-memory.

```python
def test_registra_el_ajuste_en_la_metrica() -> None:
    metrics = InMemoryMetricRepository()

    AjustarStock(metrics=metrics).execute(un_ajuste(motivo="rotura"))

    assert metrics.get_value("application_stock_ajustado_total", motivo="rotura") == 1
```

**Naming**: `application_*_total` para contadores, labels `component`/`service` como en el resto.
**Nunca** `instance_name` derivado del nombre del pod: rompe en cada deploy (lo dice el propio
`CLAUDE.md` de la libreria); usa las labels estables.

**Gap de la libreria (escalon 4)**: si lo que necesitas no se puede expresar con la libreria (falta un
tipo de metrica, un decorador no cubre tu tipo de proceso, no hay forma de anadir un label), abre issue
en `mercadona/mo.pypi.monitoring` describiendo el caso y **dilo en la spec**. Un contador a mano en
paralelo a la libreria no es una solucion: es el gap, heredado.

### Alertas: `mercadona/mercadona.online.gke`

Slice **propia**, siempre. Repo distinto ⇒ PR distinta por definicion, y mezclarla con la metrica
romperia la higiene del diff.

| | |
|---|---|
| Ruta | `templates/prometheus/prometheus-server/teams/<equipo>/<equipo>-alerting-rules-<env>.tpl` |
| Equipos | `shop`, `checkout`, `in-store`, `supply`, `market`, `data`, `flota`, `ultima-milla`, `primera-milla`, `in-colmena`, `calidad`, `staff`, `ser-humano`, `vyp`, `sre`, `shared-infra` |
| Envs | `prod`, `sta`, `mercanetes`, `training` (un `.tpl` por env) |
| Forma | ConfigMap de k8s dentro de un Go template: **escaping embebido** (`{{"{{"}} $labels.deployment {{"}}"}}`). Se rompe facil; leer `templates/CLAUDE.md` antes de tocar |
| Labels obligatorias | `severity`, `channel`, `mo_team`, `label_mercadona_es_team_owner` (legacy), y `for:` no-cero — lo fuerza `validate_alerting_rules.sh` |
| Puertas | `make run-manifestr-local` (render) + `make test_prometheus_rules` (**`promtool test rules`**) |
| Tests | `tests/prometheus/rules/<env>/<equipo>/*.yml` |
| CI en PR | `.github/workflows/prometheus-alerting-rules-validation.yml` |

**Una alerta es TDD-able de verdad.** Su README separa las dos preguntas: lint/validate/check
responden *"¿parsea el YAML y compila el PromQL?"*; `promtool test rules` responde *"cuando estas
metricas se comportan asi, ¿dispara la alerta?"*. Escribe el test con `input_series` primero, mira que
falla, y luego la regla:

```yaml
rule_files:
  - rules.yml
evaluation_interval: 1m
tests:
  - input_series:
      - series: 'application_stock_ajustado_fallido_total{deployment="shop-api"}'
        values: '0+1x10'
    alert_rule_test:
      - eval_time: 6m
        alertname: ShopAjusteStockFallido
        exp_alerts:
          - exp_labels: {severity: warning, mo_team: shop, deployment: shop-api}
```

Criterios de aceptacion tipicos de una slice de alerta: el test `promtool` que dispara con la serie
esperada, el que **no** dispara por debajo del umbral, labels obligatorias presentes y `for:`
no-cero.

`SENAL` tipica: `prometheus ALERTS{alertname="X"} presente y == 0 en 24h; advisory` — es decir, la
regla **cargo** y **no genera falsos positivos**. Es advisory a proposito: una alerta recien puesta que
dispara no tumba el deploy, te dice que el umbral esta mal calibrado.

### Paneles: `mercadona/mo.sre.grafana-configs`

Slice **propia**, la ultima de la cadena y la primera candidata a posponer.

| | |
|---|---|
| Ruta | `settings/<env>/dashboards-files/<Equipo>/<panel>.json` (raiz de `dashboards-files/` = carpeta `General` de Grafana) |
| Envs | `production`, `sta`, `mercanetes` |
| CI | Jenkinsfile que **solo sube a GCS en `master`**: sin validacion en PR, sin tests |

No hay puerta mas alla de "el JSON parsea", asi que es **capa eximida** (delta 1 de `slice-runner`,
como los modelos ORM): no fuerces test-first. La puerta es "JSON valido + el panel renderiza y sus
queries devuelven datos", y eso se comprueba tras el deploy. Su `SENAL` normalmente es `exenta`, con el
motivo escrito.

## Orden forzoso

No se puede alertar ni pintar una serie que nadie emite. No es preferencia, es dependencia:

```
slice-N    emite la senal (repo de app)        SENAL: la serie aparece con sus labels
    | deploy + deploy-watch confirma la serie viva
slice-N+1  alerta (gke, carpeta del equipo)    SENAL: ALERTS{alertname="X"} presente y == 0
slice-N+2  panel (grafana-configs)             SENAL: exenta - render manual
```

Coherente con **"Aislamiento de infra"** de `slicing.md` (PRs distintas: despliega, observa, y luego el
paso siguiente) y con el **test de despriorizacion**: el panel es exactamente la slice que puedes
posponer sin perder el core.

## Como se escribe la linea `SENAL:`

Texto libre **estructurado**, no un DSL. `deploy-watch` habla en terminos de negocio y su colector
construye la query concreta, asi que basta con ser inequivoco:

    SENAL: <fuente> <expresion o serie> ; <assert vivo con su ventana> ; critical|advisory

```
SENAL: prometheus rate(application_stock_ajustado_total{motivo="rotura"}[5m]) > 0 en 10m post-deploy; critical
SENAL: elasticsearch logs con ajuste_rechazado y campo motivo presentes tras el primer rechazo; advisory
SENAL: prometheus ALERTS{alertname="ShopAjusteStockFallido"} presente y == 0 en 24h; advisory
SENAL: exenta - refactor puro, ningun comportamiento cambia
```

Malas, y por que:

```
SENAL: se monitoriza con Grafana                 <- no nombra serie, ventana ni assert: no es refutable
SENAL: la latencia no empeora                    <- ¿que percentil, medido donde, contra que baseline?
SENAL: revisar que funcione                       <- prosa
```

`critical` frena el `go` de `deploy-watch` si el breach persiste; `advisory` informa. Por defecto,
**advisory**: marca `critical` solo lo que el usuario siente (errores, indisponibilidad), igual que en
`monitoring.md`.

## Anti-patterns

- **Alerta o panel en la misma PR que la metrica.** Repos distintos y ademas mezcla concerns; el
  orden forzoso existe porque la serie tiene que estar viva primero.
- **Alertar una serie que aun no ha llegado a prod**: la regla se evalua contra nada y no dispara
  nunca (o dispara al reves si es un `absent()`).
- **Instrumentacion ad-hoc paralela a la libreria** en vez de declarar el gap.
- **Declarar `SENAL` con lo que el test ya prueba** ("el contador se incrementa" es el criterio de
  emision, no la senal viva).
- **Dejar la telemetria para "la slice de observabilidad" del final**: es la aplazable que nunca llega,
  y es justo lo que este doc corrige de la heuristica 9.
- **`SENAL` ausente sin declarar exencion**: pasa desapercibida y degrada el veredicto del deploy al
  generico, sin que nadie lo haya decidido.
- **Metrica de alta cardinalidad** (ids de pedido, emails, uuid como label): revienta Prometheus. Eso
  va al log estructurado o al span, no a un label.

## Fuentes

- Charity Majors, Liz Fong-Jones, George Miranda — *Observability Engineering*, cap. 11
  (Observability-Driven Development). Honeycomb — *Authors' Cut: Making the Move to ODD*.
- Splunk — *Observability-Driven Development Explained*. oneuptime — *ODD with OpenTelemetry*
  (observability contract: "estos tests no testean logica de negocio; testean que la telemetria que
  produce el codigo cumple el contrato").
- `mercadona/mo.pypi.monitoring` — `docs/docs/instrumentation.md`, `docs/docs/index.md`,
  `monitoring/metrics.py`, `monitoring/test_utils/repositories.py`.
- `mercadona/mercadona.online.gke` — `tests/prometheus/README.md`, `templates/CLAUDE.md`,
  `templates/prometheus/prometheus-server/teams/`.
- `mercadona/mo.sre.grafana-configs` — `README.md`.
