# Diseno: nombres de slice, conventional commits, PR limpia y skill `slice-spec`

Fecha: 2026-07-21
Estado: aprobado

Origen: feedback del usuario sobre `slice-runner`:
1. Que cada slice tenga un nombre.
2. Que al hacer el spec se cumpla el formato que espera el script; una skill liviana
   que llame al brainstorming de superpowers y sirva para dejar el formato del spec.
3. En las slices, que solo suba a la PR los ficheros de la slice, no planes ni otros artefactos.
4. Que use conventional commits.

Aclaracion clave del usuario: la spec y el ledger **no se comitean**; al terminar la
implementacion se **descartan**.

## Decisiones (cerradas con el usuario)

- **Nombre de slice**: la spec declara solo `name` (kebab-case); el `type` de conventional
  commit es `feat` por defecto, con override opcional.
- **Descarte de estado**: la spec + `.slice-runner/` viven gitignored durante todo el run y
  se descartan cuando no quedan slices pendientes (fin del run), no por slice.
- **Skill**: `slice-spec`, con modo autoria (envuelve brainstorming) y modo `validate`.

## 1. Nombre de slice (feedback 1)

### Formato A (checklist)

El `name` va entre parentesis tras el id:

```markdown
- [ ] slice-01 (cantidad-vo): Crear value object Cantidad con validacion de rango
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
```

- `slice-01` = id (orden + estado del checkbox `[ ]`/`[x]`/`[!]`).
- `cantidad-vo` = **name**, estable y determinista.
- Override de type opcional: `(refactor: cantidad-vo)`. Name a secas ⇒ `feat`.
- Rama: `slice/01-cantidad-vo` (derivada de id + name, no del texto libre).

### Formato B (fichero = una slice)

El name va en cabecera, junto a `> Estado:`:

```markdown
> Nombre: cantidad-vo
> Estado: pendiente
```

### Compatibilidad

Si una spec no trae `(name)`, se deriva un slug del titulo como hoy, con aviso. No rompe
specs existentes ni el smoke.

## 2. Conventional commits (feedback 4)

- Commit y titulo de PR = `feat(<name>): <resumen>`.
- Type por defecto `feat`; override desde la spec (`(refactor: name)`).
- En el paso de alineamiento, si el cambio claramente no es `feat` y la spec no lo declaro,
  se confirma el type con el usuario (barato; evita `silent-misalignment`).

## 3. PR solo con ficheros de la slice + estado efimero (feedback 3 + aclaracion)

- **`.slice-runner/` entero gitignored**, incluido `runs.jsonl` (antes versionado). La spec
  vive por defecto en `.slice-runner/spec.md`, tambien gitignored.
- **Regla de staging (nucleo del punto 3)**: el subagente implementador devuelve la lista
  explicita de ficheros de codigo que toco para los AC. "Abrir PR" hace `git add <esos
  ficheros>`, **nunca `git add -A`/`.`**. El verificador comprueba que el diff staged no
  contiene spec/plan/ledger/docs.
- **Descarte al terminar el run**: cuando no quedan slices pendientes (todas hecha/bloqueada),
  slice-runner hace `rm -rf .slice-runner/` (+ la spec). Durante el run persisten como memoria
  para el contexto-fresco/loop.

## 4. Skill `slice-spec` (feedback 2)

Skill fina, dos modos:

- **Autoria (por defecto)**: invoca `superpowers:brainstorming` para explorar idea y diseno.
  Al aprobar el diseno, en lugar del `docs/superpowers/specs/...` que produce brainstorming,
  emite una spec en el formato exacto de slice-runner (Formato A con `slice-NN (name): titulo`
  + AC, o Formato B si es una sola slice), escrita en `.slice-runner/spec.md` (gitignored).
  Reengancha la cola de brainstorming: la spec ES el plan que consume slice-runner, sustituye
  el "terminal = writing-plans".
- **`validate`**: dado un spec existente, valida contra el contrato del script (ids, names
  kebab-case, AC presentes, checkboxes validos) y reporta desviaciones; puede corregirlas.
  Es `offload-deterministic` (check de formato pequeno) + `check-alignment`.

Se apoya en `ai-patterns` (`text-native`, `check-alignment`) y remite a
`hamburger-method`/`story-splitting` para el troceo. No re-piensa el diseno: delega en
brainstorming; su trabajo es el contrato de formato.

## 5. Cambios de arrastre

- **`panel/slice-panel.py`**: `_SLICE_ID` parsea el `(name)`/`(type: name)` opcional; muestra
  el name; compat con specs sin name; sigue renderizando con `--once`.
- **`smoke/`**: `fixture/spec.md` gana name (`slice-01 (fizzbuzz-core): ...`); `README.md`
  actualiza expectativas (`feat(fizzbuzz-core): ...`, ledger gitignored). `sample-output/`
  queda como ejemplo ilustrativo.
- **`CLAUDE.md` (repo)** — cambio de principio: "El estado vive en el repo" se invierte a: el
  estado del run (spec + `.slice-runner/`) es efimero y gitignored, se descarta al terminar el
  run; durante el run es la memoria del contexto-fresco; el registro duradero son las PRs
  mergeadas.
- **`README.md` (repo)**: menciona `slice-spec` y el modelo de estado efimero.

## Consecuencias asumidas

- Se **invierte un principio no-negociable** previo del repo ("el estado vive en el repo").
- El coste-por-slice del ledger pasa a ser efimero (solo del run actual); no hay historico
  versionado.
