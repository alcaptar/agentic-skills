# El verificador juzga el indice, y el verde de la CI hay que demostrarlo

Fecha: 2026-07-30
Estado: aprobado

## Origen

Esta spec no sale de una idea: sale del **primer smoke real** de `slice-runner` (issue #3, PR #4 de
`alcaptar/agentic-skills`, 2026-07-29). El loop se recorrio entero -seleccion, alineacion, TDD,
controles, verificador `PASA` sin hallazgos, PR draft, CI verde- y **los diez criterios de
`smoke/README.md` pasaron**. Lo que aparecio son dos defectos del tramo final que ningun test offline
podia ver, porque los dos son sobre el **estado de git** y sobre la **forma de una invocacion
externa**, no sobre logica pura.

Es el argumento del `maturity-map` en vivo: se llevaba una semana construyendo y ninguna corriendo.

## Intencion

Hoy el tramo final de `slice-runner` **no puede completarse tal y como esta escrito**, y su espera de
CI **se cuelga en silencio** cuando el agente adivina mal el nombre de un campo de `gh`. Uno de los
dos defectos bloquea el run; el otro lo deja indistinguible de una CI lenta hasta que salta el
timeout.

### Defecto 1: dos controles piden estados de git incompatibles

- `diff-bundle` (paso 7) calcula `git diff <base>...HEAD`: solo ve lo **commiteado**.
- El commit esta en el paso 8, **despues**.
- Y `pr-hygiene` (paso 8) mira `git diff --cached`: necesita el indice **staged y sin commitear**.

En el orden documentado los dos no pueden estar satisfechos a la vez. En el smoke, el paso 7 devolvio
`FALLA: sin cambios respecto a origin/master` con la slice entera implementada y verde.

Comprobado ademas por el lado feo: `pr-hygiene` con el indice vacio **falla en cerrado** ("nada
staged"), no pasa vacuo. Si hubiera pasado, el atajo obvio -commitear primero- habria dejado un
control fail-closed aprobando la nada. No es el caso, y eso es merito del script.

### Defecto 2: el poll de CI degrada a "nunca verde"

El paso 9 dice "cada tick consulta `gh pr checks --json`" sin fijar los campos. `gh pr checks --json`
**no tiene campo `conclusion`** -sus campos son `bucket`, `completedAt`, `description`, `event`,
`link`, `name`, `startedAt`, `state`, `workflow`-, pero `conclusion` **si** existe en
`gh run list --json` y en `statusCheckRollup`. Es la conjetura natural y es la equivocada solo en este
subcomando.

En el smoke se pidio `--json name,state,conclusion`, `gh` respondio `Unknown JSON field`, el tick lo
leyo como "sin checks aun" y reporto eso **doce ticks, cuatro minutos**, con la CI verde desde el
segundo 14. El modo de fallo no es un error: es una **degradacion silenciosa** a "nunca verde" que se
come el timeout. En un run desatendido (Nivel 2 con `/loop`) es una slice colgada sin causa visible.

Fiarse del exit code pelado no arregla nada por si solo: `gh pr checks` devuelve **1 tanto con la CI
roja como con una invocacion invalida**, asi que el bug de hoy pasaria a leerse como "CI roja" y el
paso 9 reintentaria al implementador contra un fallo inexistente.

## Decisiones

### 1. `diff-bundle` diffea el indice staged, no HEAD

`escribe_diff_bundle` pasa de `git diff <base>...HEAD` a **`git diff --cached --merge-base <base>`**.

Se conserva intacta la razon de ser de los tres puntos -que el avance de la base no aparezca como
borrados, y el verificador no cace violaciones fantasma- pero con `--merge-base`, que es su
equivalente para `--cached`. Verificado en un playground aislado:

| forma | resultado con la base avanzada |
|---|---|
| `git diff --cached --merge-base main` | solo el fichero de la slice |
| `git diff --cached $(git merge-base main HEAD)` | igual, pero dos invocaciones |
| `git diff --cached main` | el de la slice **mas el avance de main**, el fantasma |
| `git diff --cached main...HEAD` | **error de sintaxis**: los tres puntos no valen con `--cached` |

Se elige la primera: una sola invocacion y sin shell-out para el merge-base.

**Cambio del comportamiento por defecto, sin flag.** Un `--staged` opcional reintroduce el juicio del
agente exactamente donde la docstring actual presume de haberselo quitado ("el rango lo fija el script
y no el juicio de un modelo"), y ademas recrea el modo de fallo de hoy: olvidar el flag devuelve el
diff vacio. El unico llamante es el paso 7; no hay compatibilidad que romper.

### 2. Orden nuevo del tramo 7-8

```
git add <ficheros declarados por el implementador>
pr-hygiene      (indice cargado: su input de diseno)
diff-bundle     (--cached --merge-base: exactamente lo que sera el commit)
verificador     -> FALLA: vuelve al paso 5, sin commit que deshacer
                -> PASA: commit, push, PR
```

Tres propiedades, y la tercera no se vio hasta el playground:

1. **Nada se commitea hasta `PASA`.** Los reintentos no dejan rastro y el invariante de "una slice, un
   commit" -del que depende que el verificador no pueda auditar el orden test-antes-de-implementacion,
   ver la decision del 2026-07-27- se sostiene **sin `git commit --amend`**. El amend era el precio de
   la alternativa barata (reordenar sin tocar codigo) y es una instruccion sutil que un agente falla.
2. **El verificador juzga exactamente lo que ira en la PR.** Hoy juzga `base...HEAD`, que es lo mismo
   pero solo despues del commit.
3. **`pr-hygiene` pasa a dar integridad al input del verificador.** Un fichero untracked es
   **invisible** a `git diff --cached` (verificado), asi que un test nuevo sin stagear no lo veria el
   verificador; y `pr-hygiene`, que corre justo antes, es precisamente lo que afirma que el conjunto
   staged es igual a la lista declarada por el implementador. Hoy los dos controles son
   independientes: en el orden nuevo uno protege al otro. Y como entre la verificacion y el commit no
   se stagea nada, no hay ventana para meter un fichero que el verificador no haya visto.

Se mantiene el fail-closed: sin nada staged, `diff-bundle` devuelve `FALLA` con "nada staged", igual
que hoy devuelve FALLA con cero cambios.

### 3. Subcomando `ci-status`: el verde se demuestra

    controles.py ci-status --repo <ruta> --pr <n> [--json]
      -> verde | rojo | pendiente | sin-checks | desconocido

Encapsula la invocacion de `gh`, los nombres de campo y el mapeo de exit codes, para que ningun
agente vuelva a recordarlos mal. Es el principio del repo aplicado donde acaba de fallar: lo mecanico
lo resuelve el script, cuyo exit code es autoritativo, no la memoria del modelo.

**La decision que importa: solo es `verde` un todo-pass explicito con al menos un check.** Todo lo
demas cae en `pendiente`, `rojo`, `sin-checks` o `desconocido`. Asi no hay que adivinar que hace `gh`
exactamente ante una PR sin CI configurada -no se ha podido verificar y no se supone-: el riesgo queda
invertido, y lo que no se puede demostrar verde no lo es. Misma forma que `pr-hygiene` con el indice
vacio.

Dos cosas que **no** lleva, y el motivo:

- **Ni `--watch` ni polling.** Devuelve un tiro y sale. El ticking lo hace el harness (background mas
  notificacion), que es el principio de esperas no bloqueantes; un script que poll-ea **es** la shell
  bloqueante que la skill prohibe.
- **`sin-checks` no colapsa en `verde`.** Seria un defecto peor que el de hoy: hoy se cuelga, y
  colapsando reportaria verde una PR sin ninguna CI.

El paso 9 llama a este subcomando por tick. `verde` y `rojo` se comportan como hoy; `pendiente` sigue
tickeando.

### 4. `bloqueada: ci-indeterminada`, motivo nuevo

`desconocido` y `sin-checks` no son ni verde ni rojo: no son un fallo de la slice, son **que no se
puede medir**. Reusar `ci-roja` seria mentir en el registro duradero, y dejarla en `esperando-merge`
afirmaria un verde que nunca hubo. Asi que hace falta un motivo nuevo: la slice para en
`bloqueada: ci-indeterminada`, con el estado concreto y la PR abierta, igual que en `ci-roja`.

Consecuencia deliberada: eso obliga a anadirlo a `issue_body.MOTIVOS_BLOQUEADA`, y el test de contrato
del 2026-07-29 **exigira** que `SKILL.md` y el parser lo declaren los dos. Es el test haciendo
exactamente su trabajo en el primer cambio que toca ese vocabulario.

## Descartado

- **Reordenar solo `SKILL.md`, sin tocar codigo.** Es el arreglo de minutos, pero obliga a `--amend`
  en cada reintento del verificador para no romper el invariante de un commit por slice, deja un
  commit de trabajo rechazado, y no arregla nada del paso 9: seguiria dependiendo de que el agente
  recuerde nombres de campo, que es justo lo que fallo.
- **Dar a `diff-bundle` un modo working-tree** (`git diff <base>` con el arbol de trabajo, sin
  stagear). Descartado por el mismo hallazgo del playground: **los untracked no aparecen**, asi que un
  test nuevo -el caso normal en una slice- seria invisible al verificador. Requiere stagear primero de
  todos modos, con lo que se convierte en la decision 1 por otro camino.
- **Fijar solo el nombre de campo en el paso 9** (`--json name,state,bucket`). Arregla el sintoma de
  hoy y deja el mecanismo: el siguiente campo mal recordado vuelve a colgar el loop en silencio.

## Lo que arrastra

- **`skills/slice-runner/SKILL.md`**: pasos 7, 8 y 9. El paso 7 pierde la mencion al rango
  `<base>...HEAD` y gana el orden nuevo; el paso 9 pasa a `ci-status` con los cinco estados.
- **`skills/slice-runner/scripts/controles.py`**: `escribe_diff_bundle` y el subcomando `ci-status`.
- **`skills/slice-runner/scripts/issue_body.py`**: `ci-indeterminada` en `MOTIVOS_BLOQUEADA`.
- **`tests/test_controles.py`**: diff staged desde el branch-point; que el avance de la base no salga
  como fantasma; que un untracked no entre; fail-closed con indice vacio; y el mapeo de estados de
  `ci-status` con la salida de `gh` **inyectada**, sin red.
- **`tests/test_skill_contracts.py`**: un test de contrato mas, con el patron del 2026-07-29 -extraer
  de los dos lados y comparar-: los estados que `SKILL.md` documenta para `ci-status` tienen que ser
  exactamente los que emite el script.
- **`smoke/README.md`**: su "Criterio de smoke OK" describe el tramo final y no fija el orden. Es el
  documento que habria cazado esto, asi que se actualiza con el orden y con la comprobacion del
  `sin-checks`.
- **`docs/design-notes.md`**: entrada de decision apuntando aqui.

## Verificacion

- `make check` verde (linting, mypy strict, pytest).
- Los tests nuevos, **vistos en rojo antes de darlos por buenos**, con la misma disciplina que los
  tests de contrato del 2026-07-29: mutar el codigo y comprobar que cada test cae por su motivo.
- Re-correr el smoke completo contra GitHub y comprobar que el tramo 7-9 pasa **sin intervencion
  manual**, que es lo que hoy no ocurre.
