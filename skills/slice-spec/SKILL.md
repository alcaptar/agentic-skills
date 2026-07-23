---
name: slice-spec
description: Crea (o valida) una spec de slices en el formato exacto que consume slice-runner. Usar cuando el usuario quiera "escribir una spec", "montar el plan de slices", "trocear una feature en slices", "slice-spec", o tenga una idea/feature y necesite convertirla en una spec ejecutable por slice-runner. Envuelve superpowers:brainstorming para el diseno y luego emite la spec en su formato exacto (checklist de slices con nombre y AC). Modo `validate` para revisar una spec existente contra el contrato. No implementa codigo: produce la spec que slice-runner luego ejecuta.
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
- **Guia el corte, no lo delega.** El troceo lo lleva esta skill cargando su cerebro de slicing
  (`references/slicing.md`): walking skeleton, heuristica ordenada, hamburger como motor de
  composicion, calibrador de tamano y validacion del corte. La skill es la **fuente de verdad** del
  slicing; `hamburger-method`/`story-splitting` son profundizacion opcional, no el motor.
- **Slices verticales y pequenas.** Cada slice es una rebanada entregable de punta a punta con AC
  propios, no una capa tecnica suelta.
- **AC obligatorios por slice.** Sin AC no hay puerta de verificacion en slice-runner: toda slice
  declara criterios de aceptacion concretos y comprobables.
- **La spec es efimera.** Se escribe en `.slice-runner/spec.md` (gitignored); slice-runner la
  descarta al terminar el run. No la comitees ni la guardes en `docs/`.

## Contrato de formato (lo que el script espera)

La spec es un **checklist de slices**. Un solo formato, sin variantes.

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
  No hace falta declarar la lista de types validos: el commit lo redacta el agente (sabe conventional
  commits) y su unica puerta determinista es la higiene del diff (`gates.py pr-hygiene`).
- Debajo de cada slice, una o mas lineas indentadas con `AC:` describiendo criterios concretos
  (y donde viven los tests si aplica). Las **restricciones duras** (p. ej. "no toca infra
  directamente") se expresan como un AC comprobable mas.
- Checkbox inicial siempre `[ ]` (pendiente). slice-runner lo pasa a `[x]`/`[!]` durante el run.
- Una feature de **una sola slice** = un checklist con una unica linea.

## Steps — modo autoria (por defecto)

1. **Invoca `superpowers:brainstorming`** y sigue su proceso para entender intencion, proponer
   enfoques y validar el diseno con el usuario. **Excepcion al terminal de brainstorming:** no
   invoques `writing-plans`; el paso siguiente es emitir la spec de slices (pasos 2-4).
2. **Trocea en slices verticales (guia activa).** Carga `references/slicing.md` y aplica su
   procedimiento sobre el diseno aprobado: identifica el **walking skeleton** (slice #1), genera el
   resto por la **heuristica ordenada**, y **solo abre dialogo con la persona** (opciones graduadas
   por capa, estilo hamburger) cuando el corte no es obvio o una slice supera el budget. Valida cada
   slice contra los criterios de validez y el conjunto contra el **test de despriorizacion** e
   **igualdad de tamano**. Elige `name` kebab-case por slice y, si aplica, su `type`.
3. **Escribe la spec** en `.slice-runner/spec.md` (crea `.slice-runner/` y su `.gitignore` con `*`
   + `!.gitignore` si no existen, para que nunca se comitee). Cumple el contrato de formato al pie
   de la letra.
4. **Auto-validacion.** Aplica el checklist de `validate` (abajo) sobre lo que acabas de escribir y
   corrige inline antes de entregar.
5. **Cierra** diciendo la ruta de la spec y que se ejecuta con `/slice-runner` (o `/loop /slice-runner`
   para encadenar todas las slices en Nivel 2).

## Steps — modo `validate <ruta>`

Revisa una spec existente contra el contrato y reporta desviaciones (con `regla + linea`). Ofrece
corregirlas. Checklist:

- Es un checklist de slices (`## Slices` con lineas `- [ ] slice-NN ...`).
- Cada slice tiene `slice-NN`, `(name)` kebab-case unico, titulo y al menos una linea `AC:`.
- Si aparece un `type` en el parentesis, es un type de conventional commit (no hay lista normativa
  que validar aqui: el commit lo redacta y valida el flujo de slice-runner).
- Checkboxes validos (`[ ]`/`[x]`/`[!]`).
- Ninguna slice sin AC (sin AC no hay puerta de verificacion en slice-runner).
- Nombres unicos y estables (no colisionan al derivar ramas `slice/NN-name`).
- **Calidad del corte** (contra `references/slicing.md`): cada slice es vertical, desplegable sola y
  reversible; el conjunto pasa el **test de despriorizacion** (hay >=1 slice que se podria posponer)
  y tiene **tamano equilibrado**; ninguna slice nombrada por capa tecnica salvo horizontal
  justificado; cuando una slice sustituye comportamiento en prod, nombra su mecanismo seguro (flag /
  expand-contract).

Si todo cumple: reporta `spec valida` y recuerda que se ejecuta con `/slice-runner`.

## Fin

Reporta: ruta de la spec, numero de slices y sus nombres, y el comando para ejecutarla
(`/slice-runner`, o `/loop /slice-runner` para Nivel 2). No implementes nada: ese es el trabajo de
`slice-runner`.
