# Smoke test de slice-runner (real, contra GitHub)

**Todo lo que sigue documenta el flujo anterior**: la skill `/slice-runner` orquestando a mano los
subagentes `agents/slice-implementer.md` y `agents/slice-verifier.md`, sobre el formato viejo de un
solo issue con checklist (`Part of #N`). Ese flujo ya no vive en este repo -esta congelado en
`alcaptar/agentic-skills-legacy`, ver "Instalacion" en `../README.md` para donde apunta hoy el
symlink de esa skill-, asi que reproducir el "Como ejecutarlo" de mas abajo exige instalarla desde
ahi. El flujo que conduce hoy una slice (`uv run slice-runner run`, formato padre + subissue con
`Closes #<subissue>`) no tiene todavia su propio smoke de I/O real contra `gh`; hasta que exista,
este es el unico smoke de I/O real de este repo y por eso sigue vivo, no porque sea el smoke del
flujo vigente.

Harness para validar el loop de `slice-runner` de punta a punta **contra GitHub de verdad**: el
estado del run vive en un issue, asi que el smoke ya no es offline. Es la forma de ganar confianza en
el "self-verification loop" antes de subir al Nivel 2 (ver `../docs/maturity-map.md`).

La logica pura (parseo y reescritura del cuerpo del issue) se testea offline en `../tests/`
(`python3 -m pytest`). Este smoke cubre lo que esos unit tests no pueden: la **I/O real** contra
`gh` (issue create/view/edit/comment, pr) y el CI de GitHub Actions.

## Qué valida

El **inner loop critico** de extremo a extremo: `slice-spec` crea el issue -> `slice-runner` lee el
issue, alinea, implementa con TDD, verifica con un subagente independiente, abre PR (`Part of #N`),
espera CI verde y **refleja el estado de la slice en el issue** en cada transicion.

Eso es el camino feliz. Los cuatro caminos de fallo (`bloqueada: controles`, `bloqueada: verify`,
`ci-roja`, `ci-indeterminada`) tambien se sondean aqui, pero no salen solos: hay que provocarlos, y la
provocacion de cada uno esta escrita en "Como provocar los caminos de fallo", mas abajo.

## Requisitos

- `gh` autenticado (`gh auth status`) con permiso para crear issues y PRs.
- Un **repo remoto propio** (p. ej. un fork/clon de la fixture) con GitHub Actions que corra los
  controles (`make linting && make check-types && make test`) en `pull_request`. **La receta de
  `ci-indeterminada` es la excepcion declarada**: necesita justo lo contrario -una copia sin ningun
  workflow- y monta su propio repo, asi que no reutiliza este.
- `uv`, `git`, `make` para el proyecto objetivo.

## Estructura

```
fixture/              proyecto uv autocontenido, en estado RESET (fizzbuzz sin implementar)
  pyproject.toml      ruff + mypy strict + pytest via uv
  Makefile            test / check-types / check-style / check-format / linting
  conventions.md      vara de convenciones (para el verificador)
  spec.md             spec completa (1 slice, con fuentes y controles) que se sube al issue
  fizzbuzz/core.py    vacio: la slice lo implementa
sample-output/        evidencia del codigo que produce la slice
  core.py.example     implementacion esperada de fizzbuzz
  test_core.py.example  test esperado
```

## Cómo ejecutarlo

1. **Sube la fixture a un repo remoto** con CI en `pull_request` (o usa uno ya montado):

   ```bash
   cp -r smoke/fixture /tmp/slice-smoke && cd /tmp/slice-smoke
   git init -q && git add -A && git commit -qm baseline
   gh repo create <tu-usuario>/slice-smoke --private --source=. --push
   uv run python -V   # calienta el entorno (instala ruff/mypy/pytest)
   ```

2. **Crea el issue con la spec** (via la skill o a mano):

   ```
   /slice-spec        (usa fixture/spec.md como borrador)
   ```
   o directamente `gh issue create --title "fizzbuzz" --body-file spec.md`.

3. **Corre el loop** apuntando al issue:

   ```
   /slice-runner #<N>   (o: "corre la siguiente slice del issue #<N>")
   ```

Debe: leer el issue, seleccionar `slice-01` (name `fizzbuzz-core`), marcarla `en-curso` en el issue,
alinear, escribir el test (rojo), implementar `fizzbuzz`, refactor, **dejar los controles verdes**
(`controles.py controles`), verificar con el agente `slice-verifier`, abrir PR (`Part of #<N>`), y al llegar a
CI verde marcar la slice `esperando-merge` en el issue.

Sigue el estado en vivo **desde el propio issue en GitHub** (se actualiza en cada transicion).

## Criterio de "smoke OK"

- El commit y el titulo de PR son conventional commits con el name como scope:
  `feat(fizzbuzz-core): ...`, y el cuerpo referencia el issue con `Part of #<N>`.
- **El cuerpo del PR cuenta la intencion, no el codigo.** Abre con `## Intencion` (la linea
  `INTENCION:` de la slice, que la fixture declara), sigue con los criterios de aceptacion cumplidos
  y la senal, y **no enumera ficheros ni narra el diff**. Si aparece un parrafo del tipo "se anade
  `fizzbuzz/core.py` con una funcion que...", la regla del paso 8 no esta llegando. Comprueba
  tambien que no dice "inferida": la fixture **si** declara intencion, asi que ese encabezado seria
  falso.
- El PR tiene CI verde (`make linting && make check-types && make test`).
- El verificador devuelve `PASA` (criterios de aceptacion cubiertos + convenciones OK).
- **Los dos agentes definidos resuelven** (`subagent_type: slice-implementer` y `slice-verifier`, ambos
  con symlink instalado). Si uno no resuelve, lo correcto es `bloqueada: sin-subagentes` en el paso 3 y
  **sin codigo escrito**; que el orquestador lo haga inline es un fallo del smoke, no un apano.
- El mensaje final del verificador es el JSON del veredicto **sin prosa alrededor**: la tool `Agent` no
  valida schemas, asi que esto solo se comprueba aqui.
- **El orquestador no le relata la metodologia al implementador.** Su prompt de invocacion lleva datos
  del run (criterios, intencion, senal, fuentes, controles, ruta); si aparece el ciclo TDD o los deltas
  redactados ahi, la separacion del paso 5 no esta llegando y se esta pagando ese contexto dos veces.
- **El verificador no ejecuta controles**, y ahora es estructural: no tiene `Bash`. Ojo con "arreglarlo"
  devolviendoselo -el smoke del 2026-07-27 comprobo que un `allowed-tools` restringido **no bloquea** lo
  no listado (ejecuto `ls`, ausente de su lista), asi que `Bash` con allowlist no es una alternativa
  valida a no tener `Bash`-.
- **El verificador recibe el diff en disco** (`controles.py diff-bundle`), no lo calcula. Comprueba que
  `--out` apunta **fuera del repo**: un fichero de trabajo dentro no debe poder acabar en la PR.
- **El orden del tramo 6-8 se respeta**: `git add` -> `pr-hygiene` -> controles -> `diff-bundle` ->
  verificador -> **commit**. Los tres primeros son el paso 6 (se stagea **antes** de medir: un control
  que lee el indice no ve un fichero nuevo sin stagear), los dos siguientes el 7 y el commit el 8. El
  commit va DESPUES del veredicto, asi que un FALLA no deja rastro y la slice sigue siendo un solo
  commit sin `--amend`. Es donde el smoke del 2026-07-29 se encontro el defecto bloqueante:
  `diff-bundle` mirava `<base>...HEAD` y el commit estaba despues, asi que el paso 7 recibia "sin
  cambios" con la slice entera implementada. Si vuelve a aparecer, alguien ha devuelto el commit a su
  sitio anterior.
- **La CI se consulta con `controles.py ci-status`**, nunca con un `gh pr checks` a mano. Comprueba
  que un tick devuelve `verde`/`pendiente` y no "sin checks" con la CI ya terminada: `gh pr checks
  --json` **no tiene campo `conclusion`** (pero `gh run list --json` si), y pedirlo devuelve un error
  que se lee igual que "aun no hay checks" -en el smoke del 2026-07-29 eso reporto doce ticks
  seguidos sin checks con la CI verde desde el segundo 14, y el modo de fallo es que **se cuelga
  hasta el timeout**, no que avise-.
- **Sin hallazgos de ruido.** Dos que el smoke ya cazo y no deben reaparecer: un hallazgo sobre "no
  puedo constatar que el test precediera a la implementacion" (inverificable con un solo commit, prohibido
  reportarlo) y el mismo assert debilitado contado dos veces como `alta` (`manipulacion-tests` +
  `test-desiderata`). Si vuelven, la rubrica ha regresado.
- En el issue, la linea de la slice pasa por `[en-curso]` -> `[esperando-merge] PR #<M>` y, tras el
  merge, `[x] ... [mergeada]`.
- El diff staged de la PR contiene **solo** `fizzbuzz/core.py` y `tests/test_core.py`: ni borradores
  ni artefactos (lo garantiza `controles.py pr-hygiene`).
- **La `SENAL` viaja y no genera ruido.** La spec de la fixture declara `SENAL: exenta - <motivo>`
  (libreria pura, sin runtime que observar). El verificador debe **aceptarla** sin hallazgos de
  `observabilidad`: exigir instrumentacion a una libreria sin despliegue seria un falso positivo, y es
  justo el modo de fallo del item 9 recien anadido. Comprueba tambien que el resumen del paso 3 y el
  cuerpo del PR mencionan la senal (o su exencion): si no aparecen, la linea se esta perdiendo entre
  paso 1 y el implementador.

## Como provocar los caminos de fallo

El camino feliz se dispara solo: la fixture esta preparada para pasar y basta correr el loop. Los cuatro
caminos de fallo hay que **provocarlos**, y ninguna de las cuatro provocaciones se parece a las otras,
asi que quedan escritas aqui para no volver a deducirlas cada vez. Lo que este fichero no repite es el
contrato: los estados y los presupuestos de reintentos los declaraba el `SKILL.md` del runner (retirado;
ver `CLAUDE.md`), y la lista de motivos validos vivia en `issue_body.py` (`MotivoBloqueada`), tambien
retirado ya con el flujo viejo. Aqui esta solo **como se provoca cada uno** y **que rastro debe
quedar**.

**Ojo con la version de los scripts que estas sondeando.** `~/.claude/skills/slice-runner/` es un
symlink al arbol de trabajo de este repo, asi que la rama en la que estas **decide que codigo corre**. Si
creas la rama de la sonda desde `origin/master`, corres los scripts tal como estan en `origin`, no los de
tu trabajo sin subir, y nada avisa. Paso tres veces el mismo dia. Antes de sondear un cambio: o lo subes,
o ramificas desde local y aceptas que la PR arrastre tus commits.

**Tres de estas cuatro recetas asumen el modo in-tree**: issue y PR en este mismo repo, con la
fixture donde esta (`smoke/fixture/`), no en el repo copiado que describe "Como ejecutarlo". La
diferencia importa: en una copia de la fixture el arbol empieza en la propia fixture -los tests estan
en `tests/`, no en `smoke/fixture/tests/`-, asi que la receta de `ci-roja` apunta ahi a rutas que no
existen. **`ci-indeterminada` es la excepcion y va justo al contrario**: in-tree ya no se alcanza
-desde que `.github/workflows/check.yml` corre en toda PR de este repo, ninguna se queda sin checks-,
asi que solo queda provocable en una copia **antes** de montarle la CI en `pull_request` que exige
`## Requisitos`, cuando la copia todavia no tiene ningun workflow. Ver su seccion, mas abajo.

**No describas la sonda en el cuerpo del issue.** El implementador lo lee entero, no solo la linea de
su slice: en la sonda de `ci-roja` (issue #13) el cuerpo explicaba el sub-experimento -si tocaria un
fichero ajeno y si `pr-hygiene` lo cazaria- y el implementador **cito esa frase literalmente** al
justificar su decision. Su razonamiento se sostenia igual por otras vias, pero el experimento quedo
invalidado: el sujeto sabia que se le probaba. Deja en el issue lo que la slice necesita para
ejecutarse -intencion, criterios, controles, fuentes- y guarda el proposito de la sonda fuera de el.

Dos reglas mas para los cuatro. **Una provocacion por run**: si siembras dos a la vez no sabras cual de los
dos frenos actuo, y el segundo no llega a ejercitarse porque el primero para el loop. Y **mira el issue,
no la conversacion**: el rastro que cuenta es el que sobrevive al cierre de la sesion -el motivo escrito
en la linea de la slice y el registro durable que escribe el programa el mismo (`metrics.jsonl`)-, asi que si el orquestador lo narro en prosa pero
no lo escribio, el camino no esta validado.

El quinto motivo, `sin-subagentes`, no se provoca desde la fixture: depende de que el entorno vete la
tool `Agent`, y eso no lo puede forzar ni el issue ni el repo.

### `bloqueada: controles`

Se provoca **desde el issue**: en su seccion `## Controles`, declara un comando que no resuelva (por
ejemplo `lint: make linting-que-no-existe`). Los controles los declara el issue y `slice-runner` solo los
lee, asi que el fallo es terminal por diseno: la skill prohibe expresamente al implementador arreglar el
`Makefile` o cambiar el comando para que pase, y sin esa salida los reintentos que declara el paso 6 se
agotan contra la misma pared. No rompas codigo para conseguirlo, que es la tentacion obvia y la peor: un test
roto tambien tumba los controles, pero entonces no distingues si el loop paro porque el control no
resuelve o porque el implementador no supo arreglar el test.

Al comprobar el "sin PR", filtra por estado: el nombre de rama se reutiliza entre sondas, asi que
`gh pr list --head slice/01-fizzbuzz-core --state all` devuelve las PRs cerradas de runs anteriores. Lo
que cuenta es `--state open`.

Debe dejar: la slice `bloqueada: controles` en el issue, la metrica durable con
`veredicto=bloqueada-controles`, `ci=none` y `--reintentos-controles` al tope del paso 6, y **ninguna PR ni ninguna
invocacion del verificador** -un fallo mecanico no se juzga, se arregla-. Comprueba tambien que lo que
llega al orquestador del control en rojo es la **ruta** del log (`--out` a un directorio fuera del repo)
y no el output del build.

### `bloqueada: verify`

La palanca es un **conflicto deliberado** entre el criterio de aceptacion de la slice y las
convenciones: escribe en el issue una `ACEPTACION:` que exija justo lo que `conventions.md` prohibe -un
docstring en `fizzbuzz/core.py`, o el parametro en castellano-. Pedirlo en el prompt de invocacion no
sirve: el implementador carga las convenciones y quita la violacion en la primera ronda.

**Pero el veto no llega por donde parece, y esto se comprobo en la sonda del 2026-07-30 (issue #12).**
La intuicion es que el implementador obedece la aceptacion y el juez veta la violacion de convenciones.
No pasa: el implementador aplica la precedencia que fija la skill -en conflicto ganan las convenciones-,
**rechaza las clausulas y reporta el conflicto**, nombrando los dos lados y escalando la decision. El
codigo entregado cumple `conventions.md` punto por punto. El veto llega igual, pero por la regla
**`conformidad-ac`**: dos criterios de aceptacion que ningun test pinea, con `alta` y evidencia citable.

Tres consecuencias al montar la sonda:

- **No esperes un hallazgo de `convenciones`.** Si aparece, es que el implementador puso la aceptacion
  por encima de la vara, y eso es un defecto distinto y mas grave que el que sondeas.
- La palanca **no depende** de que el juez califique de `alta` una violacion de estilo, que era el
  riesgo que esta receta advertia antes: un criterio de aceptacion sin cumplir es `alta` por rubrica.
- El reintento es **inutil por diseno**, igual que en `bloqueada: controles`: el implementador se
  encontraria el mismo conflicto imposible. Si acotas reintentos, declaralo.

Debe dejar: la slice `bloqueada: verify`, la metrica con `veredicto=FALLA`, `ci=none`,
`--hallazgos-alta` al menos en 1, y `--reintentos-verify` con lo que se haya gastado de verdad -y
`--descartes-verify` en 0: un descarte es el agente devolviendo un JSON que no
parsea, un fallo distinto que no debe acabar contado aqui-. Y **ni PR ni commit**: el commit va despues
del veredicto, asi que la rama tiene que quedarse sin ningun commit de la slice. Los cambios si quedan
**stageados** -el `git add` lo hace el paso 6, antes de los controles y del juez, y el juez juzga ese
indice- y nada los desstagea al cerrar: esperar el arbol limpio es el falso defecto facil de reportar
aqui. Si te encuentras un commit, el orden del tramo 6-8 se ha vuelto a invertir.

### `ci-roja`

Es el unico de los cuatro que necesita que **los controles pasen y la CI no**, asi que se provoca
dejando la CI mas ancha que lo declarado: en `## Controles` declara solo `lint: make linting` y siembra en
la fixture, **fuera de los ficheros de la slice**, un fallo que solo vea la CI -un test que falla en
`smoke/fixture/tests/`, o un error de tipos en un modulo que la slice no toca-, commiteado en la baseline
antes de correr el loop. `.github/workflows/smoke-fixture.yml` corre `make linting`, `make check-types` y
`make test`, asi que el paso 6 la deja pasar con solo el lint verde y la CI la tumba. **El paso de tests
es condicional**: la fixture nace virgen y `pytest` sale "no tests collected", asi que el workflow solo
exige `make test` cuando hay `tests/test_*.py` -que es el caso de esta receta en cuanto siembras el test
que falla, y tambien el de cualquier run que ya haya implementado una slice-. No es un montaje
artificial: es el riesgo real de que los controles los declare una persona y queden mas estrechos que la
CI, y este camino existe justo para eso.

**La base del `diff-bundle` no es la rama por defecto**, y esto es facil de fallar: si la semilla va en
un commit propio sobre la rama, hay que pasarle a `diff-bundle` **el commit de la semilla**, no
`master`. Con `--base master` el bundle incluye la semilla y el verificador acaba juzgando un error que
la slice no causo, o sea un falso hallazgo garantizado. Medido en la sonda: tres ficheros con `master`,
dos con el commit de la semilla.

**Los logs de la CI, a disco.** El paso 9 dice traer los logs del check fallido con `gh run view
--log-failed`, sin mas. Mandalos a un fichero fuera del repo y pasa la **ruta** al implementador, igual
que hace `--out` con los controles locales: si no, el output del build acaba en el contexto del
orquestador, que es justo lo que el resto del pipeline evita. La skill no lo pide asi todavia.

Debe dejar: un reintento por el paso 5 con los logs del check fallido y, si sigue roja, la slice
`bloqueada: ci-roja` con la metrica en `ci=red` y `--reintentos-ci` reflejando ese reintento. **La PR se
queda abierta** y la rama sin descartar: es un circuit breaker, y cerrar la PR tiraria el unico sitio
donde esta la evidencia para arreglarlo. Vigila una cosa en el reintento: si el implementador arregla el
fallo sembrado esta tocando un fichero ajeno a la slice, y `pr-hygiene` debe cazarlo; que no lo cace es en
si mismo un hallazgo del smoke.

### `ci-indeterminada`

**Ya no se provoca in-tree.** Se provocaba con una PR que no tocara `smoke/fixture/**`, cuando el unico
check del repo era `.github/workflows/smoke-fixture.yml`, filtrado por `paths: smoke/fixture/**`. Desde
que `.github/workflows/check.yml` corre `make check` en **toda** PR, ninguna PR de este repo se queda sin
checks -que era justo el objetivo-, asi que el camino solo queda alcanzable en el **modo copia**: una
copia de la fixture sin workflows, tal como queda recien creada, donde `controles.py ci-status` no puede
medir y devuelve **exit 4**. Paso de ser el mas facil de disparar sin querer a necesitar montaje.

La receta es la de "Como ejecutarlo" **con el paso 1 al reves**: la copia se sube **sin** CI -no "con CI
en `pull_request`"- y el run entero -issue, rama, PR- vive en ella. Es la unica de las cuatro que corre
contra un repo que **no** cumple `## Requisitos`, y a proposito: aqui la ausencia de checks es el sujeto
del experimento, no un descuido del montaje.

**La receta en modo copia todavia no se ha corrido entera**: nadie la ha sondeado desde que el camino
dejo de ser alcanzable in-tree, asi que los cuatro pasos estan escritos por lectura del codigo y del
comportamiento de `gh`, no de una corrida observada. La primera vez que se ejecute puede pedir ajustes.

1. **Copia la fixture y subela sin ningun workflow.** La fixture no trae `.github/`, asi que el `cp -r`
   ya deja el estado que hace falta; lo que hay que hacer es **no** anadirle despues el workflow de
   `pull_request`:

   ```bash
   cp -r smoke/fixture /tmp/slice-smoke-ci && cd /tmp/slice-smoke-ci
   git init -q && git add -A && git commit -qm baseline
   gh repo create <tu-usuario>/slice-smoke-ci --private --source=. --push
   uv run python -V   # calienta el entorno: los controles locales tienen que pasar
   ```

2. **Confirma en el remoto que la copia no define ningun workflow, antes de gastar el run.** Es la
   unica precondicion de la sonda, y lo que la rompe no es la fixture -no trae `.github/`- sino
   reutilizar una copia a la que una receta anterior ya le monto el workflow de `pull_request`:

   ```bash
   gh api repos/<tu-usuario>/slice-smoke-ci/actions/workflows --jq '.total_count'   # tiene que dar 0
   ```

   Ese endpoint lista **solo los workflows definidos en la copia**, asi que un check impuesto desde
   fuera -un required workflow o un ruleset de organizacion- daria 0 igualmente. No aplica aqui porque
   el paso 1 crea el repo bajo tu cuenta personal, donde no hay organizacion que lo imponga; si alguna
   vez se monta bajo una, la precondicion hay que comprobarla en los checks de la PR ya abierta.

3. **Crea el issue con la spec de la fixture, en la copia**, tal cual y sin sembrar nada:
   `gh issue create --title fizzbuzz --body-file spec.md`. Los controles que declara `spec.md`
   (`make linting`, `make check-types`, `make test`) tienen que quedar **verdes**: este camino necesita
   que el loop llegue al paso 9, asi que no se rompe nada de lo que rompen las otras recetas -si el
   loop para antes, en `bloqueada: controles` o `bloqueada: verify`, no has sondeado este camino-.

4. **Corre el loop** contra ese issue (`/slice-runner #<N>`) con la copia como directorio de trabajo.
   Vale igual el aviso del symlink de mas arriba: el codigo bajo prueba es la copia, pero los scripts
   que corren son los de la rama que tengas checkouteada en **este** repo.

Lo que pasa entonces en el paso 9, y por que la copia sin workflows equivale a la vieja PR sin checks:
`gh pr checks --json` no escribe nada en stdout -manda "no checks reported" a stderr- y sale con **exit
1**, el mismo codigo que usa cuando la CI esta roja. `controles.py ci-status` no mira ese exit code:
clasifica el stdout, y un stdout vacio es **`desconocido`** con **exit 4**, la rama de
`ci-indeterminada`. Como la clasificacion depende solo del stdout, da igual **por que** no hay check -un
`paths` que no matchea, o que no exista ningun workflow-, y por eso la receta nueva sondea el mismo
camino que la vieja. Medido asi en la sonda del 2026-07-30 (issue #9, PR #10), en modo in-tree, **y solo
ahi**: el estado observado fue `desconocido`, no `sin-checks`, y fiarse del exit code de `gh` habria
confundido "esta PR no tiene CI" con "la CI ha fallado", mandando al implementador a arreglar un fallo
inexistente. En modo copia la equivalencia esta razonada por el clasificador, no observada.

El `sin-checks` literal esta fuera del alcance de esta receta: solo lo dan checks que corran y se
salten, variante que nadie ha sondeado. No se pierde nada del camino, porque los dos estados mapean al
mismo exit 4 y a la misma rama del paso 9; lo unico que cambia es la precision del diagnostico.

Cuando acabes, esa copia **ya no sirve para el camino feliz de "Como ejecutarlo"** hasta que le montes
el workflow de `pull_request` que pide `## Requisitos`; y en cuanto se lo montes, deja de servir para
esta. Las otras tres recetas no se ven afectadas: corren in-tree y no usan copia.

Debe dejar: la slice `bloqueada: ci-indeterminada` con el estado `desconocido` en el issue, la metrica
en `ci=none`, la **PR abierta** y **ningun reintento** al implementador: no hay
nada que arreglar en el codigo. Que sea un estado propio y no se reparta entre los otros dos es lo
importante de este camino: no es verde porque nadie midio, y no es rojo porque nada fallo. Tratarlo como
rojo manda al implementador a arreglar un fallo inexistente, que es caro pero se ve. Tratarlo como verde
reporta como validada una PR que **nadie ha medido**, y eso no se ve nunca: es peor que colgarse
tickeando hasta el timeout, porque colgarse al menos acaba llamando la atencion.

## Pendiente de smokear (I/O aun no validada)

Lo que los unit tests no pueden cubrir y este smoke **todavia no ejecuta**. Los caminos de fallo no
entran aqui porque la seccion anterior dice como provocarlos con lo que ya hay; lo que queda en esta
lista necesita infraestructura que hoy no existe:

- **Slice cross-repo** (`REPO: <org>/<repo>`): rama, controles, `gh pr create` y CI **en el repo
  destino**, con `Part of <org>/<repo-del-issue>#<N>` como referencia cross-repo, y las fuentes de
  convencion leidas de su subseccion `### <org>/<repo>`. Necesita un segundo repo remoto de pruebas.
  Hasta que se smokee, esa ruta esta validada solo por la logica pura (`fuentes_para`, parseo de
  `REPO:`) y por que `controles.py` ya aceptaba `--repo`.
- **`deploy-watch` con senal declarada**: que una senal `declarada: true` sin muestras devuelva
  `inconclusive` esta cubierto offline (`tests/test_deploy_core.py`, y el CLI), pero la recogida real
  de una serie de negocio recien creada no.

## Evidencia de referencia

`sample-output/` guarda el codigo que la slice deberia producir (`core.py.example`,
`test_core.py.example`). El estado del run ya no deja ficheros locales: la evidencia viva es el issue
en GitHub.
