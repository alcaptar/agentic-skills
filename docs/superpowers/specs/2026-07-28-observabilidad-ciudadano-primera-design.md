# Observabilidad como ciudadano de primera categoria

Fecha: 2026-07-28

## Problema

El flujo `slice-spec` -> `slice-runner` -> `deploy-watch` verifica muy bien **antes** de mergear
(test por AC, verificador adversarial, CI) y muy mal **despues**. `deploy-watch` elige sus senales
por *blast radius inferido del diff* (`monitoring.md`: RED en el edge + USE del recurso), asi que su
veredicto solo puede afirmar **"el servicio esta sano"**, nunca **"el comportamiento que introdujo
slice-02 esta pasando en produccion"**.

Los dos sintomas concretos:

1. **La senal no se disena.** `slicing.md` ya pide, en "Defaults universales", que cada slice defina
   "como se comprueba su comportamiento vivo". Es prosa que nadie parsea ni consume: el eslabon
   existe en el papel y se pierde en el contrato. Peor, la heuristica 9 clasifica la telemetria como
   **capacidad transversal aplazable**, que contradice de frente lo que este diseno establece.
2. **La senal no existe.** Si la slice no emite nada nuevo, no hay nada que mirar tras el deploy, y
   eso se descubre tarde: en el incidente, no en el slicing.

## Decision

La observabilidad se decide **en el slicing** (es ahi donde el corte todavia se puede cambiar), se
declara **en el contrato de la spec**, se construye **dentro de la slice** cuando falta, y se
comprueba **viva** tras el deploy.

### El hallazgo que hace esto barato: la senal tiene dos asserts

| | assert | quien lo verifica | cuando |
|---|---|---|---|
| **Emision** | el codigo emite la metrica/log/span con sus labels | test + `slice-verifier` | pre-merge |
| **Valor vivo** | el contador sube / el error no aparece tras el deploy | `deploy-watch` | post-deploy |

La emision es un **AC normal** (falsable: borra la instrumentacion y el test cae). El valor vivo
**no es testeable** y hoy no tiene donde vivir: es lo que justifica un campo propio.

Coincide con la practica de la industria (**ODD**, *Observability Engineering* cap. 11; Honeycomb;
Splunk): decides la telemetria antes de implementar, la instrumentacion viaja con el codigo, y no das
el cambio por hecho hasta mirarlo en produccion. El "observability contract" (oneuptime) es
exactamente esto: telemetria declarada aparte de la logica, con tests que "no testean logica de
negocio: testean que la telemetria que produce el codigo cumple el contrato".

## Contrato: `SENAL:` y `REPO:`, hermanas de `AC:`

```markdown
## Fuentes de convencion
- doc: CLAUDE.md
- skill: .claude/skills/duplicate-action

### mercadona/mercadona.online.gke
- doc: CLAUDE.md
- doc: templates/CLAUDE.md
- doc: tests/prometheus/README.md

## Slices
- [ ] slice-02 (ajustar-stock): Caso de uso AjustarStock [pendiente]
      AC: emite evento StockAjustado; incrementa stock_ajustado_total{motivo}; tests en test/application/
      SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
- [ ] slice-05 (alerta-ajuste-fallido): Alerta de ajustes fallidos [pendiente]
      REPO: mercadona/mercadona.online.gke
      AC: promtool test con input_series de 3 fallos dispara ShopAjusteStockFallido; labels severity/channel/mo_team; for no-cero
      SENAL: prometheus ALERTS{alertname="ShopAjusteStockFallido"} presente y == 0 en 24h; advisory
- [ ] slice-06 (panel-ajuste-stock): Panel de ajustes de stock [pendiente]
      REPO: mercadona/mo.sre.grafana-configs
      AC: settings/production/dashboards-files/Shop/ajuste-stock.json es JSON valido y sus queries usan las series de slice-02
      SENAL: exenta - el render del panel se comprueba a mano; no hay serie propia que emitir
```

Reglas:

- **`SENAL:` es obligatoria** en specs nuevas si la slice **cambia comportamiento observable en
  produccion** (endpoint, consumer, job, flag que conmuta un camino). Exentas: refactor puro sin
  cambio de comportamiento, value objects internos, migraciones sin efecto visible aun. **La exencion
  se declara y se justifica**: `SENAL: exenta - <motivo>`. Ausencia silenciosa no es exencion.
- **Falsabilidad, al otro extremo.** La vara actual es "nombra el cambio de produccion que haria
  fallar este AC". La `SENAL` es la misma vara mirando a prod: **"nombra la senal que cambiaria si
  esto se rompe vivo"**. Si no puedes nombrarla, la slice no es observable, y eso es un defecto de
  diseno detectable en el slicing.
- **`SENAL:` es texto libre estructurado**, no un DSL: `<fuente> <expresion> ; <assert vivo> ;
  critical|advisory`. Encaja con el contrato del colector de `deploy-watch`, donde el hilo principal
  habla en terminos de negocio y el colector construye la query concreta.
- **`REPO:` declara el repo destino de la slice.** Ausente = el repo del issue (el de la app).
- **Alertas y paneles son siempre slices propias** (repos distintos ⇒ PRs distintas por definicion).

## Escalera de senal (se aplica durante el slicing)

Baja un escalon solo si el anterior no basta. El escalon 1 es el que evita instrumentar de mas.

1. **¿Ya la da la libreria gratis?** Con `mo.pypi.monitoring`, una accion/comando/endpoint
   instrumentado ya emite `application_action_executed_total{action_name,component,service}`,
   `application_action_duration_seconds`, `application_http_requests_total{method,path,status}`,
   `application_http_request_latency_seconds` (opt-in, documentado para SLI good-event ratios), spans
   APM `application.action` y logs JSON de inicio/fin. La `SENAL` apunta a esa serie: **cero codigo
   nuevo**.
2. **¿Basta enriquecer lo que ya emite?** `@instrumented_action(log_attributes=[...])`, un
   `SpanContext`, un `extra={}` en el logger.
3. **¿Metrica de negocio nueva?** `Counter`/`Gauge`/`Summary`/`Histogram` + `MetricRepository`
   inyectado (puerto abstracto: DI, encaja con hexagonal), con su **test de emision** via
   `InMemoryMetricRepository.get_value(nombre, **labels)`. Es codigo de produccion de **esta** slice.
4. **¿La libreria no lo expresa idiomaticamente?** Es un **gap**: se declara (issue en
   `mo.pypi.monitoring`) y se resuelve o se acota ahi. **Nunca** un contador ad-hoc paralelo a la
   libreria.

Naming: `application_*_total`, labels `component`/`service`. Nunca `instance_name` basado en
pod-name: rompe en cada deploy (lo dice el propio CLAUDE.md de la libreria).

## Orden forzoso

No se puede alertar ni pintar una serie que nadie emite. No es preferencia, es dependencia:

```
slice-N    emite la senal (repo de app)      SENAL: la serie aparece con sus labels
    | deploy + deploy-watch confirma la serie viva
slice-N+1  alerta (gke, carpeta del equipo)  SENAL: ALERTS{alertname="X"} presente y == 0 (sin falsos positivos)
slice-N+2  panel (grafana-configs)           SENAL: exenta / render manual
```

Encaja con dos cosas que ya estan en `slicing.md`: **"Aislamiento de infra"** (PRs distintas;
despliega, observa, y luego el siguiente paso) y el **test de despriorizacion** — el panel es
exactamente la slice que se puede posponer sin perder el core.

## Los dos repos destino (asimetricos)

### Alertas: `mercadona/mercadona.online.gke`

| | |
|---|---|
| Ruta | `templates/prometheus/prometheus-server/teams/<equipo>/<equipo>-alerting-rules-<env>.tpl` (16 equipos; envs `prod`/`sta`/`mercanetes`/`training`) |
| Forma | ConfigMap de k8s en Go template, con escaping embebido delicado (`{{"{{"}} $labels.deployment {{"}}"}}`) |
| Convencion validada por CI | labels `severity`, `channel`, `mo_team`, `label_mercadona_es_team_owner`; `for:` no-cero (`validate_alerting_rules.sh`) |
| Puertas deterministas | `make run-manifestr-local` + `make test_prometheus_rules` -> **`promtool test rules`** (`input_series` -> `exp_alerts`), en `tests/prometheus/rules/<env>/<equipo>/` |
| CI en PR | `.github/workflows/prometheus-alerting-rules-validation.yml` |
| Fuentes de convencion | `CLAUDE.md` raiz, `templates/CLAUDE.md`, `tests/prometheus/README.md`, comandos `.claude/commands/` |

**Una alerta es TDD-able de verdad.** Su propio README lo separa: las tres primeras puertas
responden "¿parsea el YAML y compila el PromQL?"; `test_alerting_rules.sh` responde otra pregunta,
*"cuando estas metricas se comportan asi, ¿dispara la alerta?"*. Se escribe el test con
`input_series` primero, se ve fallar, y luego la regla. Una slice de alerta encaja **entera** en el
modelo de `slice-runner`.

### Paneles: `mercadona/mo.sre.grafana-configs`

| | |
|---|---|
| Ruta | `settings/<env>/dashboards-files/<Equipo>/<panel>.json` |
| CI | Jenkinsfile que solo sube a GCS en `master`. Sin validacion en PR, sin tests |

Sin puerta mas alla de "el JSON parsea": es el caso claro de **capa eximida** (delta 1 de
`slice-runner`, como los modelos ORM). La puerta es "JSON valido + el panel renderiza y sus queries
devuelven datos", y eso se comprueba post-deploy.

## Cross-repo: `REPO:` por slice, un solo issue

`slice-runner` asumia **un** repo. Se elige `REPO:` por slice frente a un issue propio en cada repo
destino porque el issue unico es la fuente de verdad del run (principio del repo: una feature = un
issue); partirlo en dos ahorra codigo y lo cobra en trazabilidad, que es justo lo que el diseno del
issue protege.

Consecuencia critica: **las fuentes de convencion pasan a ser por repo.** Medir una alerta de gke con
la vara del repo de la app es exactamente el `silent-misalignment` que esa seccion existe para
evitar: la vara de gke es otra (Manifestr, escaping embebido, politica de labels). Formato:
subsecciones `### <org>/<repo>` dentro de `## Fuentes de convencion`; las lineas antes de cualquier
`###` son las del repo de la app.

`gates.py` ya acepta `--repo <ruta>` en sus tres subcomandos (`git -C`, `cwd=repo`): el cross-repo
**no requiere cambios en los scripts de puertas**.

`metrics.py --repo` sigue siendo el repo **del issue**, no el destino: si no, las slices de una misma
feature se repartirian en dos cubos de metricas y la calibracion del loop dejaria de agregar bien.

## Cambios por fichero

| Fichero | Cambio |
|---|---|
| `skills/slice-spec/references/observabilidad.md` (**nuevo**) | La escalera completa (universal) + el stack de Mercadona (tabla de `mo.pypi.monitoring`, rutas/convenciones/puertas de gke, rutas de grafana-configs) + como redactar la `SENAL` con ejemplos. `reference-docs`: se carga solo cuando el slicing detecta que hay senal que disenar |
| `skills/slice-spec/references/slicing.md` | Seccion corta "Observabilidad de la slice" (regla, exencion, orden forzoso, alertas/paneles como slices propias, puntero a `observabilidad.md`); **corregir la heuristica 9** (lo aplazable es telemetria fina/alerting, no la senal minima); anadir a "Validacion del corte" y a "Anti-patterns" |
| `skills/slice-spec/SKILL.md` | Contrato: `SENAL:` y `REPO:`; obligatoriedad y exencion declarada; vara de falsabilidad extendida a la senal; paso de troceo aplica la escalera; checklist de `validate` |
| `skills/slice-runner/scripts/issue_body.py` | `Slice.senal: list[str]`, `Slice.repo: str \| None`; `Fuente.repo: str \| None` + subsecciones `### <repo>`; `fuentes_para(fuentes, repo)`; `render_fuentes_section` agrupa por repo. Acepta `SENAL:` y `SEÑAL:`; canonico `SENAL:` |
| `tests/test_issue_body.py` | Parseo de `SENAL:`/`REPO:`, fuentes por repo, y que `set_slice_estado` preserva ambas lineas |
| `skills/slice-runner/SKILL.md` | Principio "la observabilidad es parte de la slice"; pasos 1 (parsear + fuentes del repo de la slice), 2 (comandos **del repo destino**), 3 (alinear incluye repo y senal), 4 (rama en el destino), 5 (delta de observabilidad + escalera), 7 (vara del repo destino), 8 (PR en el destino con `Part of mercadona/<repo-app>#N`), 9 (CI del destino), 10 (`deploy-watch` con la senal) |
| `agents/slice-verifier.md` | Item de rubrica `observabilidad`: `SENAL` declarada no exenta ⇒ instrumentacion en el diff de **produccion** (no solo en test) y con la libreria, no ad-hoc. Alta si la senal declarada no puede cumplirse con lo que el diff introduce. Delimitado contra el item 5 (`conformidad-ac`) por la regla "un defecto, un hallazgo" |
| `skills/deploy-watch/SKILL.md` + `references/monitoring.md` | La `SENAL` declarada **manda** sobre las inferidas por blast radius, con su criticidad; si la senal declarada **no se puede medir**, el veredicto es `inconclusive`, no `go`; para slices de gke/grafana-configs no hay rollout de app que vigilar y el veredicto se apoya en la senal declarada |

## Compatibilidad

- **Specs legacy sin `SENAL:`**: `slice-runner` **avisa y sigue**, no bloquea. Mismo precedente que
  `(name)` ausente. Bloquear romperia todos los issues existentes, y la obligatoriedad vive donde
  toca: en el contrato de `slice-spec` (una spec nueva sin `SENAL` no es valida).
- **`REPO:` ausente** = repo del issue: todo lo existente sigue funcionando sin tocar el issue.
- **`parse_fuentes(body)`** conserva su firma y su retorno (`list[Fuente]`); el campo `repo` entra con
  default `None`.

## Por que no se bloquea con la senal ausente (fail-closed vs friccion)

La seccion `## Fuentes de convencion` es fail-closed porque sin vara el verificador **no puede
funcionar**: ejecutar seria teatro. Una `SENAL` ausente no invalida la verificacion pre-merge; degrada
la comprobacion post-deploy al veredicto generico de hoy, que es lo que ya teniamos. Bloquear ahi seria
sobredimensionar, y ademas incoherente con el criterio de degradacion del repo: se puede **declarar**
la degradacion en el artefacto (el comentario de `deploy-watch` en el issue dice que la slice no
declaro senal), asi que se degrada y se declara.

## Nota operativa

`agents/slice-verifier.md` **no se relee en caliente** (el registro de agentes se cachea al primer
load de la sesion). Tras tocarlo hace falta **sesion nueva** para probarlo; si no, el smoke valida la
definicion vieja en silencio.

## Fuentes

- *Observability Engineering* (Majors, Fong-Jones, Miranda), cap. 11 — Observability-Driven Development.
- Honeycomb — *Authors' Cut: Making the Move to Observability-Driven Development*.
- Splunk — *Observability-Driven Development Explained*.
- oneuptime — *How to Implement Observability-Driven Development with OpenTelemetry* (observability
  contract; "estos tests no testean logica de negocio: testean que la telemetria cumple el contrato").
- `mercadona/mo.pypi.monitoring` — `docs/docs/instrumentation.md`, `monitoring/metrics.py`,
  `monitoring/test_utils/repositories.py`.
- `mercadona/mercadona.online.gke` — `tests/prometheus/README.md`, `templates/prometheus/prometheus-server/teams/`.
- `mercadona/mo.sre.grafana-configs` — `README.md`.
