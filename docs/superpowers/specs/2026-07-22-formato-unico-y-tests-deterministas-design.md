# Formato unico de spec + endurecimiento de los scripts deterministas

Fecha: 2026-07-22
Estado: aprobado (pendiente de plan de implementacion)

## Problema

La herramienta soporta **dos** formatos de spec:

- **Formato A** — checklist de slices (`## Slices` con `- [ ] slice-NN (name): ...`).
- **Formato B** — plan de una sola slice estilo superpowers (fichero entero = 1 slice, con
  `Goal`, `Global Constraints`, `Task`/`Step` internos y estado en cabecera).

El Formato B nacio para consumir directamente los `docs/superpowers/plans/*.md` de un repo real.
Pero el flujo canonico hoy es `slice-spec` (que envuelve brainstorming y **no** llama a
`writing-plans`) emitiendo siempre el checklist. El Formato B ya no aporta poder expresivo sobre el
A y en cambio genera superficie transversal: obliga a **detectar** formato, **derivar** AC de
`Goal`/`Tasks`/`Global Constraints`, llevar el estado en cabecera, y mantener un contrato duplicado
en tres sitios (slice-spec, slice-runner, panel). Es el origen directo de un bug del panel
(mal-parsea los `Step` de B como si fueran slices).

Ademas hay tres defectos independientes del numero de formatos:

- **#1** `gates.py --json` esta definido en el parser padre; su docstring y el `SKILL.md` lo
  documentan tras el subcomando, donde argparse lo rechaza con exit 2. La puerta "autoritativa"
  falla ante el uso que ella misma ensena.
- **#3** La puerta determinista `commit-msg` de `gates.py` valida algo que el agente ya sabe hacer
  (conventional commits) y encima obliga a mantener una lista de types que diverge entre `gates.py`
  (11) y `slice-spec` (9). Es determinismo innecesario: se elimina la puerta y la lista.
- **#5** `metrics.py` `_load` hace `json.loads` sin proteccion; una linea corrupta en el log durable
  append-only revienta el `report` de todos los repos. El panel ya es defensivo; metrics no.
- **#7** El resumen del panel no cuenta `en curso` ni `abortada-presupuesto` (suman al total pero a
  ningun contador).

No existen tests de los scripts deterministas (`gates.py`/`metrics.py`/panel), solo el smoke E2E
manual. `offload-deterministic` descansa en que esos scripts sean fiables, y el `maturity-map`
marca "self-verification loop you trust" como requisito para subir a Nivel 2.

## Objetivo

Un **unico formato de spec** (el checklist) y unos scripts deterministas fiables y testeados.
Menos superficie, un solo contrato, y la confianza en el loop que pide el mapa de madurez.

Alcance acordado: Enfoque 3 (unificar formato + coherencia de contrato + robustez + tests) e incluir
el fix #7 del panel.

## Diseno

### 1. El formato unico

Desaparece la dualidad "Formato A / Formato B". Queda **el** formato de spec (el checklist actual),
sin numerar:

```markdown
# <titulo de la feature>

## Slices
- [ ] slice-01 (name): <titulo de la slice>
      AC: <criterio 1>; <criterio 2>; tests en <ruta>
- [ ] slice-02 (refactor: otro-name): <titulo>
      AC: <criterios>
```

- Reglas duras (sin cambios): `slice-NN` orden de dos digitos; `(name)` kebab-case unico; `type`
  opcional dentro del parentesis (`(refactor: name)`), por defecto `feat`; checkbox `[ ]`/`[x]`/`[!]`;
  al menos una linea `AC:` por slice.
- **Las restricciones duras son AC.** Lo que en el Formato B eran `Global Constraints` (lo que el
  verificador comprobaba una a una) pasa a expresarse como un AC comprobable mas. Un solo concepto.
- Una feature de **una sola slice** = un checklist con una sola linea. No se pierde ese caso de uso.
- Se elimina la **autodeteccion de formato**. Si el `.md` no es este checklist, `slice-runner` para
  y pide una spec valida (o sugiere `/slice-spec`).

### 2. Impacto por componente

- **`slice-spec/SKILL.md`** (fuente unica del contrato de formato):
  - Elimina la seccion "Formato B" y toda referencia a formatos "A/B".
  - Paso "elige formato" desaparece: siempre emite el checklist.
  - `validate`: elimina las ramas de B (cabecera `> Nombre:`, `Goal`, derivacion de AC).
  - El `type` opcional del parentesis se documenta **sin lista normativa** de types (el agente sabe
    conventional commits); `validate` deja de comprobar la lista de types.
- **`slice-runner/SKILL.md`**:
  - "Formatos de spec soportados" pasa de dos a uno; elimina la autodeteccion.
  - Elimina la derivacion de AC desde `Goal`/`Tasks`/`Global Constraints` y el estado en cabecera.
  - Verificador: elimina el item "Global Constraints (Formato B)" (queda cubierto por "conformidad
    con los AC").
  - Seleccion de slice = la indicada por el usuario o la primera `[ ]`.
  - Paso 7 (abrir PR): elimina la "puerta determinista del mensaje" (`commit-msg`). El commit sigue
    siendo `type(name): resumen` redactado por el agente; el `name` como scope sigue viniendo
    determinista de la spec, y el staging explicito lo garantiza `pr-hygiene`.
- **`panel/slice-panel.py`**:
  - Un solo parser (el actual del checklist). Se **endurece** para contar como slice **solo** las
    lineas cuyo contenido case `slice-NN`; una linea `- [ ]` que no sea una slice se ignora (hoy se
    pinta como slice, origen del mal-parseo del Formato B).
  - **#7**: el resumen cuenta tambien `en curso` y `abortada-presupuesto`.
- **`gates.py`**:
  - **Se elimina la puerta `commit-msg` y la constante `COMMIT_TYPES`** (ver seccion 3). El script
    queda con una sola puerta: `pr-hygiene`.
  - **#1**: `--json` se define en el subparser `pr-hygiene` para que funcione tras el subcomando,
    como documenta el uso. Se ajusta el docstring.
  - `FORBIDDEN_PREFIXES` **se mantiene intacto**: `docs/superpowers/specs/` y `plans/` son un
    backstop para design-docs/planes, no artefactos del Formato B. (Correccion sobre una suposicion
    inicial erronea.)
- **`metrics.py`**:
  - **#5**: `_load` envuelve `json.loads` en `try/except json.JSONDecodeError` y salta lineas
    corruptas, igual que hace el panel.
- **`smoke/` y `docs/`**:
  - `smoke/README.md`: "formato A" -> "el formato" (la fixture ya es un checklist de 1 slice).
  - `docs/design-notes.md`: sincroniza con "todo `.slice-runner/` efimero y gitignored" (hoy dice
    `runs.jsonl` versionado y coste en el ledger, desactualizado #2) y refleja la unificacion de
    formato.
  - `README.md`: elimina la mencion a los dos formatos.

### 3. #3 — eliminar el determinismo del commit-msg

El agente sabe que es un conventional commit; validar el mensaje con un script es determinismo
innecesario. Se elimina la puerta `commit-msg` de `gates.py` y su lista `COMMIT_TYPES`. Con ello
desaparece la duplicacion de la lista de types (no hay lista en `gates.py` ni en `slice-spec`, luego
nada que sincronizar) y #3 se disuelve en la causa, no en el sintoma.

Que se mantiene: el mensaje sigue siendo `type(name): resumen`, pero lo redacta el agente con su
conocimiento; el `name` es el scope y sigue viniendo determinista de la spec, y el staging explicito
lo garantiza `pr-hygiene`. Criterio de `offload-deterministic`: se offloadea a script solo la regla
mecanica con coste de error alto que el modelo no garantiza por si mismo (que no entre la
spec/ledger en la PR), no lo que el modelo hace bien de fabrica (redactar un conventional commit).

### 4. Tests (#6)

Carpeta `tests/` en la raiz, `pytest`, sin dependencias de terceros nuevas.

- **`test_gates.py`** (solo `pr-hygiene`, la unica puerta que queda):
  - fail-closed sin `--allow`; artefacto prohibido staged; spec staged; subconjunto declarado OK;
    nada staged. Usa un repo git temporal (`tmp_path` + `git init`). Parametrizado.
- **`test_metrics.py`**:
  - `_aggregate`: `primer_intento` excluye abort-con-0-reintentos; porcentajes y medias; log vacio.
  - `_load` salta lineas corruptas (fix #5).
  - Roundtrip `record` -> `report` con `--path` en `tmp_path`.
- **`test_panel.py`**:
  - `_parse_spec`: slice con name; con `type`; sin name (deriva slug); linea `- [ ]` no-slice
    ignorada (endurecimiento).
  - `_split_name`; `_estado_de` (la fase viva de `state.json` manda sobre el ledger;
    `esperando-merge`); `_resolve_spec_path`.
- **Import del panel**: su fichero lleva guion (`slice-panel.py`), no importable por nombre. Se carga
  con `importlib.util.spec_from_file_location` desde `conftest.py` (fixture), sin renombrarlo (lo
  citan README y CLAUDE.md). `gates.py` y `metrics.py` se importan por nombre via `pythonpath` de
  pytest.
- **`pyproject.toml`** minimo en la raiz: `[tool.pytest.ini_options]` con `pythonpath` a los dirs de
  scripts, y `testpaths = tests`.

## No incluido (YAGNI / otros specs)

- CI de GitHub Actions para correr los tests: se documenta `python3 -m pytest`; el workflow queda
  fuera de este spec.
- Nivel 2/3 de autonomia y sus guardrails: sin cambios aqui.

## Verificacion

- `python3 -m pytest` verde.
- `python3 panel/slice-panel.py . --once` renderiza sin error (verificacion que exige CLAUDE.md).
- `gates.py` (`pr-hygiene`) y `metrics.py` responden como documentan (incl. `--json` tras el
  subcomando), y `gates.py` ya no expone `commit-msg`.
- Busqueda de "Formato B"/"formato A"/"Global Constraints" en el repo sin resultados fuera de este
  design-doc historico.
