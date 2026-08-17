# Cerebro de observabilidad de la slice

Reference-doc de `slice-spec`. Se carga **solo cuando el slicing detecta que hay senal que
disenar** (`reference-docs` + `context-management`), y tambien lo carga el **implementador** de
`slice-runner` cuando la slice tiene que instrumentar algo.

Dos partes: la **escalera** (universal, vale para cualquier repo) y el **stack concreto** -la
libreria de instrumentacion, el repo de alertas y el de paneles-, que es un overlay por organizacion
y no viaja aqui. Sin overlay la escalera sigue valiendo; lo que hay que averiguar es contra que.

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

## El stack concreto: overlay por organizacion

La escalera de arriba es universal; para bajarla hacen falta tres datos que **son de cada
organizacion**: que emite ya la libreria de instrumentacion sin escribir una linea (escalon 1), como
se enriquece lo que ya emite (escalon 2), y donde viven las alertas y los paneles -en que repo, con
que ruta y con que se validan-.

Eso vive en un fichero aparte, `references/observabilidad.local.md`, que la skill **carga si existe**
y que no viaja en este repo. Sin el la escalera sigue funcionando: lo que se pierde es el atajo de
saber de antemano que serie sale gratis, y hay que ir a mirarlo al repo que se toca.

Lo que el overlay tiene que contestar:

| Pregunta | Para que escalon |
|---|---|
| Que primitivas de la libreria instrumentan solas, y que series emiten | 1 |
| Como se anade un atributo, un label o un span a lo que ya emite | 2 |
| Como se declara una metrica de negocio propia y como se testea su emision | 3 |
| Donde se abre un gap de la libreria | 4 |
| En que repo viven las alertas, con que ruta, que labels son obligatorias y con que se validan | slice de alerta |
| En que repo viven los paneles y que control tienen | slice de panel |

**Una slice de alerta es TDD-able de verdad**, la tenga quien la tenga: lint y validate contestan
*"¿parsea el YAML y compila el PromQL?"*, y `promtool test rules` contesta la otra pregunta, *"cuando
estas metricas se comportan asi, ¿dispara la alerta?"*. Se escribe el test con `input_series`
primero, se mira que falla, y luego la regla. Criterios de aceptacion tipicos: dispara con la serie
esperada, **no** dispara por debajo del umbral, y las labels que exija el repo de infra estan
presentes con un `for:` no-cero.

**Un panel normalmente es capa eximida**: si su unico control es "el JSON parsea", no se fuerza
test-first, se comprueba renderizando despues del deploy, y su `SENAL` suele ser `exenta` con el
motivo escrito.

## Orden forzoso

No se puede alertar ni pintar una serie que nadie emite. No es preferencia, es dependencia:

```
slice-N    emite la senal (repo de app)        SENAL: la serie aparece con sus labels
    | deploy + deploy-watch confirma la serie viva
slice-N+1  alerta (repo de infra)              SENAL: ALERTS{alertname="X"} presente y == 0
slice-N+2  panel (repo de paneles)             SENAL: exenta - render manual
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
SENAL: prometheus ALERTS{alertname="AjusteStockFallido"} presente y == 0 en 24h; advisory
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
- Prometheus — *Unit Testing for Rules* (`promtool test rules`).
