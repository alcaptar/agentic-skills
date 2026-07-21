---
name: slice-spec
description: Crea (o valida) una spec de slices en el formato exacto que consume slice-runner. Usar cuando el usuario quiera "escribir una spec", "montar el plan de slices", "trocear una feature en slices", "slice-spec", o tenga una idea/feature y necesite convertirla en una spec ejecutable por slice-runner. Envuelve superpowers:brainstorming para el diseno y luego emite el formato (Formato A checklist o Formato B una-slice) con nombre por slice y AC. Modo `validate` para revisar una spec existente contra el contrato del script. No implementa codigo: produce la spec que slice-runner luego ejecuta.
---

# Slice Spec

STARTER_CHARACTER = [slice-spec]

Emite `[slice-spec]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Skill fina que produce la **spec** que `slice-runner` consume, en su formato exacto. No re-piensa
el diseno del producto: **delega el diseno en `superpowers:brainstorming`** y su unico trabajo es
el **contrato de formato** (los nombres de slice, los AC, los checkboxes que el script y el panel
saben parsear). Es el `check-alignment` + `text-native` del flujo: la spec en markdown es el
artefacto compartido entre humano y agente.

Par natural: `/slice-spec` escribe la spec, `/slice-runner` la ejecuta.

Dos modos:

- **Autoria (por defecto):** brainstorming -> spec bien formada en `.slice-runner/spec.md`.
- **`validate <ruta>`:** revisa una spec existente contra el contrato y reporta (o corrige) desviaciones.

## Principios

- **No implementa.** No escribe codigo ni tests; produce la spec. El estado terminal es una spec
  valida, no un plan de `writing-plans` ni una PR.
- **El diseno lo lleva brainstorming.** No dupliques su trabajo (entender intencion, proponer
  enfoques, validar diseno). Esta skill reengancha solo la **cola**: cuando el diseno esta
  aprobado, en vez de `writing-plans` emite la spec de slices. La spec ES el plan que consume
  slice-runner.
- **Formato es contrato.** La spec debe parsearla el panel (`panel/slice-panel.py`) y el paso 1
  de slice-runner sin ambiguedad. Si no cumple el contrato de abajo, no esta terminada.
- **Cada slice tiene nombre.** `name` kebab-case, estable, determinista: alimenta rama y scope de
  commit en slice-runner. Sin nombre no hay spec bien formada.
- **Slices verticales y pequenas.** Cada slice es una rebanada entregable de punta a punta con AC
  propios, no una capa tecnica suelta. Para el troceo, apoyate en `hamburger-method` y
  `story-splitting` si la feature es grande o ambigua.
- **AC obligatorios por slice.** Sin AC no hay puerta de verificacion en slice-runner: toda slice
  declara criterios de aceptacion concretos y comprobables.
- **La spec es efimera.** Se escribe en `.slice-runner/spec.md` (gitignored); slice-runner la
  descarta al terminar el run. No la comitees ni la guardes en `docs/`.

## Contrato de formato (lo que el script espera)

`slice-runner` autodetecta dos formatos. Emite uno de los dos, sin mezclarlos.

### Formato A — checklist de slices (por defecto)

```markdown
# <titulo de la feature>

## Slices
- [ ] slice-01 (nombre-kebab): <titulo de la slice>
      AC: <criterio 1>; <criterio 2>; tests en <ruta>
- [ ] slice-02 (otro-nombre): <titulo>
      AC: <criterios>
```

Reglas duras:

- Cada slice es una linea `- [ ] slice-NN (name): titulo`. `NN` = orden de dos digitos; `name` =
  kebab-case unico dentro de la spec.
- Type opcional para conventional commits: `slice-03 (refactor: extraer-repo): ...`. Sin type ⇒ `feat`.
- Debajo de cada slice, una o mas lineas indentadas con `AC:` describiendo criterios concretos
  (y donde viven los tests si aplica).
- Checkbox inicial siempre `[ ]` (pendiente). slice-runner lo pasa a `[x]`/`[!]` durante el run.

### Formato B — plan de una sola slice (estilo superpowers)

Usalo cuando la feature es **una sola** slice con pasos internos:

```markdown
# Slice — <titulo>

> Nombre: nombre-kebab
> Type: feat        (opcional; por defecto feat)
> Estado: pendiente

## Goal
<que consigue la slice, en una-tres frases>

## Global Constraints
- <restriccion dura 1 que el verificador debe comprobar>

### Task 1 — <nombre>
- [ ] Step 1: <accion>
  Expected: <verificacion / interfaz esperada>
```

Reglas duras:

- Un fichero = una slice. El `name` va en la cabecera `> Nombre:`.
- Los AC se derivan del `Goal` + los `Expected`/`Interfaces` de los Tasks + los `Global Constraints`.
- Los `- [ ] Step N` son el plan interno; el estado de la slice se lleva a nivel de fichero (`> Estado:`).

## Steps — modo autoria (por defecto)

1. **Invoca `superpowers:brainstorming`** y sigue su proceso para entender intencion, proponer
   enfoques y validar el diseno con el usuario. **Excepcion al terminal de brainstorming:** no
   invoques `writing-plans`; el paso siguiente es emitir la spec de slices (pasos 2-4).
2. **Trocea en slices verticales.** A partir del diseno aprobado, define las slices: cada una
   entregable, con AC propios, en orden de dependencia. Si la feature es grande o el troceo no es
   obvio, usa `hamburger-method`/`story-splitting`. Elige `name` kebab-case por slice y, si aplica,
   su `type`.
3. **Elige formato.** Varias slices ⇒ Formato A. Una sola slice con pasos internos ⇒ Formato B.
4. **Escribe la spec** en `.slice-runner/spec.md` (crea `.slice-runner/` y su `.gitignore` con `*`
   + `!.gitignore` si no existen, para que nunca se comitee). Cumple el contrato de formato al pie
   de la letra.
5. **Auto-validacion (offload-deterministic).** Aplica el checklist de `validate` (abajo) sobre lo
   que acabas de escribir y corrige inline antes de entregar.
6. **Cierra** diciendo la ruta de la spec y que se ejecuta con `/slice-runner` (o `/loop /slice-runner`
   para encadenar todas las slices en Nivel 2).

## Steps — modo `validate <ruta>`

Revisa una spec existente contra el contrato y reporta desviaciones (con `regla + linea`). Ofrece
corregirlas. Checklist:

- Formato detectable (A o B) sin ambiguedad.
- Formato A: cada slice tiene `slice-NN`, `(name)` kebab-case unico, titulo y al menos una linea `AC:`.
- Type, si aparece, es valido (`feat|fix|refactor|chore|docs|test|perf|build|ci`).
- Formato B: cabecera con `> Nombre:` kebab-case; `Goal` presente; AC derivables.
- Checkboxes validos (`[ ]`/`[x]`/`[!]`).
- Ninguna slice sin AC (sin AC no hay puerta de verificacion en slice-runner).
- Nombres unicos y estables (no colisionan al derivar ramas `slice/NN-name`).

Si todo cumple: reporta `spec valida` y recuerda que se ejecuta con `/slice-runner`.

## Fin

Reporta: ruta de la spec, formato (A/B), numero de slices y sus nombres, y el comando para
ejecutarla (`/slice-runner`, o `/loop /slice-runner` para Nivel 2). No implementes nada: ese es el
trabajo de `slice-runner`.
