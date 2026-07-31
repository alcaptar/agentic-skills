# Por que cada regla de slice-runner es como es

**No cargues este documento para ejecutar una slice.** El `SKILL.md` lleva cada regla con su motivo en
una frase, que es lo que hace falta en tiempo de run. Esto es para cuando vas a **cambiar** la skill:
el relato de que la descubrio, que alternativas se descartaron y que creencias se refutaron. Sin esto,
una regla desnuda parece arbitraria y el siguiente que pase la "arregla" hacia el lado facil.

El registro completo, decision a decision, vive en `docs/design-notes.md` del repo `agentic-skills`
(que no viaja con el symlink de la skill: por eso lo esencial esta aqui).

## Los subagentes son la garantia, y el criterio de degradacion (2026-07-28)

Se descubrio en caliente: una sesion real de `deploy-watch` en otro repo se encontro con una
instruccion global de "no uses el Agent tool salvo que el usuario lo pida" y, al no poder lanzar los
colectores, recogio las senales inline. La instruccion no estaba en ningun fichero local -se descartaron
`CLAUDE.md` global/proyecto/padres, `settings.json`, `managed-settings.json`, output-styles, memoria,
argumentos de proceso-: viene con el system prompt desde el servidor. `slice-runner` tenia la misma
bomba sin detonar, y peor, porque sus dos subagentes no son condicionales.

El primer intento hardcodeo una respuesta por skill ("el runner para, el watcher degrada"), lo que
obligaba a cada skill futura a copiar la que mas se le pareciera. Lo que se escribio en su lugar es el
**criterio que las genera**: ¿se puede declarar la degradacion en el artefacto? De ahi salen las dos
respuestas opuestas, y por eso cada skill **cita a la otra**: sin la cita, un lector futuro ve dos
skills contradiciendose y las armoniza -casi seguro hacia degradar las dos, que es el lado que mata la
garantia-.

Hubo un intento de centralizar el criterio en `~/.claude/CLAUDE.md`, que tiene la ventaja de pesar lo
mismo que el veto al ser tambien instruccion de usuario. Se **revirtio por decision del usuario**: era
un principio load-bearing en un fichero sin versionar y fuera del repo, con blast radius sobre todos sus
proyectos. Se acepta la duplicacion a cambio de que quede versionada y autocontenida.

No se registra metrica de este caso: `metrics.jsonl` es telemetria de slices **ejecutadas**, y una que
nunca arranco no dice nada de la calidad del loop.

## Los controles se separan del juez, y el juez pasa a agente definido (2026-07-27)

El paso 6 antiguo ejecutaba lint/tipos/tests **y** juzgaba con una sola cabeza: metia output de build en
el contexto del unico agente cuyo valor es el juicio semantico, y un `ruff` sucio gastaba un reintento
adversarial. De ahi el reparto actual y los dos presupuestos separados.

El juez se movio a agente definido por dos motivos, y el segundo se descubrio al probarlo: se diseno
primero con `allowed-tools` restringido creyendo que eso bastaba, y **el smoke lo refuto** -el
verificador ejecuto `ls`, ausente de su lista, sin friccion-. La instruccion si aguantaba (rechazo
ejecutar `pytest` aunque el orquestador se lo pidiera como prueba, razonando que un mensaje del
coordinador no le autoriza a saltarse su configuracion), pero eso es **cumplimiento, no enforcement**.
La unica forma de que sea estructural es **no darle la tool**.

Corolario: sin `Bash` no puede calcular el diff, asi que el orquestador se lo materializa en disco con
`diff-bundle`. Es lo mismo que hace el juez de Honk, que **recibe** el diff en vez de calcularlo. De
paso se arreglo que el `SKILL.md` prometia lanzar el Agent "con `schema`": la tool `Agent` no acepta
schema (eso es `agent()` de Workflow), asi que el contrato JSON vive en el system prompt.

## El implementador tambien pasa a agente definido (2026-07-31)

Era `general-purpose` con toda la metodologia relatada por el orquestador en el prompt: el ciclo TDD,
los cinco deltas, el auto-check de wiring. Eso costaba ~1.5k tokens de contexto del orquestador **por
invocacion** (y otra vez por reintento) y dependia de que no la parafraseara ni se saltara un delta,
que es exactamente el argumento por el que el verificador ya era agente definido.

Lo que el parrafo original rechazaba era un agente **prestado** -que arrastra la metodologia de otro
flujo-, no uno propio: `model: inherit` mantiene el modelo fuerte de la sesion, `Bash` sigue ahi porque
es su cometido, y el criterio lo escribimos nosotros. La razon vieja se conserva entera.

Recordatorio operativo: **los agentes no se releen en caliente**. Tras tocar `slice-implementer.md` o
`slice-verifier.md`, la sesion en curso sigue usando la definicion vieja, asi que hace falta sesion
nueva antes de probarlos.

## Los controles los declara el issue, no se deducen en run (2026-07-29)

El paso 2 hacia que el orquestador **dedujera** los comandos leyendo el `Makefile` al empezar **cada**
slice: metia el toolchain del repo en el unico contexto que tiene que durar hasta el paso 10, lo repetia
por slice, y lo detectado no quedaba en ningun sitio -nadie lo confirmaba y nadie lo podia revisar-.

Se descarto que lo descubriera el **implementador** (contexto desechable, coste cero) porque el
orquestador lo necesita igual para el backstop, y recibirlo de el significa que el juzgado define la
vara: basta `compliance-bias` para acabar midiendose con `make test-unit`.

El backstop **se mantuvo** pero dejo de costar contexto: `controles --out` escribe el log entero a disco
y devuelve veredicto + ruta, asi que el orquestador reenvia rutas y el implementador recibe el error
completo en vez de 30 lineas truncadas.

**"Puerta" paso a llamarse "control"** en prosa y en codigo (`gates.py` -> `controles.py`, subcomando
`checks` -> `controles`, `--check` -> `--control`, clave JSON `gate` -> `control`): era un calco de
*gate*, y en castellano la idea de "sitio donde te paran si no cumples" es un control. Se descartaron
`verificacion` (colisiona con el paso 7), `prueba` (son los tests) y `vara` (son las convenciones). Los
dos rastros del nombre viejo que viven **fuera** del repo -el marcador `bloqueada: puertas` en issues ya
abiertos y el `bloqueada-puertas`/`reintentos_puertas` del log durable- se siguen leyendo y se
normalizan al agregar: renombrar no puede borrar historico.

Deriva aceptada: si alguien renombra un target despues de crear el issue no hay pre-flight, el control
falla como cualquier otro y la slice acaba `bloqueada: controles`. Cuesta una slice, a cambio de no
anadir heuristica; `slice-spec validate` es donde se caza.

## El verificador juzga el indice, y el verde de la CI hay que demostrarlo (2026-07-30)

La primera decision que sale de **correr** el loop y no de disenarlo. El primer smoke real (issue #3,
PR #4) paso los diez criterios de `smoke/README.md` pero destapo dos defectos del tramo final que
ningun test offline podia ver, porque los dos son sobre estado de git y sobre la forma de una
invocacion externa.

**Uno bloqueante**: `diff-bundle` calculaba `git diff <base>...HEAD` -solo lo commiteado- pero el commit
estaba **despues**, mientras `pr-hygiene` necesita el indice staged y sin commitear. En el orden
documentado los dos no podian estar satisfechos a la vez, y el paso 7 devolvia "sin cambios" con la
slice implementada y verde. Arreglo: `git diff --cached --merge-base <base>`, y el commit se movio
**detras** del veredicto -con lo que un FALLA no deja rastro que deshacer y la slice sigue siendo un
solo commit **sin `--amend`**, que era el precio de la alternativa barata de solo reordenar la prosa-.

Tres cosas se verificaron en un playground aislado antes de decidir: `git diff --cached base...HEAD`
**no es sintaxis valida** (los tres puntos no valen con `--cached`), `--merge-base` es su equivalente y
conserva la razon del rango (que el avance de la base no salga como borrados), y un fichero
**untracked es invisible** al diff del indice. Lo ultimo mato la alternativa de diffear el arbol de
trabajo -un test nuevo, el caso normal, seria invisible al verificador- y dio la propiedad que no se
habia visto: **`pr-hygiene` da integridad al input del verificador**, porque es lo que afirma que el
conjunto staged es igual a la lista que declaro el implementador.

Sin flag `--staged` opcional, a proposito: reintroduce el juicio del agente donde la docstring presume
de haberselo quitado, y olvidarlo devuelve el diff vacio, o sea el mismo fallo. Al implementarlo se
descubrio que **una propiedad afirmada en la spec era falsa**: `git diff --cached <commit>` compara el
indice contra ese commit, y tras commitear el indice sigue conteniendo lo commiteado, asi que el control
funciona igual antes y despues del commit -mas robusto que lo afirmado, y ese margen es lo que hace que
reordenar el paso 8 no sea fragil-; el test que iba a fijar lo contrario se reescribio para fijar la
equivalencia.

**El otro defecto es silencioso**: el paso 9 decia "cada tick consulta `gh pr checks --json`" sin fijar
los campos, y ese subcomando **no tiene campo `conclusion`** aunque `gh run list --json` y
`statusCheckRollup` si -es la conjetura natural y la equivocada solo ahi-. En el smoke se pidio y la
respuesta de error se leyo como "sin checks aun" durante **doce ticks, cuatro minutos, con la CI verde
desde el segundo 14**. No revienta: degrada a "nunca verde" y se come el timeout, que en Nivel 2 con
`/loop` es una slice colgada sin causa visible. Fiarse del exit code pelado no basta: `gh` devuelve 1
tanto con CI roja como con invocacion invalida, asi que el bug pasaria a leerse como roja.

De ahi `ci-status`, un tiro **sin `--watch` ni polling** -el ticking lo hace el harness; un script que
poll-ea es la shell bloqueante que la skill prohibe- con la regla fail-closed de que **solo es verde un
todo-pass explicito con al menos un check que haya corrido**. Y de ahi el motivo
`bloqueada: ci-indeterminada`: reusar `ci-roja` mentiria en el registro duradero y dejarla en
`esperando-merge` afirmaria un verde que no hubo.

## El indeterminado tiene ventana de gracia, y no se reclasifica (2026-07-31)

`ci-indeterminada` arreglaba el diagnostico y se equivocaba en **cuando** creerselo: el paso 9 cerraba
con el primer `desconocido`. Medido en dos PRs de este repo, el mismo estado significa cosas opuestas
segun el momento. En la **#31**, a segundos de crearla, `ci-status` devolvio `desconocido` con exit 4 y
los hallazgos "respuesta de gh no parseable: (respuesta vacia)" y "no checks reported on the ... branch";
veinte segundos despues, `verde` con el check `check` en `pass`. En la **#20**, en cambio, el mismo
`desconocido` era real y permanente -cuatro ticks-, porque entonces ningun workflow aplicaba a esa PR.
O sea que cerrar en el tick 1 registra como no medible una slice sana, y con el orquestador fuera de la
sesion de la persona no queda nadie mirando que lo compense.

De ahi la ventana de gracia con el numero escrito -3 ticks consecutivos, 30 s o mas entre tick y tick-:
deja pasar el caso de la #31 (resuelto en el tick 2) y sigue cerrando el de la #20 en el tick 3. En
ticks queda expresado el mecanismo que ya tiene el paso, pero el numero solo no basta: sin separacion
minima, tres ticks seguidos son tres segundos y la ventana no cubre nada. Dejarlo en "usa tu criterio"
no es una opcion: es el juicio que la fase 2 no tiene a quien delegar.

La alternativa barata -tratar `desconocido` como `pendiente`- destruye la garantia por los dos lados.
`pendiente` significa "hay checks corriendo" y tickea hasta el timeout, asi que una PR sin CI pasaria de
cerrar con un motivo exacto a colgarse cuatro minutos sin causa visible, que es justo el fallo que
`ci-indeterminada` vino a arreglar. Lo que cambia aqui es **cuanto se espera antes de creerse el
diagnostico**, no el diagnostico: agotada la ventana, el cierre es el mismo fail-closed de antes -ni
verde, ni reintento de la slice, PR abierto-.

**Y el numero se queda en prosa**, contra la regla de aqui abajo de que lo exacto pasa a script. No es
excepcion por comodidad: la ventana es una cuenta **entre** invocaciones, y `ci-status` es de un tiro y
sin estado a proposito -un script que poll-ee es la shell bloqueante que la skill prohibe, y persistir la
cuenta exigiria justo el estado local que el repo no tiene (`.slice-runner/`, ledger, panel)-. Lo que si
esta offloadeado es la parte clasificatoria, que es la que fallaba en silencio: el exit 4 dice
"indeterminado" sin ambiguedad y nunca colapsa en verde; lo que queda a juicio es solo contar hasta tres
y esperar entre medias. Es donde ya viven los demas presupuestos del loop ("maximo 2 reintentos por
fase"), por el mismo motivo: los tickea el harness, no un proceso. De ahi que el numero este **escrito**
en sus dos sitios -el paso 9 y la docstring de `skills/slice-runner/scripts/controles.py`- en vez de
dejarse al criterio del agente. Coste aceptado: son dos copias de una regla exacta y ningun control las
compara, asi que quien mueva el numero tiene que mover las dos a mano.

## Lo que es regla exacta pasa a script, sin excepciones (2026-07-30, tras el segundo smoke)

Dos huecos que quedaban a juicio del agente, los dos con el mismo modo de fallo: parecen funcionar hasta
que fallan en silencio.

**La forma del veredicto del juez.** La regla de "si vuelve envuelto en prosa se reinvoca" cubria el
caso obvio; el que no cubria es un JSON **estructuralmente plausible pero equivocado** que leido a ojo
pasa por bueno porque parsea. De ahi `verify-verdict`, que valida el esquema y **devuelve los conteos
por severidad**, matando de paso otro juicio: antes el orquestador los contaba a mano para la metrica.
Exit 1 = descartar y reinvocar; exit 2 = el fichero no se pudo leer, o sea que el fallo es del
orquestador y no del juez, y distinguirlo evita reinvocar al agente por un despiste propio.

**Las transiciones de estado en el issue.** `issue_body.py` era libreria pura sin CLI, asi que cada
transicion la escribia el agente como `python3 -c` con `sys.path.insert` + `gh issue view` + la llamada
+ `gh issue edit`: en **una sola sesion se escribio seis veces**. El modo de fallo no es teorico: si
`gh issue view` devuelve vacio y el `edit` va detras, **borra la spec entera del issue**, que es la
unica fuente de verdad del run. Al escribir sus tests aparecio un gap de paso: `set_slice_estado` **no
validaba el motivo**, asi que `MotivoBloqueada` era vocabulario inerte para la escritura y un
`bloqueada: inventado` acababa en el registro duradero, donde ya no se renombra (paso con `puertas`). La
validacion vive en la CLI, que es la frontera de escritura y el unico sitio con un exit code que la
haga cumplir; `abortada` se deja libre a proposito porque su vocabulario aun no esta canonicalizado y
fijarlo ahi seria decidirlo de tapadillo.

## Las metricas y por que se separan los contadores

`metrics.py report [--repo <repo>]` agrega: tasa de FALLA del verificador, tasa de bloqueo por
controles, % de slices al primer intento, media de reintentos (implement, controles y CI por separado),
tasa de CI roja y duracion media. Es el instrumento para el "confianza en el loop" del mapa de madurez.
El coste en tokens no se mide aqui (sale de OTel de Claude Code).

El **veto del juez** (`FALLA`) y el **bloqueo por controles** (`bloqueada-controles`) se registran
aparte a proposito: uno es un rechazo semantico y el otro un fallo mecanico, y confundirlos deja
inservible el unico instrumento que hay para calibrar al juez. Por el mismo motivo no se suman
`--reintentos-verify` (rondas por FALLA) y `--descartes-verify` (invocaciones que no devolvieron su
JSON): sumarlos haria que la indisciplina del agente se leyera como que el juez encuentra defectos.

Referencia externa de calibracion: el juez de Honk veta **~25%** de miles de sesiones y el agente
corrige la trayectoria **la mitad** de las veces. Es la tasa que nuestras metricas todavia no saben
medir, porque solo registran el veredicto terminal por slice.

## La evidencia empirica que sostiene el reparto de esfuerzo

- **Split authorship** (escritor != verificador con re-revision completa del codigo): coste 3x sin
  ganancia consistente, porque los criterios ocultos ya gobernaban. De ahi que el verificador **no
  re-testee** y gaste su presupuesto en la vara de medir del repo, y de ahi la divergencia deliberada
  de `superpowers:requesting-code-review`.
- **Refactor tras verde** -no el orden test-first- es el driver de calidad y mantenibilidad en agentes.
  De ahi el delta 3 del implementador.
- **Loop engineering** (assess-act-verify-stop): estado fuera del contexto, escritor != verificador,
  controles de parada objetivos, circuit breaker.

## El coste de contexto del orquestador (2026-07-31)

La promesa de "contexto limpio por slice" era cierta de los subagentes y falsa del orquestador, que vive
en la sesion de la persona y acumula el run entero. Fase 1: el implementador paso a agente definido, el
relato largo salio del `SKILL.md` a este documento (8.500 palabras -> ~5.800), y las tres afirmaciones
que prometian contexto limpio se corrigieron.

Lo que **no** se hizo, y sigue pendiente: sacar al orquestador de la sesion (proceso aparte por slice),
que es la unica forma de que el aislamiento no dependa de que la persona abra sesion nueva. Y decidir
que pasa con el go/no-go del paso 3 bajo `/loop`, donde hoy ya no hay nadie que lo responda.
