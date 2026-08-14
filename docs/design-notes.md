# Notas de diseno

> **Registro vivo del porque.** A diferencia de las otras lecturas de `docs/`, este si se sigue
> ampliando: cada decision entra con su fecha y su motivo para no re-derivarla. No es vara de medir
> -eso son las convenciones- sino la memoria de como se llego a ellas.

Decisiones tomadas al construir estas skills y el porque, para poder seguir iterando sin re-derivarlo.

## Contexto

Flujo de trabajo objetivo: escribo specs; cada slice de la spec quiero que se implemente sola, se valide, se abra PR y se confirme CI verde; y tras aprobar, monitorizar el despliegue. Encaja con "loop engineering" (assess -> act -> verify -> stop) y spec-driven development.

## slice-runner

### Decisiones clave

- **Nivel 1 por defecto** (una slice por invocacion, para maximo control). Nivel 2 = envolver en `/loop`. Nivel 3 = Workflow fan-out (no construido; solo para slices independientes).
- **Un formato de spec**: checklist (`## Slices`, una linea `- [ ] slice-NN (name): ...` por slice). Hubo un segundo formato (plan de una slice estilo superpowers, el fichero entero = 1 slice) para consumir `docs/superpowers/plans/*.md` de un repo real; se **elimino** porque el flujo canonico (slice-spec -> slice-runner) siempre emite el checklist, y el Formato B no aportaba poder expresivo pero si superficie transversal (deteccion, derivacion de AC, contrato duplicado en 3 sitios).
- **Los controles los declara el issue, no los deduce nadie en tiempo de run** (decision 2026-07-29, ver abajo). Muchos repos corren todo en Docker via `make` (`make test`, `make check-types`, `make fastapi-migrate`...) y lanzar `pytest`/`ruff` directos falla, asi que hay que saber los comandos reales; lo que cambio es **quien** los sabe y **cuando**.
- **Convenciones del repo como vara de medir principal**, `backend-best-practices` como secundaria, default generico al final. No es invento: replica la jerarquia de autoridad que declara el `CLAUDE.md` de los repos (convenciones > skill > default). Implementador y verificador cargan ambas.
- **TDD consciente de capa.** Test-first por AC en capas con test; en capas eximidas por convencion (modelos ORM, migraciones alembic) el control es "suite intacta + efecto verificado", no test-first. El repo decide.
- **Gate de check-alignment** antes de implementar (mostrar entendimiento, esperar go/no-go). Evita transcribir a ciegas el codigo pre-horneado de una spec. En un dry-run real este gate detecto que una slice ya estaba mergeada y aborto antes de romper la cadena de alembic.
- **El ciclo TDD se delega en superpowers, los deltas se quedan** (decision 2026-07-27): `slice-runner` reescribia de su cuenta el ciclo red-green-refactor y la integridad de tests, que `superpowers:test-driven-development` ya cubre; esa prosa duplicada se desincroniza (superpowers lo mantiene un tercero, va por la 6.2.0). Ahora el implementador **invoca** esa skill y en `slice-runner` viven solo los deltas: exencion por capa, integridad de tests **preexistentes**, refactor tras cada verde, y el esfuerzo en la calidad del test. Como su Iron Law ("no production code without a failing test") contradice la exencion de capa, se declara la precedencia explicita **convenciones del repo > exencion de capa > Iron Law** (sin eso, `selective-hearing`: gana la regla que mas suena en el entrenamiento). Se anade el principio **"los tests son ciudadanos de primera categoria"**, que cita los checks de severidad alta del verificador en vez de repetirlos. Fuera de alcance: `verification-before-completion` (los controles ya son deterministas con exit code autoritativo; anadir su prosa no cambiaria comportamiento). **Contraparte en `slice-spec`**: el principio solo tiene dientes si el AC es refutable, asi que `validate` pasa de comprobar que los AC **existen** a exigir que sean **falsables** (misma vara que `writing-good-tests.md`: nombra el cambio de produccion que haria fallar el AC); un AC vago tumbaba el mapeo AC↔test en origen.
- **Verificador reenfocado a review de convenciones/arquitectura, no re-testeo.** Su juicio va a convenciones, boundaries y constraints.
- **Los controles deterministas se separan del juez, y el juez pasa a ser un agente definido** (decision 2026-07-27). El paso 6 ejecutaba lint/tipos/tests **y** juzgaba con una sola cabeza: metia output de build en el contexto del unico agente cuyo valor es el juicio semantico (`limited-focus` autoinfligido) y un `ruff` sucio gastaba un reintento adversarial. Ahora los controles corren dos veces antes del juez -en el ciclo del implementador (feedback incremental) y como **backstop del orquestador**, porque el auto-reporte del implementador no es fuente de verdad-, via el subcomando nuevo `controles.py controles`, que devuelve exit code + salida truncada y **no** entra en el contexto de nadie en crudo. El juez ya **no recibe nada de los controles**: cuando se le invoca estan verdes por construccion. Consecuencias: la rubrica pierde su item `[det]` (quedan 8, todos `[sem]`), los controles tienen **presupuesto de reintentos propio** (2, separado del del juez) con cierre `bloqueada: controles`, y `metrics.py` gana `bloqueada-controles` + `--reintentos-controles` para no registrar un fallo mecanico como veto del juez. El juez se mueve a un **agente definido** (`agents/slice-verifier.md`, symlink a `~/.claude/agents/`): su rubrica va en el **system prompt** -verbatim en cada invocacion, en vez de relatada por el orquestador, que podia parafrasearla o saltarse items- y **no tiene `Bash`** (`tools: Read, Grep, Glob, Skill`), asi que su incapacidad de ejecutar puertas es estructural por ausencia de la tool. Se diseno primero con `allowed-tools` restringido creyendo que eso bastaba, y **el smoke del 2026-07-27 lo refuto**: `allowed-tools` en el frontmatter de un agente no bloquea lo no listado -el verificador ejecuto `ls`, ausente de su lista, sin friccion, y no hay reglas `deny` globales que lo expliquen-. La instruccion si aguantaba (rechazo ejecutar `pytest` aunque el orquestador se lo pidiera como prueba, razonando que un mensaje del coordinador no le autoriza a saltarse su configuracion), pero eso es cumplimiento, no enforcement. Corolario: como sin `Bash` no puede calcular el diff, el orquestador se lo **materializa en disco** con `controles.py diff-bundle` (`slice.diff` + `files.txt`, rango `<base>...HEAD` fijado por el script para quitar de encima el footgun de `..` vs `...`, y `--out` fuera del repo). Es ademas lo que hace el juez de Honk, que **recibe** el diff en vez de calcularlo. De paso se arreglo que `SKILL.md` prometia lanzar el Agent "con `schema`": la tool `Agent` no acepta schema (eso es `agent()` de Workflow), asi que el contrato JSON vive ahora en el system prompt.
- **Los controles se declaran en el issue, y el orquestador deja de ver output de build** (decision 2026-07-29). El paso 2 hacia que el orquestador **dedujera** los comandos leyendo el `Makefile` al empezar **cada** slice: metia el toolchain del repo en el unico contexto que tiene que durar hasta el paso 10, lo repetia por slice, y lo detectado no quedaba en ningun sitio ("cachea lo detectado en la respuesta") -nadie lo confirmaba y nadie lo podia revisar-. Ahora hay una seccion `## Controles` en el cuerpo del issue, hermana de `## Fuentes de convencion` y con su misma forma por repo (`### org/repo` para las slices con `REPO:`): la descubre `slice-spec` con el helper determinista nuevo `discover_controles.py` (targets del `Makefile` + senales de `pyproject`/`tox`, **sin decidir**), la **confirma la persona** -que es quien sabe que este repo necesita `make env-start` antes, o que `make test` tarda 20 minutos-, y `slice-runner` **solo la lee**; el paso 2 pasa de deducir a leer y es fail-closed como las fuentes. Se descarto que la descubriera el **implementador** (contexto desechable, coste cero) porque el orquestador la necesita igualmente para el backstop del paso 6, y recibirla de el significa que **el juzgado define la vara con la que se le juzga**: basta `compliance-bias` para acabar midiendose con `make test-unit`. Segunda mitad de la decision: el backstop **se mantiene** -lo que no vale del paso 5 no es su ejecucion, que es el mismo script y el mismo exit code, sino el **canal**: el orquestador no ve las tool calls del subagente, solo su mensaje final en prosa- pero deja de costar contexto, porque `controles.py controles --out` escribe el log entero a disco y devuelve `veredicto + ruta`: el orquestador reenvia rutas sin leerlas y el implementador recibe el error completo en vez de 30 lineas truncadas. De paso, **"puerta" pasa a llamarse "control"** en prosa y en codigo (`gates.py` -> `controles.py`, subcomando `checks` -> `controles`, `--check` -> `--control`, clave JSON `gate` -> `control`): era un calco de *gate*, y en castellano la idea de "sitio donde te paran si no cumples" es un control; se descartaron `verificacion` (colisiona con el paso 7), `prueba` (son los tests) y `vara` (son las convenciones). Los dos rastros del nombre viejo que viven **fuera** del repo -el marcador `bloqueada: puertas` escrito en issues abiertos y el `bloqueada-puertas`/`reintentos_puertas` del log durable de metricas- se siguen leyendo y se normalizan al agregar; renombrar no puede borrar historico. **Deriva**: si alguien renombra un target despues de crear el issue no hay pre-flight, el control falla como cualquier otro y la slice acaba `bloqueada: controles`; se acepto el coste (quema una slice) a cambio de no anadir heuristica, y `slice-spec validate` es donde se caza. Ver `docs/superpowers/specs/2026-07-29-controles-declarados-en-el-issue-design.md`.
- **El verificador juzga el indice, y el verde de la CI hay que demostrarlo** (decision 2026-07-30, la primera que sale de **correr** el loop y no de disenarlo). El primer smoke real (issue #3, PR #4) recorrio el flujo entero y paso los diez criterios de `smoke/README.md`, pero destapo dos defectos del tramo final que ningun test offline podia ver, porque los dos son sobre **estado de git** y sobre la **forma de una invocacion externa**. **Uno bloqueante**: `diff-bundle` (paso 7) calculaba `git diff <base>...HEAD` -solo lo commiteado- pero el commit estaba en el paso 8, **despues**, mientras `pr-hygiene` necesita el indice **staged y sin commitear**; en el orden documentado los dos no pueden estar satisfechos a la vez, y el paso 7 devolvia "sin cambios" con la slice implementada y verde. Arreglo: `diff-bundle` pasa a `git diff --cached --merge-base <base>` y el commit se mueve **detras** del veredicto, con lo que un FALLA no deja rastro que deshacer y la slice sigue siendo un solo commit **sin `--amend`** (que era el precio de la alternativa barata de solo reordenar la prosa). Sin flag a proposito: un `--staged` opcional reintroduce el juicio del agente donde la docstring presume de haberselo quitado, y olvidarlo devuelve el diff vacio, o sea el mismo fallo. Tres cosas se verificaron en un playground aislado antes de decidir: `git diff --cached base...HEAD` **no es sintaxis valida** (los tres puntos no valen con `--cached`), `--merge-base` es su equivalente y conserva la razon de ser del rango -que el avance de la base no salga como borrados-, y un fichero **untracked es invisible** al diff del indice. Eso ultimo mato la alternativa de diffear el arbol de trabajo (un test nuevo, el caso normal, seria invisible al verificador) y dio la propiedad que no se habia visto: **`pr-hygiene` pasa a dar integridad al input del verificador**, porque es lo que afirma que el conjunto staged es igual a la lista que declaro el implementador. **El otro defecto es silencioso**: el paso 9 decia "cada tick consulta `gh pr checks --json`" sin fijar los campos, y ese subcomando **no tiene campo `conclusion`** aunque `gh run list --json` y `statusCheckRollup` si -es la conjetura natural y la equivocada solo ahi-; en el smoke se pidio y la respuesta de error se leyo como "sin checks aun" durante **doce ticks, cuatro minutos, con la CI verde desde el segundo 14**. No revienta: **degrada a "nunca verde"** y se come el timeout, que en Nivel 2 con `/loop` es una slice colgada sin causa visible. Fiarse del exit code pelado no basta (`gh` devuelve 1 tanto con CI roja como con invocacion invalida, asi que el bug pasaria a leerse como roja). Arreglo: subcomando `ci-status`, un tiro **sin `--watch` ni polling** -el ticking lo hace el harness, un script que poll-ea es la shell bloqueante que la skill prohibe-, que encapsula la invocacion, los nombres de campo y el mapeo de exit codes, con la regla fail-closed de que **solo es verde un todo-pass explicito con al menos un check que haya corrido**; asi no hace falta adivinar que hace `gh` ante una PR sin CI, y `sin-checks` no colapsa en verde (seria peor que colgarse: reportaria validada una PR sin CI). De ahi el motivo nuevo `bloqueada: ci-indeterminada`: reusar `ci-roja` mentiria en el registro duradero y dejarla en `esperando-merge` afirmaria un verde que no hubo. Al implementarlo se descubrio que **una de las propiedades afirmadas en la spec era falsa**: `git diff --cached <commit>` compara el indice contra ese commit, y tras commitear el indice sigue conteniendo lo commiteado, asi que el control **funciona igual antes y despues del commit** -mas robusto que lo afirmado, y ese margen es lo que hace que reordenar el paso 8 no sea fragil-; el test que iba a fijar lo contrario se reescribio para fijar la equivalencia. Ver `docs/superpowers/specs/2026-07-30-verificar-antes-de-commitear-design.md`.
- **Los dos contadores del verificador no se mezclan** (decision 2026-07-30, del segundo smoke). El verificador tenia presupuesto propio de 2 reintentos pero `metrics.py` **no tenia campo para registrarlos**: la calibracion del juez estaba ciega justo donde importa. Al anadirlo aparecio que no era un contador sino dos, porque hay dos motivos distintos de reinvocarlo: `FALLA` es un **rechazo semantico** (el juez veto codigo y se vuelve al paso 5) y devolver prosa en vez de su JSON es un **fallo mecanico del agente** (se reinvoca sin tocar codigo). Se separan en `--reintentos-verify` y `--descartes-verify` por el mismo argumento que ya separa `FALLA` de `bloqueada-controles` en este mismo fichero -"confundirlos deja inservible el unico instrumento que hay para calibrar al juez"-: sumarlos haria que la indisciplina del agente se leyera como que el juez encuentra defectos. Un descarte **no** descalifica la slice como "primer intento", porque lo que se rehizo fue la respuesta del juez, no el codigo. Y `descartes_verify` se reporta como **tasa de slices**, no como media: la pregunta que responde es "en que fraccion no aguanto el contrato de salida", que es una propiedad del agente y no de la slice. El motivo por el que esto se descubrio: el smoke 2 recibio prosa en la primera invocacion y el **JSON pelado al reinvocar con el prompt identico**, asi que el cumplimiento del contrato es **estocastico** -en el smoke 1 cumplio a la primera y parecia fiable- y la regla de reinvocar es lo unico que lo sostiene, dado que la tool `Agent` no valida schemas.
- **Lo que es regla exacta pasa a script, sin excepciones** (decision 2026-07-30, tras el segundo smoke). Dos huecos que quedaban a juicio del agente, los dos con el mismo modo de fallo: parecen funcionar hasta que fallan en silencio. (1) **La forma del veredicto del juez.** La regla de "si vuelve envuelto en prosa se reinvoca" cubria el caso obvio; el que no cubria es un JSON **estructuralmente plausible pero equivocado** -`"veredicto": "PASS"`, una `severidad` inventada, un hallazgo sin `evidencia`, o un `PASA` que convive con un hallazgo `alta`- que leido a ojo pasa por bueno porque parsea. Nuevo `controles.py verify-verdict`, que valida el esquema y **devuelve los conteos por severidad**, matando de paso otro juicio: antes el orquestador los contaba a mano para la metrica. Exit 1 = descartar y reinvocar (suma a `--descartes-verify`), exit 2 = el fichero no se pudo leer, o sea que el fallo es del orquestador y no del juez -distinguirlo evita reinvocar al agente por un despiste propio-. (2) **Las transiciones de estado en el issue.** `issue_body.py` era libreria pura sin CLI, asi que cada transicion la escribia el agente como `python3 -c` con `sys.path.insert` + `gh issue view` + la llamada + `gh issue edit`: en **una sola sesion se escribio seis veces**. El modo de fallo no es teorico: si `gh issue view` devuelve vacio y el `edit` va detras, **borra la spec entera del issue**, que es la unica fuente de verdad del run. Ahora hay CLI con `show` (lee el issue y emite slice elegida, fuentes y controles ya filtrados por repo, intencion, y la `rama` y el `scope` ya derivados) y `set-estado` (read-modify-write completo, fail-closed ante cuerpo vacio). El nucleo sigue puro y es lo que se testea; la CLI es la capa de I/O, mismo patron que `clasifica_ci`/`consulta_ci` en `controles.py` -por eso se actualizo la nota que decia que la I/O vivia solo en `gh`-. Al escribir sus tests aparecio un gap de paso: `set_slice_estado` **no valida el motivo**, asi que `MotivoBloqueada` seguia siendo un vocabulario inerte para la escritura y un `bloqueada: inventado` acababa en el registro duradero, donde ya no se renombra (paso con `puertas`). La validacion vive en la CLI, que es la frontera de escritura y el unico sitio con un exit code que la haga cumplir; `abortada` se deja libre a proposito porque su vocabulario aun no esta canonicalizado y fijarlo ahi seria decidirlo de tapadillo.
- **El implementador pasa a agente definido y el relato sale del `SKILL.md`** (decision 2026-07-31, fase 1 del coste de contexto). El README prometia contexto limpio por slice y en la practica no se podian correr todas las slices de una feature en una sesion: habia que compactar a mitad del run, y a partir de ahi el orquestador decidia con el contexto mutilado -el fallo que este repo existe para evitar-. La promesa era cierta **solo de los subagentes**; el orquestador vive en la sesion de la persona, y `/loop` reinyecta el prompt en la **misma** conversacion, asi que el nivel donde mas se prometia es donde menos se cumplia. Medido, el coste por slice era: `SKILL.md` 8.500 palabras (~13k tokens) recargadas por invocacion, el prompt del implementador redactado entero por el paso 5 (metodologia incluida, y otra vez por reintento), los ticks de CI y de merge, y `deploy-watch` encadenado en la misma sesion. Dos palancas de cuatro: (1) **el implementador pasa a agente definido** (`agents/slice-implementer.md`), con la metodologia -ciclo TDD, los cinco deltas, auto-check de wiring, controles verdes- en su system prompt en vez de relatada; el paso 5 se queda con los datos del run. No rompe la razon vieja de que fuera `general-purpose`: lo que ese parrafo rechazaba era un agente **prestado**, y uno propio con `model: inherit` y `Bash` conserva las tres propiedades que pedia, anadiendo la que ya justifico mover al verificador (la metodologia no se puede parafrasear ni saltar items). (2) **el relato largo sale del `SKILL.md` a un fichero de referencia propio de la skill** (mas tarde retirado junto con el resto de la prosa del runner) -no a `docs/design-notes.md`, porque el symlink de instalacion apunta al directorio de la skill y desde otro repo `docs/` no existe-, con criterio de corte explicito: se queda la regla y su por que **en una frase**, se va el relato (que smoke lo descubrio, alternativas descartadas, creencias refutadas). El objetivo era <=4.500 palabras y **se quedo en ~5.840**: al llegar ahi lo que restaba ya era regla o por que de una frase, y bajar mas exigia borrar reglas para cumplir una cifra estimada antes de hacer el trabajo. Se dejo el numero real declarado en vez de recortar reglas. Descartadas: **desencadenar `deploy-watch`** del paso 10 (~6-10k tokens, la palanca mas grande) por decision del usuario, que prefiere conservar el encadenado automatico, y **`Monitor` en vez de N ticks** por ahorro escaso. Ver `docs/superpowers/specs/2026-07-31-contexto-del-orquestador-design.md`.
- **El indeterminado de la CI tiene ventana de gracia, y no se reclasifica** (decision 2026-07-31, medida en dos PRs de este repo). `bloqueada: ci-indeterminada` (decision del 2026-07-30, arriba) acerto el **diagnostico** y se equivoco en **cuando creerselo**: el paso 9 cerraba con el primer `sin-checks`/`desconocido`. Medido: en la **PR #31**, a segundos de crearla, `ci-status` devolvio `desconocido` con exit 4 -hallazgos "respuesta de gh no parseable: (respuesta vacia)" y "no checks reported on the ... branch"- y **veinte segundos despues** `verde` con el check `check` en `pass`; en la **PR #20**, en cambio, el mismo `desconocido` era real y permanente (cuatro ticks), porque entonces ningun workflow aplicaba a esa PR. O sea que el mismo estado significa cosas opuestas segun el momento, y cerrar en el tick 1 registra como no medible una slice sana -con nadie mirando que lo compense, porque bajo `/loop` el orquestador ya no esta en una sesion supervisada-. Arreglo: **ventana de gracia con el numero escrito, 10 ticks indeterminados consecutivos y 30 s o mas entre tick y tick**, que deja pasar el caso de la #31 (resuelto en el tick 2) y sigue cerrando el de la #20; **subida de 3 ticks a 10 el 2026-08-13**, porque 3 son 90 segundos y eso no es una ventana de gracia sino una carrera contra la cola de GitHub Actions: 10 ticks son 5 minutos, que es lo que se tarda en distinguir 'no hay CI' de 'la CI todavia no ha arrancado'. **Y el numero no es lo unico que fallaba ahi**: la PR #221 de este repo cerro `bloqueada: ci-indeterminada` a los 70 segundos de abrirse y **ninguna ventana la habria salvado**, porque su CI no iba a arrancar nunca -tenia un conflicto con `master`, y GitHub Actions no ejecuta un workflow de `pull_request` sobre una pull request inmergeable: el evento corre sobre el merge commit (`refs/pull/N/merge`), que con conflicto no se puede construir-. O sea que `ci-indeterminada` esta fundiendo dos causas que se arreglan en sitios distintos: **'los checks todavia no han llegado'** -que es lo que la ventana espera- y **'esta pull request no se puede mergear'**, que ninguna espera resuelve y que `gh pr view --json mergeable` dice sin ambiguedad. Distinguirlas es trabajo pendiente, y hasta que se haga el diagnostico manda a mirar al sitio equivocado; la separacion minima no es decoracion, sin ella tres ticks seguidos son tres segundos y la ventana no cubre nada. Descartada la alternativa barata de **reclasificar `desconocido` a `pendiente`**: ese estado significa "hay checks corriendo" y tickea hasta el timeout, asi que una PR sin CI pasaria de cerrar con un motivo exacto a colgarse cuatro minutos sin causa visible, que es justo el fallo que `ci-indeterminada` vino a arreglar. Lo que cambia es **cuanto se espera antes de creerse el diagnostico**, no el diagnostico: agotada la ventana el cierre es el mismo fail-closed de antes (ni verde, ni reintento de la slice, PR abierto, `bloqueada: ci-indeterminada` + metrica `ci=none`). El numero **se quedo en prosa** en su dia, contra la regla de que lo que es regla exacta pasa a script, y no por comodidad: la ventana es una cuenta **entre** invocaciones, y `ci-status` es de un tiro y sin estado a proposito -un script que poll-ee es la shell bloqueante que la skill prohibe, y persistir la cuenta exigiria el estado local que se elimino en 2026-07-23-, mientras que la parte que fallaba en silencio (clasificar) si estaba offloadeada: el exit 4 dice "indeterminado" sin ambiguedad y nunca colapsa en verde. **Eso caduco cuando el orquestador paso a ser un programa**: la cuenta entre invocaciones tiene donde vivir (`Budgets` en `src/slice_runner/domain/budgets.py`, que es tambien donde viven los otros presupuestos del loop), la decide una funcion pura, y las copias que siguen en prosa -la docstring de `controles.py`, que es donde se mira al dudar de la invocacion, este parrafo y el `README.md`- **si las compara un control** (`tests/test_skill_contracts.py`), asi que mover el numero ya no es moverlas a mano una por una sin red. `ci-status` sigue sin estado.
- **Que hacer con un hallazgo que no bloquea, decidido por regla** (decision 2026-07-31, clasificando seis decisiones reales del mismo dia). El paso 7 declaraba que `media`/`baja` **no bloquean** y no decia nada mas, asi que que hacer con ellos lo improvisaba el orquestador: en una sola jornada el mismo tipo de hallazgo recibio **tres tratos distintos** -reintento, deuda declarada, y reintento hasta agotar el presupuesto-. En Nivel 1 lo compensa la persona que esta mirando; en Nivel 2 la varianza se hereda sin testigo, que es el motivo de arreglarlo ahora. Las seis decisiones: (1) un `README` que seguia afirmando de todas sus recetas lo que tras la slice solo valia para tres; (2) una docstring de modulo que decia que el exit 4 significa "para" cuando el paso 9 acababa de pasar a "cuenta un tick"; (3) `docs/design-notes.md`, declarado registro completo, sin la decision que la slice tomaba; (4) un paso de receta que justificaba un precheck con un argumento que el comando no sostiene -reintento los cuatro-; (5) una docstring citando un numero de paso desfasado, defecto **preexistente**; (6) un parrafo sin re-envolver, una frase redundante y una errata gramatical -deuda los dos-. Se probo primero el eje obvio, **la severidad**, y **no separa los casos**: 1-3 son `media` y 4 es `baja` con el mismo trato, mientras 5 y 6 son `baja` con el trato opuesto. El eje que si los separa es **si el arbol queda incumpliendo la vara** (1-4) frente a **mejorable pero conforme** (5-6), con el matiz del 5: el incumplimiento era preexistente y el diff solo lo heredaba. De ahi las dos preguntas del paso 7 -¿deja el arbol incumpliendo la vara? y ¿esta alguna de las dos partes en el diff de esta slice?- y de ahi que la primera exija **citar las dos partes**: es lo que la hace comprobable, porque un incumplimiento tiene dos lados y una preferencia solo uno. Los seis casos eran **todos de prosa**, asi que la pregunta 1 nombra explicitamente las **dos formas** del mismo eje -afirmacion falsa en documentacion, violacion de convencion citable con regla + path en codigo-: redactada solo como "afirmar algo falso", un hallazgo sobre codigo la responde "no" por construccion y la clase entera caeria en deuda automatica, incluido el ejemplo que `agents/slice-verifier.md` ya califica de `media` (label de metrica con identificador de alta cardinalidad). Y **la cita la construye el orquestador**: el veredicto trae un solo `path` por hallazgo y el juez solo esta obligado a evidencia citable en `alta`, asi que clasificar segun lo que entregue en `media`/`baja` dependeria de algo que su contrato no promete -el otro lado se busca en el arbol o en las fuentes de convencion, y si no aparece, es preferencia y va a deuda-. No cambia nada de lo que ya estaba: solo `alta` bloquea, el presupuesto sigue siendo 2, y la vuelta al paso 5 por un hallazgo no bloqueante gasta **ese mismo** presupuesto -por eso `--reintentos-verify` se redefine como "rondas de vuelta al paso 5 que decide el juez" en vez de "rondas por `FALLA`": sigue siendo rechazo semantico, que es la frontera que ese contador protege frente a `--descartes-verify`-. Consecuencia obligada de no tocar el presupuesto: la regla dice tambien que al agotarlo los hallazgos no bloqueantes pendientes **pasan a deuda**, porque bloquear la slice por ellos contradiria que no bloquean. Y la deuda aceptada se escribe en el **cuerpo de la PR** (paso 8, seccion `## Deuda aceptada`, solo si la hay): el chat se tira, el issue lleva la spec y no la revision, y el cuerpo de la PR es lo que se sigue leyendo junto al codigo cuando alguien se pregunte por que esa linea sigue asi.
- **test-desiderata** en el verificador: bloquea solo lo grave (no determinista, no aislado, test que no verifica comportamiento); lo menor informa. Se salta en slices sin tests. Cubre **solo los tests nuevos**: un test preexistente degradado es del item de manipulacion-tests y ya esta contado ahi (el smoke del 2026-07-27 mostro los dos agentes contando el mismo assert relajado dos veces como `alta`, inflando el recuento por severidad que alimenta las metricas). Regla general anadida al veredicto: **un defecto, un hallazgo**, bajo la regla mas especifica.
- **El verificador no audita el historial de commits.** La rubrica pedia que el test "precediera a la implementacion", y eso es inverificable por diseno en este flujo: `slice-runner` entrega la slice en **un solo commit**, asi que el historial nunca puede acreditarlo. En el smoke del 2026-07-27 los tres agentes reportaron "no puedo constatarlo", o sea un hallazgo de ruido garantizado en **todas** las slices, que erosiona la senal del resto de la rubrica. El item pasa a llamarse **cobertura por capa** y solo comprueba que exista un test por AC (o "suite intacta + efecto verificado" en capas eximidas); el ciclo red-green lo garantiza en origen el implementador via `superpowers:test-driven-development`, con su "watch it fail" obligatorio.
- **Refactor tras cada verde** en el implementador.
- **No hace merge.** Para en "PR abierto + CI verde". Merge humano.
- **Fail-closed si el entorno veta los subagentes** (decision 2026-07-28). Descubierto en caliente: una sesion real de `deploy-watch` en otro repo se encontro con una instruccion global de "no uses el Agent tool salvo que el usuario lo pida" y, al no poder lanzar los colectores, avisó y recogio las senales inline. La instruccion no esta en ningun fichero local -descartados `CLAUDE.md` (global, de proyecto y de padres), `settings.json`, `managed-settings.json`, output-styles, `~/.claude.json`, memoria, `~/.orca`, el estado de la app y los argumentos de proceso-, asi que viene con el system prompt desde el servidor: cuenta u organizacion. **Por que salto entonces y no antes**: `deploy-watch` solo necesitaba un subagente ante anomalia (el `sre`, desde el commit inicial) hasta que `ca55675` (2026-07-24) metio colectores **por tick**; y sobre todo, esa fue la primera ejecucion real de una de estas skills sobre trabajo de verdad -aqui llevamos la semana construyendolas, no corriendolas-. `slice-runner` tenia la misma bomba sin detonar desde el commit inicial, y peor: sus dos subagentes no son condicionales. Decision: **un criterio, no dos reglas.** El primer intento hardcodeo una respuesta por skill ("el runner para, el watcher degrada"), y eso obligaba a que cada skill futura copiara la que mas se le pareciera. El criterio que las genera es: **¿se puede declarar la degradacion en el artefacto que la skill produce?** Si si, degrada y declaralo **ahi** -declararlo no es cortesia, es la condicion que autoriza a degradar-; si el artefacto entero significa justo la garantia perdida, **para**, porque producirlo seria afirmar algo falso sin que nadie aguas abajo pueda verlo. El criterio y la excepcion de que **invocar una skill cuenta como pedir sus subagentes** viven **en cada skill**, no centralizados. Hubo un intento de ponerlos en `~/.claude/CLAUDE.md` -que tiene la ventaja de pesar lo mismo que el veto, al ser tambien instruccion de usuario, mientras que una skill declarando la excepcion reduce la varianza pero no tiene ese rango- y se **revirtio por decision del usuario**: era un principio load-bearing en un fichero **sin versionar y fuera del repo**, contra la premisa de que este repo es la fuente de verdad, y con blast radius sobre todos sus proyectos y maquinas. Se acepta a cambio la duplicacion del criterio en las dos skills: cuatro lineas repetidas, pero versionadas y autocontenidas. De ahi salen las dos respuestas: `slice-runner` **para** en el paso 3 con `bloqueada: sin-subagentes`, sin escribir codigo, porque su artefacto es una PR cuyo veredicto PASA *es* la afirmacion de haberse verificado -degradado seria falso y **falso de forma invisible**, ya que quien revise asume que paso el pipeline- y parar no cuesta nada irreversible; `deploy-watch` **degrada declarandolo** al arrancar y en el informe final, porque su veredicto puede decir como se obtuvo y ademas lo calcula `deploy_core.py`, no la impresion del agente, asi que la afirmacion sigue siendo verdadera. Cada skill cita a la otra como "mismo criterio, artefacto distinto", para que nadie lea la asimetria como incoherencia y la "arregle" hacia el lado facil (degradar las dos), que es el que mata la garantia. Las conclusiones (parar / degradar) se escriben tambien en cada skill, no solo el puntero: una skill debe comportarse bien aunque el criterio general no este cargado; lo centralizado es la **derivacion**, no el resultado. No se registra metrica: el issue es el registro de estado y `metrics.jsonl` es telemetria de slices **ejecutadas**; una que nunca arranco no dice nada de la calidad del loop.
- **Contexto fresco por slice, con una asimetria que hay que decir en voz alta** (patron Ralph; corregido el 2026-07-31). Los **subagentes** si arrancan limpios y mueren al terminar, y por eso todo lo caro vive en ellos. El **orquestador no**: vive en la sesion de la persona y acumula el run entero. Lo que persiste y se re-lee es el **issue de GitHub** (spec + estado), y eso es lo que hace seguro el Nivel 2 -no que el contexto se limpie solo-: como no queda estado en la sesion, se puede tirar y abrir otra entre slices. `/loop` **no** limpia contexto: reinyecta el prompt en la misma conversacion a proposito. Afirmar lo contrario era la clase de promesa que se cumple hasta que alguien la usa en serio.
- **Estado del run en el issue de GitHub** (decision 2026-07-23): la spec y el estado de cada slice viven en el cuerpo de un issue (1 feature = 1 issue), unica fuente de verdad viva y duradera. Sustituye al estado local anterior (`.slice-runner/` con `runs.jsonl`/`state.json`/`stream.log` + un panel TUI), que se **elimino**: el seguimiento pasa a ser publico y colaborativo, sin infra local. `slice-runner` reescribe la linea de la slice en cada transicion (logica pura en `scripts/issue_body.py`, I/O en `gh`); `deploy-watch` comenta su veredicto.
- **Metricas durables fuera del repo**: `~/.claude/slice-runner/metrics.jsonl` (append-only, no versionado, sobrevive al descarte) para medir "cuando subir de nivel". Lo escribe el programa el mismo (`LocalMetricsLog`); `scripts/metrics.py` solo lo agrega.
- **Coste**: presupuesto de tokens/$ por slice como circuit breaker adicional; metrica = coste por slice mergeada (no por intentada). Motivado por el research (coste hasta 30x impredecible, Stanford). El coste vive en las metricas durables (`~/.claude/slice-runner/metrics.jsonl`), fuera del repo.

### Por que estas decisiones (fuentes)

- **Loop engineering** (Boris Cherny, Addy Osmani, LangChain): assess-act-verify-stop, worktrees para aislar, estado fuera del contexto, escritor != verificador, controles de parada objetivos, circuit breaker.
  - https://addyosmani.com/blog/loop-engineering/
  - https://www.langchain.com/blog/the-art-of-loop-engineering
- **ai-patterns** (Lada Kesseler et al.): check-alignment (evita silent-misalignment), reference-docs (cargar convenciones on-demand), offload-deterministic (make/gh en vez de juicio del modelo), context-markers (el testigo `[slice-runner]`), feedback-flip / focused-agent (verificador adversarial), reminders (lista de no negociables).
- **Bryan Finster, "Agentic Workflows: Do Agents Work?"** (empirico, 5 experimentos con coste medido):
  - Small batches ganan; requisitos claros son innegociables (valida check-alignment).
  - **Refactor tras cada verde** es el driver de calidad, no el orden test-first -> por eso se anadio como paso explicito.
  - Test-first no aporta medible en agentes -> ANOTADO, pero se mantiene TDD estricto porque el `CLAUDE.md` del repo lo manda (gana la convencion). Revisable si el repo cambia.
  - Split authorship costo 3x sin ganancia consistente porque los AC ocultos ya gobernaban -> por eso el verificador se reenfoca a convenciones/arquitectura (que Finster no midio) en vez de re-testear.
  - No sobre-testear (mutation scores altos en los peores workflows) -> respalda test-desiderata "bloquea solo lo grave".
  - https://bryanfinster.substack.com/p/agentic-workflows-do-agents-work
- **Honk (Spotify), serie de 4 partes sobre su agente de background** (1.500+ PRs mergeadas en produccion):
  - Los verificadores deterministas **no se exponen al agente** uno a uno: una sola tool `verify`, activada por contenido del componente, que parsea su propia salida y devuelve solo lo relevante. El agente "no necesita entender los detalles de invocar distintos build systems" -> es el argumento de `controles.py controles`.
  - Corren **en cada turno** y otra vez **antes de abrir la PR**, esto ultimo via **stop hook**: la garantia la da el harness, no el agente -> nuestro equivalente es el backstop del orquestador (una skill no debe instalar hooks globales).
  - El **juez LLM** corre despues de todos los verificadores y recibe **el diff y el prompt original, nada mas** -> por eso el nuestro no recibe nada de los controles.
  - Veta **~25%** de miles de sesiones y el agente corrige la trayectoria **la mitad** de las veces: es la tasa de calibracion que nuestras metricas todavia no saben medir (solo registran el veredicto terminal por slice).
  - **No copiado a proposito**: su parseo por regex es *por build system* sobre un toolchain que ellos controlan y estandarizan; nosotros autodetectamos `make`/`pyproject` en repos ajenos, donde un regex que no matchea **oculta el error real**. Se transfiere el patron, no la implementacion.
  - Su parte 4 confirma el punto ciego que nos queda: donde no habia testing automatizado (dbt, BigQuery Runner) **no pudieron verificar** y los equipos dueños tuvieron que testear a mano -> nuestro equivalente son las slices con exencion de capa, donde el juez no cubre el modo de fallo "pasa CI pero es incorrecto".
  - https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3

### Ideas para iterar (no construidas)

- Chequeo de independencia entre slices (solape de ficheros/migraciones) para habilitar paralelo seguro.
- Nivel 3 con Workflow fan-out: N implementadores en worktrees, aislamiento de entorno de test por worktree (COMPOSE_PROJECT_NAME/puertos), estrategia de orden de merge (serializar quien toque alembic).
- Convencion para archivar/marcar planes ya entregados y que el selector de "siguiente slice" no tropiece con specs stale.

## Como se escribe una convencion (lo que se midio)

La regla vive en `docs/conventions/como-se-escribe.md`. Lo que la sostiene se midio en un playground
-un mini-repo con la misma arquitectura, cinco repeticiones por variante-, porque la discusion llevaba
rato siendo de intuiciones:

- **El molde no mejora el acierto; ahorra el descubrimiento.** Con la regla del puerto que solo consume
  la infraestructura, y el precedente del arbol jugando en contra, **las tres formas de darla acertaron
  5/5**: regla sola, regla con puntero al fichero real, y regla con molde embebido. Lo que cambio fue el
  trabajo: **5 turnos con molde frente a 19 sin el**. De ahi que el molde se ponga donde el caso es
  frecuente y no en todas las reglas.
- **El volumen no rompe el cumplimiento.** La misma regla enterrada entre otras ~280 lineas siguio
  acertando 5/5. Por eso partir un documento **no** se justifica por su tamano; se justifica por poder
  cargar un tema sin llevarse los otros, que es otra cosa.
- **El censo es lo que se cobra.** Con una convencion que contaba los miembros de un enum y la tarea de
  anadir uno, la convencion quedo mintiendo en **1 de 5** intentos. Pedir explicitamente que se
  actualice lo arregla (5/5), pero el dato que decidio el diseno es otro: **con censo, el implementador
  edita `docs/conventions/` en 4 y 5 de cada 5 intentos; sin censo, en 0**. Su propio brief le dice que
  no tiene autoridad para cambiar la vara con la que se le mide, asi que una convencion que le obliga a
  tocarla ha dejado de ser vara. Con cinco repeticiones la diferencia 4/5 frente a 5/5 no es
  concluyente; la de la ultima columna, si.

El origen: de 38 hallazgos bloqueantes o medios del dogfooding, **seis eran prosa caducada** -conteos y
listas cerradas que la propia slice invalidaba-, y `infrastructure.md` concentraba 10 de los 18 de
severidad alta.

## Por donde se le entrega una convencion (lo que se midio)

La pregunta era si las convenciones rinden mas como `.md` que el implementador tiene que leer, o
inyectadas en el prompt, o dentro de una skill. Se midio con el arnes de `playground/` -tarea fija de
siete ficheros, cinco repeticiones, quince reglas comprobadas sobre el arbol resultante con el arbol
sintactico- y **las mismas 565 lineas** entregadas por cuatro canales: ninguno (control), puntero al
fichero, texto integro en el prompt, y skill del repo.

- **El canal no cambia el cumplimiento: empate.** De las quince reglas, cuatro discriminan -dominio
  plano, nombres de test largos, usar mother, y no escribir tests unitarios de dominio-. En esas cuatro:
  puntero **20/20**, inyectado **20/20**, skill **19/20**. No hay razon de eficacia para preferir un
  canal, asi que la eleccion se decide por coste de mantenimiento y por propiedad, no por rendimiento.
- **Lo que si pesa es que el documento llegue.** Sin ninguna convencion, esas cuatro reglas caen a
  **0/5, 0/5, 0/5 y 1/5**. El documento no es decorativo; el canal por el que viaja, si.
- **Inyectar gasta menos turnos que apuntar, y es la unica diferencia que aguanta.** Inyectado
  **19,6 turnos [18-21]** frente a puntero **24,0 [22-26]**: los rangos no se solapan, y son los `Read`
  que uno paga y el otro no. En dolares los cuatro rangos se solapan -0,68 / 0,89 / 0,80 / 0,74- asi que
  con cinco repeticiones **no se puede afirmar** que ninguno sea mas barato. El puntero es ademas el mas
  lento (234 s frente a 168-183 s).
- **Once de las quince reglas se cumplen sin convenciones.** El suelo es alto: o el modelo ya las hace, o
  vienen del `CLAUDE.md` global de la maquina. El valor de una convencion se concentra en las reglas
  **contraintuitivas**, y escribir las otras once no esta cambiando nada.
- **Sin convenciones se gastan mas turnos, no menos** (31 frente a 20-24): el modelo se inventa mas
  estructura -subcarpetas por tipo, tests de dominio- que luego hay que deshacer.

**Alcance de lo medido, para no estirarlo.** Es la semilla desnuda: un arbol sin codigo vecino. En
produccion el codigo de alrededor ensena por imitacion y el documento puede anadir menos, y eso lo
mediria la semilla poblada, que esta construida y sin correr. La tarea son siete ficheros, no los veinte
de una slice real.

**Y el coste real de medir no es el que se creia.** Cada llamada de este experimento salio a **0,75 $**,
asi que una tanda de cuatro variantes por cinco repeticiones cuesta unos **15 $**, no los dos que se
venian citando. Sigue siendo barato frente a una slice -la mas caro registrada, la slice-05 de #117, costo
**28 $** en 396 turnos- pero ya no es calderilla, y decide cuantas hipotesis se pueden permitir.

## El programa (`src/slice_runner/`)

Lo que sigue vivia dentro de `docs/conventions/`, mezclado con las reglas. Se movio aqui cuando
`docs/conventions/como-se-escribe.md` fijo que una convencion dice la regla y no narra como se llego a
ella: el relato no es vara de nada, y leerlo cada vez que se va a escribir codigo es contexto que no
mide. Las reglas que salen de estas decisiones siguen en su capa.

### De donde salen los numeros de `Budgets`

- **Los topes de espera de una invocacion, que fueron uno solo hasta el 2026-08-13.** El de la
  integracion continua sale de que la de este repo esta medida entre 15 y 33 segundos sobre 25 runs, asi
  que el numero no lo fija ella: lo fija el repo destino peor, y hay uno escrito -un `make test` de ~20
  minutos, en `skills/slice-spec/SKILL.md`- que hay que despejar con margen. El de las esperas humanas
  -alineacion y merge- sale de otra pregunta distinta: cuanto puede tardar una persona en estar delante
  sin que eso signifique que algo va mal, y ahi una jornada es lo razonable.

  **Fueron el mismo numero, con un acumulador unico para todo el run, y eso hacia que el ultimo que
  esperaba pagase lo que gastaron los demas.** Medido en la slice-10 de este repo el 2026-08-13: 42
  ticks esperando el `-GO` y 2 la integracion continua dejaron **16** para el merge -8 minutos de los
  30-, y el run murio en `WAIT_EXHAUSTED` con la pull request sana, verde y a punto de mergearse. Nada
  de eso se leia en el tope: decia 30 minutos y entregaba 8, con el reparto dependiendo de lo que una
  persona hubiera tardado antes. De ahi salen las dos mitades del arreglo -un tope por clase de espera,
  y el contador reiniciandose en cada paso-, cuya **regla** vive en `docs/conventions/domain.md`.

  La ventana de gracia de la CI indeterminada subio a la vez, y por su propio motivo: 3 ticks son 90
  segundos, que no es una ventana de gracia sino una carrera contra la cola de GitHub Actions.
- **El tope de una llamada a un proceso externo.** Lo mas largo que se ha medido llamar son los sobres
  de `claude -p` de `src/slice_runner/tests/payloads/`, cuyo mayor tarda 51 segundos, y lo mas largo
  declarado es ese `make test` de ~20 minutos. El valor elegido los despeja a los dos con margen, que es
  lo que se le pide a un backstop: ponerlo bajo no ahorra nada, mata un control sano a mitad.
- **El coste de una slice.** Nacio en 25 $ cuando el registro durable no tenia ni un dolar real y lo
  unico medido eran las llamadas grabadas en `src/slice_runner/tests/payloads/`, cuya mayor son
  **0.343 $**: dos ordenes de magnitud de margen sobre lo unico que se sabia. El numero elegido como
  techo inalcanzable resulto estar *dentro* del rango normal -las primeras muestras reales fueron
  **5.14, 10.75, 15.07, 25.46 y 27.73 $**, todas con Opus porque ninguna invocacion declaraba modelo
  todavia-, y **dos slices sanas murieron con `abortada:presupuesto`**, las dos justo despues de que el
  juez devolviera `PASA`, porque el limite se comprobaba tras pagar la llamada: se tiraba una aprobacion
  ya pagada en vez de impedir la siguiente. Con el implementador fijando Sonnet la muestra crecio con
  **8.77 y 13.75 $**, bastante por debajo del rango de Opus, lo que confirma que fijar el modelo barato
  abarata la slice tipica sin tocar el backstop. El techo subio a 50 $ **sin tocar que se cuenta**.
- **Los reintentos del juez, y por que se repartieron en vez de recortarse.** La intuicion era que llegar
  al segundo reintento significa un problema que ninguna vuelta arregla -una convencion mal escrita, un
  criterio mal definido- y que por tanto sobra. Medido sobre el corpus, es al reves: de las cuatro
  secuencias que llegaron a gastar los dos, **en tres el segundo reintento convirtio un veto que habria
  cerrado la slice en algo entregable**, y una necesito ademas un tercero. Con esa muestra no es
  concluyente, pero desaconseja recortar. Lo que si es solido es el reparto de las 60 verificaciones
  registradas: **21 vetos, 26 correcciones que no bloquean y 13 limpias**, o sea que el 43% de las vueltas
  que pagaba el presupuesto no impedian entregar nada -y ademas no convergian: hay secuencias que
  devuelven los mismos hallazgos dos veces seguidas-. De ahi que las dos causas dejaran de compartir
  contador, que es la misma regla que ya separaba la higiene de los controles. La reconstruccion se hizo
  por bloques consecutivos del mismo identificador de slice, que es lo unico posible mientras el corpus no
  tenga identidad ni instante por fila.
- **Los reintentos de una llamada a `gh`, y la espera entre ellos.** No hay corpus de fallos transitorios
  de la interfaz de programacion de GitHub del que medir un percentil, al contrario que el resto de esta
  lista: la intencion que trajo la slice es explicita en que se quiere cubrir -"un parpadeo de red, un
  handshake que se corrompe, una conexion que se cae"-, y esos son fallos de segundos, no de minutos. Tres
  intentos con dos segundos entre uno y el siguiente despejan un parpadeo de varios segundos sin que un
  servicio caido de verdad convierta la llamada en una espera larga: el tope de la invocacion sigue siendo
  `process_timeout_seconds`, que ya cubre "el proceso no vuelve nunca". Si el corpus de runs reales
  empieza a mostrar fallos transitorios que sobreviven a los tres intentos, este numero es el que hay que
  revisar con esa medicion delante.
- **El tope de tamano de las fuentes de convencion.** Nace con la slice que hace viajar su contenido
  literal dentro del prompt (issue #216) y todavia no tiene corpus de runs reales que medir: lo unico
  medido es el propio repo, cuyas seis fuentes que declara este issue suman **80126 caracteres**
  (`wc -c docs/conventions/{code-style,architecture,domain,application,infrastructure,testing}.md`). El
  numero elegido, **200000**, deja algo mas de dos veces y media de margen sobre ese caso real -la misma
  logica que el techo de coste, que se fijo con margen sobre lo unico medido en su dia (arriba)-, y sigue
  siendo un backstop y no una preferencia: existe para que una fuente declarada por error como un
  directorio entero, o un `.md` que crecio sin que nadie lo revisara, pare el run con su motivo en vez de
  mandar un prompt desproporcionado. Cuando el corpus de runs reales tenga fuentes mas grandes que las de
  este repo, este numero es el que hay que revisar con esa medicion delante.

### El descarte de aprobacion pagada, y por que hay dos comprobaciones de coste

La comprobacion de despues de la llamada cierra el bucle del descarte del juez -que no gasta reintento
porque no se toco el codigo-, y la de antes es la que faltaba para no tirar una aprobacion ya pagada.
Preguntarselo al **agregado** en vez de a la llamada tenia el agujero entero dentro: como una llamada sin
medicion no anade nada a la suma, bastaba **una** medicion previa en la invocacion para que el total
quedase medido para siempre, y a partir de ahi cada llamada que muriera sin sobre parseable dejaba el
total congelado por debajo del limite.

### Por que el juez tambien fija modelo, y por que uno mas caro que el implementador

Los 25-28 $ se pagaron con Opus porque ninguna invocacion declaraba modelo. La primera correccion fue
asimetrica: el implementador fija el barato porque su trabajo lo revisa otro, y el juez se dejaba heredar
el de quien lanza el run. El problema de esa asimetria no era el argumento: era que "heredar" no es una
politica declarada, es la ausencia de una. `RoleModels` no tenia campo `verify`, asi que ni el conductor
podia decir con que modelo corria el juez ni la fila durable lo escribia -no se podia saber con que se
juzgo una slice ya cerrada, ni separar su coste del de la sesion que lanzo el run (issue #259)-.

Declarado hay que elegir, y la eleccion es `"opus"`, frente al `"sonnet"` que fijan `ImplementerInvocation`
y `UnderstandingInvocation`. **No la sostiene ningun corpus**: nada de las 60 verificaciones registradas
(mas arriba) compara el mismo diff juzgado por dos modelos distintos. Lo que la sostiene es la asimetria
del coste del error. Un implementador flojo cuesta una ronda de correccion mas, que se ve en el momento y
se paga una vez; un juez flojo aprueba una pull request mala, que no se ve y la paga quien venga detras.
Mientras no haya medicion, se prefiere pagar de mas en el ultimo control antes que de menos.

Lo que hace que esto sea una decision reversible y no una preferencia enterrada es la otra mitad de la
slice: `models_by_role.verify` viaja en la fila durable, asi que en cuanto haya runs del mismo diff
juzgados por modelos distintos se podran comparar, y bajarlo sera cambiar una constante con los datos
delante. Hay test de las tres cosas: que `RoleModels` no se construye sin `verify`, que
`JudgeInvocation.argv` emite `--model`, y que la fila durable lo trae.

### La duplicacion con `skills/`: por que se acepta

Hubo una version del programa que reutilizaba `escribe_diff_bundle` y `valida_veredicto` de
`controles.py` para no duplicar logica, y el resultado fue peor: obligaba a que el programa arrastrase el
`pythonpath` del script, a escribir un `files.txt` que solo el flujo viejo necesita, y a pasar el
veredicto por un validador que Pydantic ya hacia redundante. **Acoplar el flujo nuevo al viejo para
ahorrar duplicacion sale mas caro que la duplicacion**, porque el viejo esta condenado.

### El juez como objeto, y no como proveedor de prompt

`Judge(rubric, tools, readable)` sustituye a un `PromptProvider` que solo devolvia texto. Con la rubrica,
las herramientas y los directorios legibles repartidos por capas distintas, nada obligaba a que
cuadrasen: la rubrica llego a ordenar cargar skills que el juez no podia leer, y el veredicto salia igual
de limpio. Un puerto para un valor constante era indireccion; el invariante necesitaba un objeto. La
forma viene del agente raiz de `roman_expert/chat_agents` en `mercadona/mo.staff.django-playground`.

### El registro de un paso sale del conductor, y por que no se saco mas

`ConductSlice` decidia el flujo del run **y ademas** componia a mano su telemetria: el evento de cada
transicion y la fila durable de cada cierre, esta ultima en dos sitios distintos. La consecuencia no era
estetica: cualquier slice que anadiera un campo al registro tenia que entrar en la pieza que decide cuando
se implementa, cuando se juzga y cuando se cierra.

**El dato que lo decidio fue el reparto de lo pendiente.** De las nueve slices abiertas en ese momento,
cuatro tocaban el registro (identidad de cada fila, configuracion y tamano del cambio, formato de los
almacenes, rastro duplicado) y cuatro tocaban la ejecucion y la alineacion (desbloquear un run, indultar un
hallazgo, pedir cambios sobre la pull request). Partido justo por la mitad, y las dos mitades colisionando
en el mismo fichero sin tener nada que ver entre si: el paralelismo estaba capado por diseno, no por como
estuvieran priorizadas.

Se extrajo **solo el registro**, no las cinco responsabilidades que tenia. Sacar tambien la ejecucion de
cada paso no compraba nada -esos metodos ya delegaban en casos de uso y no escondian logica-, y sacar el
repositorio del issue habria obligado a inventar un caso de uso por cada lectura, porque la alineacion lo
necesita para publicar el entendimiento, leer la respuesta y pausar.

**Lo que mide el cambio no son las lineas** -el conductor bajo de 599 a 581, apenas nada- sino que dejo de
nombrar ningun tipo de telemetria. Y de paso unifico una regla que estaba escrita en uno de los dos cierres
y no en el otro: un gasto que nunca se midio no entra en la fila, en vez de contar como cero.

### El agrupamiento de dependencias no era del conductor, era de lo que se recorre (2026-08-14)

La desviacion se escribio con un ancla equivocada: decia que agrupar los puertos era **del conductor**,
por ser "la unica pieza que compone casi todos los puertos del programa". Eso no es una regla, es un
censo de un dia, y el propio `docs/conventions/como-se-escribe.md` lo prohibe -una lista cerrada de lo que
hay hoy, presentada como si fuese la regla-.

**Lo destapo un veto.** La slice-01 de #247 necesitaba un sexto puerto en `CheckReadiness` para que el
`doctor` pudiese contrastar de que arbol salieron el programa y las skills. Seis parametros disparan
`PLR0913`, el implementador agrupo, y el juez lo bloqueo con severidad alta citando textualmente la linea
de la desviacion. El veto era correcto: la convencion decia lo que decia. Lo que no era correcto era la
convencion.

Las dos salidas que el juez ofrecio -partir la query, o enmendar la convencion- **las declaro el mismo
como decision del repo y no del implementador**, asi que el run no podia salir de ahi: cualquier cosa que
eligiera era o un veto nuevo o mover la vara con la que se le mide, que es un antipatron escrito. Se paro
el run y se decidio fuera.

**El criterio que sustituye al censo es de que es proporcional la lista de puertos.** Un caso de uso que
gana puertos porque hace mas cosas tiene una firma larga como sintoma, y se parte. Uno que los gana porque
su trabajo *es* recorrerlos -conducir un run entero, contestar si todas las piezas estan en su sitio- no
se arregla partiendolo: la misma lista queda repartida en dos piezas y aparece una tercera que las
compone. El criterio se puede aplicar a un caso de uso que todavia no existe, que es justo lo que el censo
no permitia: con la redaccion vieja, cada pieza nueva que cayera de este lado obligaba a editar la
convencion para dejarla veraz.

Coste medido del fallo: el run de la slice-01 de #247 se paro a los 36 minutos y 9,76 $, con una llamada
al juez tirada a mitad.

### La forma de una lista, extraida al tercer consumidor

`CountedLines` vivio duplicada a proposito mientras solo la compartian dos prompts: cada uno es un
contrato con un agente distinto y nada exige que se parezcan, asi que extraerla habria fijado un parecido
que no era invariante. La convencion se escribio a si misma la condicion "con un tercer prompt se
extrae", el entendimiento fue ese tercero, y la condicion se cumplio -aunque no sola: el juez veto la
slice con severidad `alta` citando esa misma linea-. Que una condicion escrita se ejecute importa mas que
la regla concreta; la que nadie ejecuta ensena que el fichero donde vive es opinion.

### El commit unico por slice era un residuo, y se retira (2026-08-11)

Nadie decidio nunca que una slice fuese un solo commit. Salio de la decision del 2026-07-30 de mover el
commit **detras** del veredicto -para que un veredicto negativo no dejara rastro que deshacer-, y "un
solo commit **sin `--amend`**" quedo escrito ahi como la consecuencia barata de ese movimiento, no como
un objetivo. El precio si se registro: la rubrica del juez tenia un item que pedia que el test precediera
a la implementacion, y hubo que retirarlo porque el historial de un commit unico nunca puede acreditarlo;
en el smoke del 2026-07-27 los tres agentes contestaron "no puedo constatarlo", o sea ruido garantizado
en todas las slices.

Se retira porque una ronda de correccion fundida con lo que corrige obliga a quien revisa a reconstruir
del diff final que se pidio cambiar. Lo que devuelve la vuelta atras no es solo permiso: es la capacidad
de acreditar en el historial el orden en que se hizo el trabajo, que se habia dado por perdida. Lo que
**no** cambia es lo que era decision propia y no consecuencia: `git add` con rutas explicitas, la higiene
del indice antes de cada commit, y `--merge` al fusionar.

### La pull request deja de nacer en borrador, y gana asignado y co-autor (2026-08-13)

Nacia con `--draft` desde el commit inicial del programa, y el motivo escrito era "el merge lo decide una
persona". Ese motivo **ya lo garantizaba otra cosa**: el programa no mergea, se para en `esperando-merge`
y termina. Lo que el borrador anadia encima no era control, era un paso manual que nada recordaba.

Se pago el mismo dia que se retiro: el run de la slice-10 de este repo agoto su espera de merge con la
pull request verde, el veredicto dado y todo hecho, porque nadie la habia sacado de borrador. El programa
tuvo que decirlo con un aviso que existia **solo** para compensar el borrador -y que se queda, porque
sigue habiendo esperas que se agotan, pero deja de afirmar que la pull request nace en borrador, que ya no
es cierto-.

Entran a la vez dos cosas que hacen visible quien hizo que: **asignada a quien conduce el run**, porque es
quien tiene que mergear y asi le aparece en su lista, y **el commit acreditando a Claude como co-autor**,
que es el mismo mecanismo que usan las pull requests que salen de una sesion de Claude Code. Lo que **no**
entra es Claude como asignado: comprobado contra la interfaz de programacion de GitHub, solo se puede
asignar a colaboradores del repo, asi que seria una llamada que falla o que se ignora en silencio.

### Que se rompe hoy al reanudar un run, y en que orden vale la pena arreglarlo (2026-08-11)

El `Run` que se persiste en la subissue lleva nueve campos; el progreso que el conductor tiene en memoria,
catorce. Lo que se pierde no es adorno: sin los veredictos, una reanudacion en el paso de implementar
manda al implementador sin los hallazgos que tiene que corregir; sin la lista de ficheros que el
implementador declaro, una reanudacion en los controles stagea una lista vacia y **acusa de infraccion de
higiene a todos los ficheros que si estaban bien**, gastandole un reintento.

Lo que se descubrio al medirlo es que **el mundo ya guarda casi todo**: los veredictos con sus hallazgos
en el corpus, los logs de los controles en disco con nombre determinista, el gasto por llamada en su log,
y la pull request la sabe el foro. Solo tres datos no viven en ningun sitio. Asi que el patron a extender
no es persistir mas, sino releer -que es lo que ya hace el entendimiento, la unica pieza que sobrevive
limpia a una muerte-. Su precio es que releer necesita poder buscar sin ambiguedad, y eso depende de que
cada fila diga de que run viene.

El orden se decidio poniendo cada arreglo contra un fallo real (un run que gasto quince dolares y murio
al entregar porque su rama no existia):

| | coste | que habria hecho en ese fallo |
|---|---|---|
| Comprobar el suelo al reanudar | quitar una condicion, mas tests | parar en el segundo cero, sin gastar |
| Caer escribiendo estado | pequeno | dejar dicho que paso en vez de quedarse en curso |
| Releer el mundo | varias lecturas nuevas, y depende de la identidad de las filas | nada: el estado no era el problema |
| Commit por paso | contenido | conservar el codigo, y fallar igual al entregar |

Lo barato es lo que mas valia, asi que va primero, y es lo contrario del orden en que se habia listado.

### Los hallazgos indultables se publican, y el comentario manda (2026-08-11)

Para indultar un hallazgo en una invocacion distinta a la que lo produjo hace falta que el hallazgo
sobreviva con identidad. El veredicto entero ya esta escrito en el corpus, asi que la opcion coherente con
"un segundo sitio donde escribir puede desmentir al primero" era que el corpus mandase y el comentario
fuese solo una vista. Se eligio lo contrario -el comentario de la subissue es la fuente de verdad- por dos
razones: quien indulta es una persona y necesita ver lo que indulta, y el corpus solo se puede buscar sin
ambiguedad cuando sus filas digan de que run vienen, que es trabajo que va por detras. El corpus se queda
en lo que es hoy, material de medicion agregada.

### Donde se va el dinero de un run, medido (2026-08-11)

Sobre 122 sesiones y 342 $ de gasto acumulado, uniendo el rastro de llamadas con el de gasto por sesion:

| paso | % del gasto | $/llamada | turnos/llamada |
|---|---|---|---|
| implementar | 68 | 4,49 | 66 |
| verificar | 21 | 1,91 | 26 |
| entender | 11 | 1,17 | 30 |

Lo que descoloca es la descomposicion de esa llamada de implementacion: **el 65% es lectura de cache**
-9,7 millones de tokens releidos a lo largo de sus 66 turnos- y **la salida es el 6%**. No se paga por
lo que el modelo escribe, se paga por el contexto que arrastra.

Y el dato que decide donde mirar: comparando la primera llamada de implementacion de cada slice con las
siguientes, **cuestan casi lo mismo** (4,70 $ y 10,2 M de lectura frente a 4,38 $ y 9,5 M). Una vuelta de
correccion **redescubre el repo entero**: repite los mismos listados y las mismas lecturas que una
llamada anterior de la misma slice hizo minutos antes. Como dos de cada tres llamadas de implementacion
son segundas o posteriores, ahi se va **el grueso de lo que cuesta implementar**.

De ahi salen tres candidatos, y el orden por premio no coincide con el orden por esfuerzo: reanudar la
sesion del arnes entre vueltas -el identificador ya se guarda en el rastro desde siempre y nunca se ha
usado-, bajar de modelo al que produce -coherente con que su trabajo lo revise otro-, e inyectar las
convenciones en vez de apuntarlas. El tercero **no se aplica por ahora**: lo que se midio inyectaba un
documento, y la vara real son decenas de miles de tokens repartidos en varios ficheros, o sea fuera del
rango medido. Los otros dos se miden en el playground antes de tocar nada.

**El riesgo de reanudar no es el que parecia.** La objecion inicial -que la sesion vieja contamine con
decisiones previas- se cambio por una mas concreta y medible: un implementador reanudado **defiende su
propio diseno** cuando el hallazgo contradice lo que eligio. La tarea `implementer-resume` lo mide con dos
hallazgos a la vez, uno que anade trabajo -donde reanudar deberia ganar- y otro que revierte una decision
suya -donde deberia perder-.

### Reanudar la sesion parte los turnos por la mitad y no ahorra nada (2026-08-11)

Medido con `implementer-resume`, cinco repeticiones por variante, dos vueltas por celda:

| segunda vuelta | llamada nueva | sesion reanudada |
|---|---|---|
| turnos | 24,4 (rango 22-26) | 11,0 (rango 9-14) |
| coste | 0,370 $ (0,348-0,397) | 0,403 $ (0,347-0,473) |
| lectura de cache | 292 k | 440 k |
| segundos | 121,9 | 127,1 |

Los rangos de **turnos no se solapan**; los de **coste se solapan enteros**, con la sesion reanudada
tendiendo a mas cara. El mecanismo esta en la lectura de cache: cada turno reanudado arrastra la
conversacion anterior entera -unos 40 k por turno frente a 12 k-, asi que se cambian muchos turnos
pequenos por pocos turnos grandes y **el producto sale igual**. Tampoco gana en reloj.

La consecuencia para donde buscar ahorro es que **el coste es turnos por contexto**, y reanudar mueve los
dos factores en direcciones opuestas. Lo que si mueve el producto es el precio del token -o sea el
modelo- o el contexto que se arrastra por turno. Reanudar se queda como herramienta de **latencia en
numero de pasos**, no de dinero, y en un repo mas grande deberia salir **peor**, no mejor: la sesion de
la primera vuelta es ahi mucho mas larga, asi que lo que arrastra cada turno reanudado crece con ella.

Y el riesgo que se habia elevado a hipotesis principal **no aparecio**: el hallazgo que revierte la
decision del propio implementador lo corrigieron **las dos variantes en las cinco repeticiones**. Las seis
reglas salieron 5/5 en ambas, asi que reanudar tampoco degrada. Simplemente no compra lo que se buscaba.

### Haiku implementando: 78% mas barato, y 2 de cada 5 salen defectuosas (2026-08-11, sin cerrar)

Misma tarea `implementer-resume`, misma semilla, solo la variante de llamada nueva, cinco repeticiones
por modelo. Antes de medir se anadio la regla que faltaba y que es la unica que dice si el codigo
**funciona**: ejecutar los tests que el propio modelo escribio. Las seis anteriores comprueban forma, y
un modelo mas flojo puede cumplirlas todas y escribir algo que no arranca.

| | el caro | el barato |
|---|---|---|
| coste por celda, dos vueltas | 0,874 $ | 0,191 $ |
| segundos | 246 | 114 |
| celdas sin una sola regla en falso | 5/5 | 3/5 |

**Los dos fallos son modos distintos y los dos importan.** Uno no hizo el trabajo -no existe el caso de
uso pedido, y su coste, la mitad que el de las demas, lo delata: hizo la mitad de los turnos y se dio por
terminado-. El otro lo hizo entero y **sus propios tests no pasan**, que es exactamente lo que las reglas
de forma no ven.

En el pipeline real ninguno de los dos llega a una pull request: el de los tests lo caza el control de
tests y el otro lo caza el juez, asi que **el coste de fallar es una vuelta extra**, no codigo malo
mergeado. Y el punto de equilibrio calculado sobre el gasto real dice que el modelo barato tendria que
subir la media de vueltas extra de 1,04 a **2,8** para dejar de ahorrar; un 40% de defectuosas la deja
alrededor de 1,5-1,9. Compensa, y con margen.

**Por que no se ha decidido.** Dos fallos sobre cinco dejan la tasa real en cualquier sitio entre el 10% y
el 70%, y es el numero del que depende todo. Afinarlo cuesta unos 3 $ -cada celda del barato son 0,20 $-,
que es lo que hay que gastar antes de tocar nada:

```bash
python3 playground/harness.py implementer-resume --label haiku --variants fresh \
  --seeds seed-populated --repetitions 20 --model haiku
```

Y aunque salga bien, **el experimento no mide el factor que decide**: cuantas vueltas de correccion pide
el modelo barato contra el juez de verdad, en un repo grande. Eso solo se ve conduciendo dos o tres slices
reales y mirando los reintentos, no en el banco.

### Un esquema sin suelo deja publicar el relleno (lo que se midio)

El 2026-08-13 una slice publico como entendimiento esto: resumen `test`, un paso `a` con motivo `b`,
esbozo `test`. Se publico con la firma del programa, y le paso lo mismo a otra persona ese mismo dia.

**Lo que la transcripcion de la sesion enseno.** El modelo llamo a `StructuredOutput` **cuatro veces**:
el informe bueno con el JSON mal escapado (rechazado por no parsear), dos intentos corregidos a los que
**se les habia caido `steps`** (rechazados por el esquema), y un cuarto minimizado a valores de relleno
que **si valido**. El programa se queda con el ultimo. No es que el modelo no trabajase: esa llamada
gasto 49.691 tokens de salida y 2,67 $, **mas que el entendimiento bueno que vino despues** (48.059 y
2,25 $). Minimizar tras tres rechazos es lo que hace cualquiera para aislar un fallo; lo que no puede
pasar es que el minimo se publique.

**No era no determinismo: era una regresion con fecha.** Sobre las 115 sesiones de arnes con
transcripcion, contando las que necesitaron mas de un intento de salida estructurada:

| Paso | Sesiones | Con mas de un intento |
|---|---|---|
| `verify` | 39 | 0 |
| `implement` | 45 | 4 (repartidas por todo el histórico) |
| `understand`, esquema de un campo de texto | 25 | **0** |
| `understand`, esquema de tres campos | 6 | **5** |

El corte es el commit que partio el entendimiento en `summary`/`steps`/`sketch`, donde `sketch` pedia
firmas de codigo. Escribir codigo dentro de un JSON es donde se rompe el escapado, y por eso `verify`
-cuyo esquema son campos cortos- no falla nunca.

**Y el esquema no tenia con que parar el relleno.** Tras retirar los cuatro topes maximos por no
haberselos contado al modelo, quedo sin ninguna restriccion: `{"summary": "test", ...}` era formalmente
valido, asi que el arnes contesto `Structured output provided successfully`. La simetria es la leccion:
**los maximos sin contar mataron una slice por rechazo, y la ausencia de minimos mato a otra por
aceptacion**. La vara va en el esquema **y** en el brief, en los dos sentidos.

**Los minimos se calibraron contra lo que ya funcionaba**, para que sean suelo contra el relleno y no
cuota que llenar. De los cinco entendimientos buenos del formato nuevo: resumenes de **669, 673, 805,
809 y 1.075** caracteres y **7 u 8** pasos. Con el suelo en 120 caracteres y 2 pasos, el mas ajustado
pasa con **5,5 veces** de margen, y el degradado -4 caracteres y 1 paso- no pasa.

**El esbozo se veia mal por otra cosa, y tambien se arreglo aqui:** el programa pegaba el texto crudo
bajo `## Esbozo` sin envolverlo, asi que markdown fundia las lineas de dos espacios con el parrafo
anterior y convertia las de cuatro en bloque. Ahora el esbozo viaja como **lista de piezas**
(`signature`, `does`) y el bloque lo compone el programa: el modelo escribe datos y no markdown, que de
paso es menos texto libre que escapar.

**Lo que sigue sin cerrarse:** el programa no ve la pelea. Sabe que hubo cuatro intentos y tres
rechazos solo porque alguien leyo la transcripcion a mano. Se cierra a medias marcando en el registro
durable de usos de herramienta las llamadas que el arnes rechazo (`failed`), que es lo que deja contar
la tasa sin abrir un `.jsonl` de sesion; decidir **que hacer** con una llamada peleada -descartarla y
repetirla, como ya hace el paso de verificar- sigue pendiente, y con la tasa de hoy rechazarlas todas
duplicaria el coste de casi todos los entendimientos.

## deploy-watch

### Decisiones clave

- **Fase post-approve, invocacion manual, read-only sobre prod.** Disparador manual elegido para cero polling en vacio.
- **Compone, no reinventa**: el agente orquesta por tick las skills de observabilidad (catalogo abierto) + agente `sre`; la decision la hace un core puro (`deploy_core.py`: umbrales relativos, confirmacion sostenida, scorecard, veredicto). Antes delegaba en una skill `deploy-monitor` suelta (script HTTP bloqueante), **absorbida en 2026-07-23**.
- **Veredicto por 4 senales**: rollout k8s, recursos (OOM/restarts/CPU), errores/latencia HTTP vs baseline, Sentry (issues nuevas del release). Sano solo si las 4 estan ok toda la ventana de estabilizacion.
- **Ante anomalia**: agente `sre` para RCA read-only + rollback redactado (git revert del merge + redeploy segun slicing.md), sin ejecutar.
- **Seguridad**: nunca ejecuta rollback ni toca backends; max_runtime + circuit breaker; merge y rollback los decide el usuario.
- **El encadenado esta apagado desde 2026-08-13, y se apago por el cableado.** El programa lleva `MutedDeployWatch` inyectado en vez de `ClaudeDeployWatch`, asi que mergear una slice ya no lanza `claude -p '/deploy-watch ...'`. El motivo es de calendario, no de diseno: la skill todavia no esta pulida -es la unica pieza del pipeline que nunca se ha medido contra un despliegue real de otra persona- y el equipo empieza a probar el flujo esta semana; una llamada que cuesta dinero, tarda y puede confundir a quien nunca ha visto la herramienta es exactamente lo que no debe encontrarse en su primera slice. **Lo que no se apago**: la linea `SENAL:` se sigue disenando en el slicing, se sigue exigiendo, y su emision sigue siendo criterio de aceptacion que el juez mide antes de mergear -o sea que lo que se pierde es la comprobacion post-deploy, no la observabilidad de la slice-. Se eligio el adaptador mudo sobre las otras dos formas por lo que cuesta **volver**: una bandera de linea de comandos anadia superficie que habria que retirar despues, y borrar la llamada de `ConductSlice` dejaba el puerto sin consumidor y obligaba a reescribir codigo y test para reencender. El detalle de la decision de capa vive en `docs/conventions/infrastructure.md`; cuando se pula, se reencienden la linea de `cli.py`, el paso 4 del `README.md` y su diagrama.

## Roadmap de autonomia (pendiente)

Estado actual: **Nivel 1** — una slice por invocacion, todo bajo control manual. Subir de nivel solo cuando el anterior sea fiable; el cuello de botella nunca es implementar, es la calidad del gate de verificacion.

- **Nivel 2 — semi-autonomo con `/loop`.** Envolver slice-runner en `/loop`: al terminar una slice (PR + CI verde), coge la siguiente pendiente sola. Guardrails a anadir antes de activarlo:
  - Circuit breaker: `max_consecutive_failures` (parar tras N slices bloqueadas seguidas).
  - `max_runtime` / tope de slices por sesion (evitar loop eterno).
  - Checkpoint humano opcional entre slices.
  - Requisito previo: confianza en el verificador; es lo que sostiene el loop sin supervision.
- **Nivel 3 — Workflow fan-out (paralelo).** Solo para slices independientes. Requiere: chequeo de independencia (solape de ficheros/migraciones), aislamiento de entorno de test por worktree (`COMPOSE_PROJECT_NAME`/puertos), y orden de merge (serializar quien toque el head de alembic).
- **Encadenar slice-runner -> deploy-watch.** Tras el merge, disparar deploy-watch automaticamente. Hoy deploy-watch es manual por decision (cero polling en vacio); la version encadenada poll-earia el estado del PR/merge para arrancar sola.
- **deploy-watch autonomo.** Opcion descartada de momento: un `/loop` que vigila el merge y arranca la monitorizacion solo. Reconsiderar si el volumen de slices crece.
- **Aislamiento mecanico del orquestador (fase 2 del coste de contexto).** La fase 1 (2026-07-31) bajo lo que cuesta el orquestador por slice, pero **no** lo saco de la sesion de la persona: el contexto limpio por slice sigue dependiendo de que ella abra sesion nueva. Lo unico que lo haria mecanico es que cada slice corra en un contexto propio -un proceso `claude -p` por slice lanzado desde un script, o un orquestador subagente-, y las dos formas chocan con el **go/no-go del paso 3**. Que es justo lo que hay que decidir explicitamente, porque bajo `/loop` **ese control humano ya es ficcion**: nadie responde una alineacion en un run desatendido, asi que Nivel 2 ya renuncio a el de facto sin escribirlo en ninguna parte. Cualquier diseno de fase 2 tiene que elegir entre recuperarlo (checkpoint humano real entre slices) o declarar que a partir de Nivel 2 no existe; heredarlo por descuido es la peor de las tres.

## Preferencias transversales

- Respuestas y skills sin emojis (preferencia del usuario) -> el testigo de contexto es un marcador de texto `[skill-name]`, no un emoji.
- Idioma: cuerpo de las skills y comunicacion en castellano; codigo/commits/PRs en ingles (convencion de los repos).
