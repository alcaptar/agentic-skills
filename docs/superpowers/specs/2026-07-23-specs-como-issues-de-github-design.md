# La spec y el estado del run viven como un issue de GitHub

Fecha: 2026-07-23
Estado: aprobado (a slicing + implementacion; sin fase de plan)

## Problema

Hoy la spec y el estado del run viven en local y son efimeros: `.slice-runner/spec.md` (copia de la
spec), `state.json` (estado vivo), `runs.jsonl` (ledger), `stream.log` (stream en vivo), y un panel
TUI (`panel/slice-panel.py`) que los agrega. Todo gitignored y descartado al terminar el run; el
registro duradero eran solo las PRs mergeadas.

Esto tiene dos limitaciones: el seguimiento es **local** (nadie mas lo ve) y esta **fragmentado**
en varios ficheros + un panel que hay que arrancar. El usuario quiere un unico punto de seguimiento,
**publico y colaborativo**, donde el estado de cada slice se vea en todo momento sin infraestructura
local.

## Objetivo

Que la **spec y el estado del run vivan como un issue de GitHub**, unica fuente de verdad, viva y
duradera. Se elimina toda la capa de estado local (panel, `state.json`, `runs.jsonl`, `stream.log`,
copia local de la spec). El seguimiento se hace desde el issue; cualquiera con acceso al repo lo ve.

## Diseno

### Modelo de datos

- **1 issue = 1 feature = la spec.** El cuerpo del issue es la spec: titulo, intro y un bloque
  `## Slices` donde cada slice es una linea de task-list con su estado y sus AC.
- **El issue es la unica fuente de verdad del estado**, vivo (que se esta haciendo ahora) y duradero
  (que quedo hecho). No hay copia local ni JSON de estado.
- **`.slice-runner/` desaparece por completo.** No se crea ni se gitignora nada nuevo.

Formato del cuerpo (contrato que parsea la logica pura; el separador exacto se afina en
implementacion, pero debe ser parseable sin ambiguedad):

```markdown
# <titulo de la feature>

<intro / contexto opcional>

## Slices
- [x] slice-01 (cantidad-vo): Crear value object Cantidad `[mergeada]` PR #11
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [ ] slice-02 (ajustar-stock): Caso de uso AjustarStock `[esperando-merge]` PR #12
      AC: emite evento StockAjustado; no toca infra directamente
- [ ] slice-03 (extraer-repo): Extraer repositorio `[en-curso]`
      AC: ...
- [ ] slice-04 (backfill): Backfill de datos `[bloqueada: ci-roja]` PR #13
      AC: ...
- [ ] slice-05 (cleanup): Retirar el flag `[pendiente]`
      AC: ...
```

### Estados por slice

Codificados en la linea de la slice (marcador `[estado]` + `PR #N` cuando aplica):

- `pendiente` — aun no empezada.
- `en-curso` — implementando/verificando.
- `esperando-merge` — PR abierta, CI verde, esperando decision humana de merge.
- `mergeada` — PR mergeada. **Es el unico estado que marca el checkbox `[x]`.**
- `bloqueada: <motivo>` — CI roja no resuelta o verify terminal; deja el PR abierto.
- `abortada: presupuesto` — supero el presupuesto de la slice.

El `[x]` solo al merge mantiene la barra de progreso nativa de GitHub ("3/5") fiel a lo que
realmente esta en produccion/main, coherente con "el registro duradero son las PRs mergeadas" y con
"el merge lo decide el humano".

### Identificacion del issue

`slice-runner` necesita saber que issue leer/actualizar:

- Por **argumento explicito**: numero o URL del issue al invocar (`/slice-runner #42`). Para Nivel 2
  (`/loop`), el numero viaja en el input del loop, asi persiste sin fichero local.
- Si no se da, lista los issues abiertos del repo y pregunta cual (o `slice-spec` acaba de darte el
  numero recien creado). Autodescubrimiento por label queda como futuro (ver "No incluido").

### Flujo

- **`slice-spec`**: brainstorming -> slicing -> `gh issue create` con la spec en el cuerpo. Como es
  una accion visible/colaborativa (outward-facing), se **confirma antes de crear** el issue. Ya no
  escribe `.slice-runner/spec.md`. Devuelve el numero/URL del issue.
- **`slice-runner`**:
  1. Recibe el issue; `gh issue view <N> --json body` -> parsea las slices y su estado (logica pura).
     Elige la primera `pendiente`; si una slice quedo `esperando-merge`, retoma ahi en vez de
     reimplementar.
  2. En cada transicion macro reescribe **solo la linea de esa slice** en el cuerpo
     (read-modify-write: `gh issue view` -> reemplaza la linea -> `gh issue edit --body`).
  3. Abre PR con `Part of #N` (no `Closes`: una PR es una slice, no la feature). Mantiene el staging
     explicito + `gates.py pr-hygiene`.
  4. Espera CI con ticks no bloqueantes; marca `esperando-merge`.
  5. Al detectar el merge (paso 9 actual): marca `[x] mergeada` y encadena `deploy-watch`.
  6. Reintentos/bloqueo/presupuesto -> reflejados en el estado de la linea.
  7. Al terminar (todas `[x]`): comenta en el issue "todas las slices mergeadas" y **deja el cierre
     del issue al humano**.
- **`deploy-watch`**: en vez de escribir al stream local, **comenta su veredicto** (sano/degradado/
  inconcluso + tabla de las 4 senales) en el issue de la feature, referenciando la slice. El veredicto
  del deploy sigue siendo informativo (no cambia el checkbox).
- **Metricas durables** (`~/.claude/slice-runner/metrics.jsonl`): sin cambios; viven fuera del repo,
  no son "estado de slices" y sostienen el "cuando subir de nivel".

### Principio reformulado

"El estado del run es efimero" se sustituye por: **"el issue de GitHub es el estado del run, vivo y
duradero"**. Registro duradero = issue (intencion + estado) + PRs (codigo). Ya no hay dualidad
efimero/duradero ni descarte de estado al terminar.

### Separacion logica pura / I/O (para testear sin mocks de gh)

- **Logica pura (offline, unit-testeable):**
  - parsear el cuerpo del issue -> lista de slices con id, name, type, titulo, estado, AC.
  - renderizar/reemplazar la linea de una slice con un nuevo estado (dado el cuerpo actual, devuelve
    el cuerpo nuevo).
- **I/O `gh` (validada por el smoke real):** `gh issue create/view/edit/comment`, `gh pr ...`.

`slice-runner` compone: lee body (I/O) -> transforma (puro) -> escribe body (I/O). Solo el borde de
I/O queda fuera del unit test.

## Impacto por componente

- **`skills/slice-runner/SKILL.md`**: reescribir toda la seccion de estado/seguimiento
  (`state.json`/`runs.jsonl`/`stream.log`/setup/descarte) a "el estado vive en el issue"; ajustar
  pasos 1 (localizar issue), 7 (PR `Part of #N`), 8 (CI -> estado en issue), 9 (merge -> `[x]`), y
  Fin (comentar + cierre humano). Añadir la identificacion del issue.
- **`skills/slice-spec/SKILL.md`**: crear el issue en vez de escribir `spec.md`; principio "spec
  efimera en `.slice-runner/`" -> "la spec vive en el issue de GitHub".
- **`skills/deploy-watch/SKILL.md`**: seccion de integracion con el stream -> comentar en el issue.
- **`panel/`**: eliminar `slice-panel.py` y `panel/README.md` (deprecado).
- **`tests/`**: eliminar `test_panel.py`; añadir tests de la logica pura del cuerpo del issue.
- **scripts**: nuevo modulo de logica pura del cuerpo del issue (p. ej.
  `skills/slice-runner/scripts/issue_body.py`). `gates.py`: quitar `.slice-runner/` de
  `FORBIDDEN_PREFIXES` (ya no existe); mantener `docs/superpowers/*`. `metrics.py`: sin cambios.
- **`docs/`**: `design-notes.md` (estado en issue, no local), `README.md` (pipeline y seguimiento),
  `maturity-map.md` (menciona ledger/stream).
- **`CLAUDE.md` del repo**: quitar el panel y `.slice-runner/` de los principios y la seccion
  "Verificacion tras tocar el panel"; reflejar el nuevo modelo (estado en issue) y una verificacion
  nueva (smoke real / unit de la logica del cuerpo).
- **`smoke/`**: rehacer para gh real contra un repo remoto (crear issue, correr el loop, verificar
  el estado en el issue). Ya no es offline autocontenido.

## Testing

- **Unit (offline):** parseo del cuerpo (todos los estados, con y sin PR, checkbox `[x]` = mergeada,
  lineas no-slice ignoradas) y reemplazo de la linea de una slice preservando el resto del cuerpo.
- **Smoke real:** contra `alcaptar/agentic-skills` o un repo objetivo con CI: `slice-spec` crea el
  issue, `slice-runner` corre una slice y el estado del issue refleja el ciclo (pendiente -> en-curso
  -> esperando-merge -> mergeada `[x]`).

## Limitaciones asumidas

- **Sin `tail -f` en vivo**: el progreso se ve refrescando el issue, a nivel de slice (estado macro),
  no de micro-fase.
- **Dependencia de `gh`/red** para el estado (ya se dependia para PR/CI).
- **Nivel 3 (paralelo)**: varios runners editando el mismo cuerpo del issue = condicion de carrera.
  Queda anotado; se resolveria con serializacion o sub-issues por slice, fuera de este cambio.
- **Concurrencia humano/agente**: si un humano edita el cuerpo a la vez que el agente, el
  read-modify-write puede pisar. En uso personal secuencial el riesgo es bajo; se mitiga editando
  solo la linea de la slice.

## No incluido (YAGNI / futuro)

- Autodescubrimiento del issue por label `slice-runner`.
- Sub-issues por slice / issue epico (se descarto: 1 issue = 1 feature).
- Cierre automatico del issue (lo hace el humano).
- CI de GitHub Actions para los unit tests (se documenta `python3 -m pytest`).

## Verificacion

- `python3 -m pytest` verde (logica pura del cuerpo + gates + metrics; ya sin test_panel).
- Busqueda de `.slice-runner`, `state.json`, `stream.log`, `slice-panel` en el repo sin resultados
  fuera de design-docs historicos.
- Smoke real: el issue refleja el ciclo completo de una slice.
