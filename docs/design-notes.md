# Notas de diseño

> **Registro vivo del porque.** A diferencia de las otras lecturas de `docs/`, este si se sigue
> ampliando: cada decisión entra con su fecha y su motivo para no re-derivarla. No es vara de medir
> -eso son las convenciones- sino la memoria de como se llegó a ellas.

Decisiones tomadas al construir estas skills y el porque, para poder seguir iterando sin re-derivarlo.

## Contexto

Flujo de trabajo objetivo: escribo specs; cada slice de la spec quiero que se implemente sola, se valide, se abra PR y se confirme CI verde; y tras aprobar, monitorizar el despliegue. Encaja con "loop engineering" (assess -> act -> verify -> stop) y spec-driven development.

## slice-runner

### Decisiones clave

- **Nivel 1 por defecto** (una slice por invocación, para máximo control). Nivel 2 = envolver en `/loop`. Nivel 3 = Workflow fan-out (no construido; solo para slices independientes).
- **Un formato de spec**: checklist (`## Slices`, una línea `- [ ] slice-NN (name): ...` por slice). Hubo un segundo formato (plan de una slice estilo superpowers, el fichero entero = 1 slice) para consumir `docs/superpowers/plans/*.md` de un repo real; se **elimino** porque el flujo canonico (slice-spec -> slice-runner) siempre emite el checklist, y el Formato B no aportaba poder expresivo pero si superficie transversal (detección, derivación de AC, contrato duplicado en 3 sitios).
- **Los controles los declara el issue, no los deduce nadie en tiempo de run** (decisión 2026-07-29, ver abajo). Muchos repos corren todo en Docker vía `make` (`make test`, `make check-types`, `make fastapi-migrate`...) y lanzar `pytest`/`ruff` directos falla, así que hay que saber los comandos reales; lo que cambio es **quien** los sabe y **cuando**.
- **Convenciones del repo como vara de medir principal**, `backend-best-practices` como secundaria, default genérico al final. No es invento: replica la jerarquía de autoridad que declara el `CLAUDE.md` de los repos (convenciones > skill > default). Implementador y verificador cargan ambas.
- **TDD consciente de capa.** Test-first por AC en capas con test; en capas eximidas por convención (modelos ORM, migraciones alembic) el control es "suite intacta + efecto verificado", no test-first. El repo decide.
- **Gate de check-alignment** antes de implementar (mostrar entendimiento, esperar go/no-go). Evita transcribir a ciegas el código pre-horneado de una spec. En un dry-run real este gate detecto que una slice ya estaba mergeada y aborto antes de romper la cadena de alembic.
- **El ciclo TDD se delega en superpowers, los deltas se quedan** (decisión 2026-07-27): `slice-runner` reescribia de su cuenta el ciclo red-green-refactor y la integridad de tests, que `superpowers:test-driven-development` ya cubre; esa prosa duplicada se desincroniza (superpowers lo mantiene un tercero, va por la 6.2.0). Ahora el implementador **invoca** esa skill y en `slice-runner` viven solo los deltas: exención por capa, integridad de tests **preexistentes**, refactor tras cada verde, y el esfuerzo en la calidad del test. Como su Iron Law ("no production code without a failing test") contradice la exención de capa, se declara la precedencia explícita **convenciones del repo > exención de capa > Iron Law** (sin eso, `selective-hearing`: gana la regla que más suena en el entrenamiento). Se añade el principio **"los tests son ciudadanos de primera categoría"**, que cita los checks de severidad alta del verificador en vez de repetirlos. Fuera de alcance: `verification-before-completion` (los controles ya son deterministas con exit code autoritativo; añadir su prosa no cambiaria comportamiento). **Contraparte en `slice-spec`**: el principio solo tiene dientes si el AC es refutable, así que `validate` pasa de comprobar que los AC **existen** a exigir que sean **falsables** (misma vara que `writing-good-tests.md`: nombra el cambio de producción que haría fallar el AC); un AC vago tumbaba el mapeo AC↔test en origen.
- **Verificador reenfocado a review de convenciones/arquitectura, no re-testeo.** Su juicio va a convenciones, boundaries y constraints.
- **Los controles deterministas se separan del juez, y el juez pasa a ser un agente definido** (decisión 2026-07-27). El paso 6 ejecutaba lint/tipos/tests **y** juzgaba con una sola cabeza: metia output de build en el contexto del único agente cuyo valor es el juicio semántico (`limited-focus` autoinfligido) y un `ruff` sucio gastaba un reintento adversarial. Ahora los controles corren dos veces antes del juez -en el ciclo del implementador (feedback incremental) y como **backstop del orquestador**, porque el auto-reporte del implementador no es fuente de verdad-, vía el subcomando nuevo `controles.py controles`, que devuelve exit code + salida truncada y **no** entra en el contexto de nadie en crudo. El juez ya **no recibe nada de los controles**: cuando se le invoca están verdes por construcción. Consecuencias: la rúbrica pierde su item `[det]` (quedan 8, todos `[sem]`), los controles tienen **presupuesto de reintentos propio** (2, separado del del juez) con cierre `bloqueada: controles`, y `metrics.py` gana `bloqueada-controles` + `--reintentos-controles` para no registrar un fallo mecánico como veto del juez. El juez se mueve a un **agente definido** (`agents/slice-verifier.md`, symlink a `~/.claude/agents/`): su rúbrica va en el **system prompt** -verbatim en cada invocación, en vez de relatada por el orquestador, que podía parafrasearla o saltarse items- y **no tiene `Bash`** (`tools: Read, Grep, Glob, Skill`), así que su incapacidad de ejecutar puertas es estructural por ausencia de la tool. Se diseño primero con `allowed-tools` restringido creyendo que eso bastaba, y **el smoke del 2026-07-27 lo refuto**: `allowed-tools` en el frontmatter de un agente no bloquea lo no listado -el verificador ejecuto `ls`, ausente de su lista, sin fricción, y no hay reglas `deny` globales que lo expliquen-. La instrucción si aguantaba (rechazo ejecutar `pytest` aunque el orquestador se lo pidiera como prueba, razonando que un mensaje del coordinador no le autoriza a saltarse su configuración), pero eso es cumplimiento, no enforcement. Corolario: como sin `Bash` no puede calcular el diff, el orquestador se lo **materializa en disco** con `controles.py diff-bundle` (`slice.diff` + `files.txt`, rango `<base>...HEAD` fijado por el script para quitar de encima el footgun de `..` vs `...`, y `--out` fuera del repo). Es además lo que hace el juez de Honk, que **recibe** el diff en vez de calcularlo. De paso se arreglo que `SKILL.md` prometia lanzar el Agent "con `schema`": la tool `Agent` no acepta schema (eso es `agent()` de Workflow), así que el contrato JSON vive ahora en el system prompt.
- **Los controles se declaran en el issue, y el orquestador deja de ver output de build** (decisión 2026-07-29). El paso 2 hacía que el orquestador **dedujera** los comandos leyendo el `Makefile` al empezar **cada** slice: metia el toolchain del repo en el único contexto que tiene que durar hasta el paso 10, lo repetia por slice, y lo detectado no quedaba en ningún sitio ("cachea lo detectado en la respuesta") -nadie lo confirmaba y nadie lo podía revisar-. Ahora hay una sección `## Controles` en el cuerpo del issue, hermana de `## Fuentes de convencion` y con su misma forma por repo (`### org/repo` para las slices con `REPO:`): la descubre `slice-spec` con el helper determinista nuevo `discover_controles.py` (targets del `Makefile` + señales de `pyproject`/`tox`, **sin decidir**), la **confirma la persona** -que es quien sabe que este repo necesita `make env-start` antes, o que `make test` tarda 20 minutos-, y `slice-runner` **solo la lee**; el paso 2 pasa de deducir a leer y es fail-closed como las fuentes. Se descarto que la descubriera el **implementador** (contexto desechable, coste cero) porque el orquestador la necesita igualmente para el backstop del paso 6, y recibirla de el significa que **el juzgado define la vara con la que se le juzga**: basta `compliance-bias` para acabar midiendose con `make test-unit`. Segunda mitad de la decisión: el backstop **se mantiene** -lo que no vale del paso 5 no es su ejecución, que es el mismo script y el mismo exit code, sino el **canal**: el orquestador no ve las tool calls del subagente, solo su mensaje final en prosa- pero deja de costar contexto, porque `controles.py controles --out` escribe el log entero a disco y devuelve `veredicto + ruta`: el orquestador reenvia rutas sin leerlas y el implementador recibe el error completo en vez de 30 líneas truncadas. De paso, **"puerta" pasa a llamarse "control"** en prosa y en código (`gates.py` -> `controles.py`, subcomando `checks` -> `controles`, `--check` -> `--control`, clave JSON `gate` -> `control`): era un calco de *gate*, y en castellano la idea de "sitio donde te paran si no cumples" es un control; se descartaron `verificacion` (colisiona con el paso 7), `prueba` (son los tests) y `vara` (son las convenciones). Los dos rastros del nombre viejo que viven **fuera** del repo -el marcador `bloqueada: puertas` escrito en issues abiertos y el `bloqueada-puertas`/`reintentos_puertas` del log durable de metricas- se siguen leyendo y se normalizan al agregar; renombrar no puede borrar histórico. **Deriva**: si alguien renombra un target después de crear el issue no hay pre-flight, el control falla como cualquier otro y la slice acaba `bloqueada: controles`; se acepto el coste (quema una slice) a cambio de no añadir heuristica, y `slice-spec validate` es donde se caza.
- **El verificador juzga el índice, y el verde de la CI hay que demostrarlo** (decisión 2026-07-30, la primera que sale de **correr** el loop y no de diseñarlo). El primer smoke real (issue #3, PR #4) recorrió el flujo entero y paso los diez criterios de `smoke/README.md`, pero destapó dos defectos del tramo final que ningún test offline podía ver, porque los dos son sobre **estado de git** y sobre la **forma de una invocación externa**. **Uno bloqueante**: `diff-bundle` (paso 7) calculaba `git diff <base>...HEAD` -solo lo commiteado- pero el commit estaba en el paso 8, **después**, mientras `pr-hygiene` necesita el índice **staged y sin commitear**; en el orden documentado los dos no pueden estar satisfechos a la vez, y el paso 7 devolvía "sin cambios" con la slice implementada y verde. Arreglo: `diff-bundle` pasa a `git diff --cached --merge-base <base>` y el commit se mueve **detrás** del veredicto, con lo que un FALLA no deja rastro que deshacer y la slice sigue siendo un solo commit **sin `--amend`** (que era el precio de la alternativa barata de solo reordenar la prosa). Sin flag a propósito: un `--staged` opcional reintroduce el juicio del agente donde la docstring presume de haberselo quitado, y olvidarlo devuelve el diff vacío, o sea el mismo fallo. Tres cosas se verificaron en un playground aislado antes de decidir: `git diff --cached base...HEAD` **no es sintaxis valida** (los tres puntos no valen con `--cached`), `--merge-base` es su equivalente y conserva la razón de ser del rango -que el avance de la base no salga como borrados-, y un fichero **untracked es invisible** al diff del índice. Eso último mató la alternativa de diffear el árbol de trabajo (un test nuevo, el caso normal, sería invisible al verificador) y dio la propiedad que no se había visto: **`pr-hygiene` pasa a dar integridad al input del verificador**, porque es lo que afirma que el conjunto staged es igual a la lista que declaró el implementador. **El otro defecto es silencioso**: el paso 9 decía "cada tick consulta `gh pr checks --json`" sin fijar los campos, y ese subcomando **no tiene campo `conclusion`** aunque `gh run list --json` y `statusCheckRollup` si -es la conjetura natural y la equivocada solo ahi-; en el smoke se pidió y la respuesta de error se leyó como "sin checks aun" durante **doce ticks, cuatro minutos, con la CI verde desde el segundo 14**. No revienta: **degrada a "nunca verde"** y se come el timeout, que en Nivel 2 con `/loop` es una slice colgada sin causa visible. Fiarse del exit code pelado no basta (`gh` devuelve 1 tanto con CI roja como con invocación invalida, así que el bug pasaría a leerse como roja). Arreglo: subcomando `ci-status`, un tiro **sin `--watch` ni polling** -el ticking lo hace el harness, un script que poll-ea es la shell bloqueante que la skill prohibe-, que encapsula la invocación, los nombres de campo y el mapeo de exit codes, con la regla fail-closed de que **solo es verde un todo-pass explícito con al menos un check que haya corrido**; así no hace falta adivinar que hace `gh` ante una PR sin CI, y `sin-checks` no colapsa en verde (sería peor que colgarse: reportaria validada una PR sin CI). De ahi el motivo nuevo `bloqueada: ci-indeterminada`: reusar `ci-roja` mentiria en el registro duradero y dejarla en `esperando-merge` afirmaria un verde que no hubo. Al implementarlo se descubrió que **una de las propiedades afirmadas en la spec era falsa**: `git diff --cached <commit>` compara el índice contra ese commit, y tras commitear el índice sigue conteniendo lo commiteado, así que el control **funciona igual antes y después del commit** -más robusto que lo afirmado, y ese margen es lo que hace que reordenar el paso 8 no sea frágil-; el test que iba a fijar lo contrario se reescribió para fijar la equivalencia.
- **Los dos contadores del verificador no se mezclan** (decisión 2026-07-30, del segundo smoke). El verificador tenía presupuesto propio de 2 reintentos pero `metrics.py` **no tenía campo para registrarlos**: la calibración del juez estaba ciega justo donde importa. Al anadirlo apareció que no era un contador sino dos, porque hay dos motivos distintos de reinvocarlo: `FALLA` es un **rechazo semántico** (el juez veto código y se vuelve al paso 5) y devolver prosa en vez de su JSON es un **fallo mecánico del agente** (se reinvoca sin tocar código). Se separan en `--reintentos-verify` y `--descartes-verify` por el mismo argumento que ya separa `FALLA` de `bloqueada-controles` en este mismo fichero -"confundirlos deja inservible el único instrumento que hay para calibrar al juez"-: sumarlos haría que la indisciplina del agente se leyera como que el juez encuentra defectos. Un descarte **no** descalifica la slice como "primer intento", porque lo que se rehizo fue la respuesta del juez, no el código. Y `descartes_verify` se reporta como **tasa de slices**, no como media: la pregunta que responde es "en que fracción no aguanto el contrato de salida", que es una propiedad del agente y no de la slice. El motivo por el que esto se descubrió: el smoke 2 recibio prosa en la primera invocación y el **JSON pelado al reinvocar con el prompt idéntico**, así que el cumplimiento del contrato es **estocastico** -en el smoke 1 cumplió a la primera y parecia fiable- y la regla de reinvocar es lo único que lo sostiene, dado que la tool `Agent` no valida schemas.
- **Lo que es regla exacta pasa a script, sin excepciones** (decisión 2026-07-30, tras el segundo smoke). Dos huecos que quedaban a juicio del agente, los dos con el mismo modo de fallo: parecen funcionar hasta que fallan en silencio. (1) **La forma del veredicto del juez.** La regla de "si vuelve envuelto en prosa se reinvoca" cubria el caso obvio; el que no cubria es un JSON **estructuralmente plausible pero equivocado** -`"veredicto": "PASS"`, una `severidad` inventada, un hallazgo sin `evidencia`, o un `PASA` que convive con un hallazgo `alta`- que leido a ojo pasa por bueno porque parsea. Nuevo `controles.py verify-verdict`, que valida el esquema y **devuelve los conteos por severidad**, matando de paso otro juicio: antes el orquestador los contaba a mano para la metrica. Exit 1 = descartar y reinvocar (suma a `--descartes-verify`), exit 2 = el fichero no se pudo leer, o sea que el fallo es del orquestador y no del juez -distinguirlo evita reinvocar al agente por un despiste propio-. (2) **Las transiciones de estado en el issue.** `issue_body.py` era libreria pura sin CLI, así que cada transición la escribia el agente como `python3 -c` con `sys.path.insert` + `gh issue view` + la llamada + `gh issue edit`: en **una sola sesión se escribió seis veces**. El modo de fallo no es teórico: si `gh issue view` devuelve vacío y el `edit` va detrás, **borra la spec entera del issue**, que es la única fuente de verdad del run. Ahora hay CLI con `show` (lee el issue y emite slice elegida, fuentes y controles ya filtrados por repo, intención, y la `rama` y el `scope` ya derivados) y `set-estado` (read-modify-write completo, fail-closed ante cuerpo vacío). El nucleo sigue puro y es lo que se testea; la CLI es la capa de I/O, mismo patrón que `clasifica_ci`/`consulta_ci` en `controles.py` -por eso se actualizo la nota que decía que la I/O vivia solo en `gh`-. Al escribir sus tests apareció un gap de paso: `set_slice_estado` **no valida el motivo**, así que `MotivoBloqueada` seguia siendo un vocabulario inerte para la escritura y un `bloqueada: inventado` acababa en el registro duradero, donde ya no se renombra (paso con `puertas`). La validación vive en la CLI, que es la frontera de escritura y el único sitio con un exit code que la haga cumplir; `abortada` se deja libre a propósito porque su vocabulario aun no esta canonicalizado y fijarlo ahi sería decidirlo de tapadillo.
- **El implementador pasa a agente definido y el relato sale del `SKILL.md`** (decisión 2026-07-31, fase 1 del coste de contexto). El README prometia contexto limpio por slice y en la práctica no se podian correr todas las slices de una feature en una sesión: había que compactar a mitad del run, y a partir de ahi el orquestador decidia con el contexto mutilado -el fallo que este repo existe para evitar-. La promesa era cierta **solo de los subagentes**; el orquestador vive en la sesión de la persona, y `/loop` reinyecta el prompt en la **misma** conversación, así que el nivel donde más se prometia es donde menos se cumplia. Medido, el coste por slice era: `SKILL.md` 8.500 palabras (~13k tokens) recargadas por invocación, el prompt del implementador redactado entero por el paso 5 (metodologia incluida, y otra vez por reintento), los ticks de CI y de merge, y `deploy-watch` encadenado en la misma sesión. Dos palancas de cuatro: (1) **el implementador pasa a agente definido** (`agents/slice-implementer.md`), con la metodologia -ciclo TDD, los cinco deltas, auto-check de wiring, controles verdes- en su system prompt en vez de relatada; el paso 5 se queda con los datos del run. No rompe la razón vieja de que fuera `general-purpose`: lo que ese párrafo rechazaba era un agente **prestado**, y uno propio con `model: inherit` y `Bash` conserva las tres propiedades que pedia, añadiendo la que ya justifico mover al verificador (la metodologia no se puede parafrasear ni saltar items). (2) **el relato largo sale del `SKILL.md` a un fichero de referencia propio de la skill** (más tarde retirado junto con el resto de la prosa del runner) -no a `docs/design-notes.md`, porque el symlink de instalación apunta al directorio de la skill y desde otro repo `docs/` no existe-, con criterio de corte explícito: se queda la regla y su por que **en una frase**, se va el relato (que smoke lo descubrió, alternativas descartadas, creencias refutadas). El objetivo era <=4.500 palabras y **se quedó en ~5.840**: al llegar ahi lo que restaba ya era regla o por que de una frase, y bajar más exigia borrar reglas para cumplir una cifra estimada antes de hacer el trabajo. Se dejó el número real declarado en vez de recortar reglas. Descartadas: **desencadenar `deploy-watch`** del paso 10 (~6-10k tokens, la palanca más grande) por decisión del usuario, que prefiere conservar el encadenado automático, y **`Monitor` en vez de N ticks** por ahorro escaso.
- **El indeterminado de la CI tiene ventana de gracia, y no se reclasifica** (decisión 2026-07-31, medida en dos PRs de este repo). `bloqueada: ci-indeterminada` (decisión del 2026-07-30, arriba) acerto el **diagnóstico** y se equivoco en **cuando creerselo**: el paso 9 cerraba con el primer `sin-checks`/`desconocido`. Medido: en la **PR #31**, a segundos de crearla, `ci-status` devolvio `desconocido` con exit 4 -hallazgos "respuesta de gh no parseable: (respuesta vacía)" y "no checks reported on the ... branch"- y **veinte segundos después** `verde` con el check `check` en `pass`; en la **PR #20**, en cambio, el mismo `desconocido` era real y permanente (cuatro ticks), porque entonces ningún workflow aplicaba a esa PR. O sea que el mismo estado significa cosas opuestas según el momento, y cerrar en el tick 1 registra como no medible una slice sana -con nadie mirando que lo compense, porque bajo `/loop` el orquestador ya no está en una sesión supervisada-. Arreglo: **ventana de gracia con el número escrito, 10 ticks indeterminados consecutivos y 30 s o más entre tick y tick**, que deja pasar el caso de la #31 (resuelto en el tick 2) y sigue cerrando el de la #20; **subida de 3 ticks a 10 el 2026-08-13**, porque 3 son 90 segundos y eso no es una ventana de gracia sino una carrera contra la cola de GitHub Actions: 10 ticks son 5 minutos, que es lo que se tarda en distinguir 'no hay CI' de 'la CI todavía no ha arrancado'. **Y el número no es lo único que fallaba ahi**: la PR #221 de este repo cerró `bloqueada: ci-indeterminada` a los 70 segundos de abrirse y **ninguna ventana la habría salvado**, porque su CI no iba a arrancar nunca -tenía un conflicto con `master`, y GitHub Actions no ejecuta un workflow de `pull_request` sobre una pull request inmergeable: el evento corre sobre el merge commit (`refs/pull/N/merge`), que con conflicto no se puede construir-. O sea que `ci-indeterminada` esta fundiendo dos causas que se arreglan en sitios distintos: **'los checks todavía no han llegado'** -que es lo que la ventana espera- y **'esta pull request no se puede mergear'**, que ninguna espera resuelve y que `gh pr view --json mergeable` dice sin ambiguedad. Distinguirlas es trabajo pendiente, y hasta que se haga el diagnóstico manda a mirar al sitio equivocado; la separación mínima no es decoración, sin ella tres ticks seguidos son tres segundos y la ventana no cubre nada. Descartada la alternativa barata de **reclasificar `desconocido` a `pendiente`**: ese estado significa "hay checks corriendo" y tickea hasta el timeout, así que una PR sin CI pasaría de cerrar con un motivo exacto a colgarse cuatro minutos sin causa visible, que es justo el fallo que `ci-indeterminada` vino a arreglar. Lo que cambia es **cuanto se espera antes de creerse el diagnóstico**, no el diagnóstico: agotada la ventana el cierre es el mismo fail-closed de antes (ni verde, ni reintento de la slice, PR abierto, `bloqueada: ci-indeterminada` + metrica `ci=none`). El número **se quedó en prosa** en su día, contra la regla de que lo que es regla exacta pasa a script, y no por comodidad: la ventana es una cuenta **entre** invocaciones, y `ci-status` es de un tiro y sin estado a propósito -un script que poll-ee es la shell bloqueante que la skill prohibe, y persistir la cuenta exigiria el estado local que se elimino en 2026-07-23-, mientras que la parte que fallaba en silencio (clasificar) si estaba offloadeada: el exit 4 dice "indeterminado" sin ambiguedad y nunca colapsa en verde. **Eso caduco cuando el orquestador paso a ser un programa**: la cuenta entre invocaciones tiene donde vivir (`Budgets` en `src/slice_runner/domain/budgets.py`, que es también donde viven los otros presupuestos del loop), la decide una función pura, y las copias que siguen en prosa -la docstring de `controles.py`, que es donde se mira al dudar de la invocación, este párrafo y el `README.md`- **si las compara un control** (`tests/test_skill_contracts.py`), así que mover el número ya no es moverlas a mano una por una sin red. `ci-status` sigue sin estado.
- **Que hacer con un hallazgo que no bloquea, decidido por regla** (decisión 2026-07-31, clasificando seis decisiones reales del mismo día). El paso 7 declaraba que `media`/`baja` **no bloquean** y no decía nada más, así que que hacer con ellos lo improvisaba el orquestador: en una sola jornada el mismo tipo de hallazgo recibio **tres tratos distintos** -reintento, deuda declarada, y reintento hasta agotar el presupuesto-. En Nivel 1 lo compensa la persona que esta mirando; en Nivel 2 la varianza se hereda sin testigo, que es el motivo de arreglarlo ahora. Las seis decisiones: (1) un `README` que seguia afirmando de todas sus recetas lo que tras la slice solo valia para tres; (2) una docstring de módulo que decía que el exit 4 significa "para" cuando el paso 9 acababa de pasar a "cuenta un tick"; (3) `docs/design-notes.md`, declarado registro completo, sin la decisión que la slice tomaba; (4) un paso de receta que justificaba un precheck con un argumento que el comando no sostiene -reintento los cuatro-; (5) una docstring citando un número de paso desfasado, defecto **preexistente**; (6) un párrafo sin re-envolver, una frase redundante y una errata gramatical -deuda los dos-. Se probo primero el eje obvio, **la severidad**, y **no separa los casos**: 1-3 son `media` y 4 es `baja` con el mismo trato, mientras 5 y 6 son `baja` con el trato opuesto. El eje que si los separa es **si el árbol queda incumpliendo la vara** (1-4) frente a **mejorable pero conforme** (5-6), con el matiz del 5: el incumplimiento era preexistente y el diff solo lo heredaba. De ahi las dos preguntas del paso 7 -¿deja el árbol incumpliendo la vara? y ¿esta alguna de las dos partes en el diff de esta slice?- y de ahi que la primera exija **citar las dos partes**: es lo que la hace comprobable, porque un incumplimiento tiene dos lados y una preferencia solo uno. Los seis casos eran **todos de prosa**, así que la pregunta 1 nombra explicitamente las **dos formas** del mismo eje -afirmación falsa en documentación, violación de convención citable con regla + path en código-: redactada solo como "afirmar algo falso", un hallazgo sobre código la responde "no" por construcción y la clase entera caeria en deuda automática, incluido el ejemplo que `agents/slice-verifier.md` ya califica de `media` (label de metrica con identificador de alta cardinalidad). Y **la cita la construye el orquestador**: el veredicto trae un solo `path` por hallazgo y el juez solo esta obligado a evidencia citable en `alta`, así que clasificar según lo que entregue en `media`/`baja` dependeria de algo que su contrato no promete -el otro lado se busca en el árbol o en las fuentes de convención, y si no aparece, es preferencia y va a deuda-. No cambia nada de lo que ya estaba: solo `alta` bloquea, el presupuesto sigue siendo 2, y la vuelta al paso 5 por un hallazgo no bloqueante gasta **ese mismo** presupuesto -por eso `--reintentos-verify` se redefine como "rondas de vuelta al paso 5 que decide el juez" en vez de "rondas por `FALLA`": sigue siendo rechazo semántico, que es la frontera que ese contador protege frente a `--descartes-verify`-. Consecuencia obligada de no tocar el presupuesto: la regla dice también que al agotarlo los hallazgos no bloqueantes pendientes **pasan a deuda**, porque bloquear la slice por ellos contradiria que no bloquean. Y la deuda aceptada se escribe en el **cuerpo de la PR** (paso 8, sección `## Deuda aceptada`, solo si la hay): el chat se tira, el issue lleva la spec y no la revisión, y el cuerpo de la PR es lo que se sigue leyendo junto al código cuando alguien se pregunte por que esa línea sigue así.
- **test-desiderata** en el verificador: bloquea solo lo grave (no determinista, no aislado, test que no verifica comportamiento); lo menor informa. Se salta en slices sin tests. Cubre **solo los tests nuevos**: un test preexistente degradado es del item de manipulación-tests y ya está contado ahi (el smoke del 2026-07-27 mostro los dos agentes contando el mismo assert relajado dos veces como `alta`, inflando el recuento por severidad que alimenta las metricas). Regla general añadida al veredicto: **un defecto, un hallazgo**, bajo la regla más específica.
- **El verificador no audita el historial de commits.** La rúbrica pedia que el test "precediera a la implementación", y eso es inverificable por diseño en este flujo: `slice-runner` entrega la slice en **un solo commit**, así que el historial nunca puede acreditarlo. En el smoke del 2026-07-27 los tres agentes reportaron "no puedo constatarlo", o sea un hallazgo de ruido garantizado en **todas** las slices, que erosiona la señal del resto de la rúbrica. El item pasa a llamarse **cobertura por capa** y solo comprueba que exista un test por AC (o "suite intacta + efecto verificado" en capas eximidas); el ciclo red-green lo garantiza en origen el implementador vía `superpowers:test-driven-development`, con su "watch it fail" obligatorio.
- **Refactor tras cada verde** en el implementador.
- **No hace merge.** Para en "PR abierto + CI verde". Merge humano.
- **Fail-closed si el entorno veta los subagentes** (decisión 2026-07-28). Descubierto en caliente: una sesión real de `deploy-watch` en otro repo se encontró con una instrucción global de "no uses el Agent tool salvo que el usuario lo pida" y, al no poder lanzar los colectores, avisó y recogio las señales inline. La instrucción no está en ningún fichero local -descartados `CLAUDE.md` (global, de proyecto y de padres), `settings.json`, `managed-settings.json`, output-styles, `~/.claude.json`, memoria, `~/.orca`, el estado de la app y los argumentos de proceso-, así que viene con el system prompt desde el servidor: cuenta u organización. **Por que salto entonces y no antes**: `deploy-watch` solo necesitaba un subagente ante anomalia (el `sre`, desde el commit inicial) hasta que `ca55675` (2026-07-24) metio colectores **por tick**; y sobre todo, esa fue la primera ejecución real de una de estas skills sobre trabajo de verdad -aquí llevamos la semana construyendolas, no corriendolas-. `slice-runner` tenía la misma bomba sin detonar desde el commit inicial, y peor: sus dos subagentes no son condicionales. Decisión: **un criterio, no dos reglas.** El primer intento hardcodeo una respuesta por skill ("el runner para, el watcher degrada"), y eso obligaba a que cada skill futura copiara la que más se le pareciera. El criterio que las genera es: **¿se puede declarar la degradación en el artefacto que la skill produce?** Si si, degrada y declaralo **ahi** -declararlo no es cortesia, es la condición que autoriza a degradar-; si el artefacto entero significa justo la garantía perdida, **para**, porque producirlo sería afirmar algo falso sin que nadie aguas abajo pueda verlo. El criterio y la excepción de que **invocar una skill cuenta como pedir sus subagentes** viven **en cada skill**, no centralizados. Hubo un intento de ponerlos en `~/.claude/CLAUDE.md` -que tiene la ventaja de pesar lo mismo que el veto, al ser también instrucción de usuario, mientras que una skill declarando la excepción reduce la varianza pero no tiene ese rango- y se **revirtio por decisión del usuario**: era un principio load-bearing en un fichero **sin versionar y fuera del repo**, contra la premisa de que este repo es la fuente de verdad, y con blast radius sobre todos sus proyectos y maquinas. Se acepta a cambio la duplicación del criterio en las dos skills: cuatro líneas repetidas, pero versionadas y autocontenidas. De ahi salen las dos respuestas: `slice-runner` **para** en el paso 3 con `bloqueada: sin-subagentes`, sin escribir código, porque su artefacto es una PR cuyo veredicto PASA *es* la afirmación de haberse verificado -degradado sería falso y **falso de forma invisible**, ya que quien revise asume que paso el pipeline- y parar no cuesta nada irreversible; `deploy-watch` **degrada declarandolo** al arrancar y en el informe final, porque su veredicto puede decir como se obtuvo y además lo calcula `deploy_core.py`, no la impresión del agente, así que la afirmación sigue siendo verdadera. Cada skill cita a la otra como "mismo criterio, artefacto distinto", para que nadie lea la asimetría como incoherencia y la "arregle" hacía el lado fácil (degradar las dos), que es el que mata la garantía. Las conclusiones (parar / degradar) se escriben también en cada skill, no solo el puntero: una skill debe comportarse bien aunque el criterio general no este cargado; lo centralizado es la **derivación**, no el resultado. No se registra metrica: el issue es el registro de estado y `metrics.jsonl` es telemetria de slices **ejecutadas**; una que nunca arranco no dice nada de la calidad del loop.
- **Contexto fresco por slice, con una asimetría que hay que decir en voz alta** (patrón Ralph; corregido el 2026-07-31). Los **subagentes** si arrancan limpios y mueren al terminar, y por eso todo lo caro vive en ellos. El **orquestador no**: vive en la sesión de la persona y acumula el run entero. Lo que persiste y se re-lee es el **issue de GitHub** (spec + estado), y eso es lo que hace seguro el Nivel 2 -no que el contexto se limpie solo-: como no queda estado en la sesión, se puede tirar y abrir otra entre slices. `/loop` **no** limpia contexto: reinyecta el prompt en la misma conversación a propósito. Afirmar lo contrario era la clase de promesa que se cumple hasta que alguien la usa en serio.
- **Estado del run en el issue de GitHub** (decisión 2026-07-23): la spec y el estado de cada slice viven en el cuerpo de un issue (1 feature = 1 issue), única fuente de verdad viva y duradera. Sustituye al estado local anterior (`.slice-runner/` con `runs.jsonl`/`state.json`/`stream.log` + un panel TUI), que se **elimino**: el seguimiento pasa a ser público y colaborativo, sin infra local. `slice-runner` reescribe la línea de la slice en cada transición (lógica pura en `scripts/issue_body.py`, I/O en `gh`); `deploy-watch` comenta su veredicto.
- **Metricas durables fuera del repo**: `~/.claude/slice-runner/metrics.jsonl` (append-only, no versionado, sobrevive al descarte) para medir "cuando subir de nivel". Lo escribe el programa el mismo (`LocalMetricsLog`); `scripts/metrics.py` solo lo agrega.
- **Coste**: presupuesto de tokens/$ por slice como circuit breaker adicional; metrica = coste por slice mergeada (no por intentada). Motivado por el research (coste hasta 30x impredecible, Stanford). El coste vive en las metricas durables (`~/.claude/slice-runner/metrics.jsonl`), fuera del repo.

### Por que estas decisiones (fuentes)

- **Loop engineering** (Boris Cherny, Addy Osmani, LangChain): assess-act-verify-stop, worktrees para aislar, estado fuera del contexto, escritor != verificador, controles de parada objetivos, circuit breaker.
  - https://addyosmani.com/blog/loop-engineering/
  - https://www.langchain.com/blog/the-art-of-loop-engineering
- **ai-patterns** (Lada Kesseler et al.): check-alignment (evita silent-misalignment), reference-docs (cargar convenciones on-demand), offload-deterministic (make/gh en vez de juicio del modelo), context-markers (el testigo `[slice-runner]`), feedback-flip / focused-agent (verificador adversarial), reminders (lista de no negociables).
- **Bryan Finster, "Agentic Workflows: Do Agents Work?"** (empirico, 5 experimentos con coste medido):
  - Small batches ganan; requisitos claros son innegociables (valida check-alignment).
  - **Refactor tras cada verde** es el driver de calidad, no el orden test-first -> por eso se añadió como paso explícito.
  - Test-first no aporta medible en agentes -> ANOTADO, pero se mantiene TDD estricto porque el `CLAUDE.md` del repo lo manda (gana la convención). Revisable si el repo cambia.
  - Split authorship costó 3x sin ganancia consistente porque los AC ocultos ya gobernaban -> por eso el verificador se reenfoca a convenciones/arquitectura (que Finster no midió) en vez de re-testear.
  - No sobre-testear (mutation scores altos en los peores workflows) -> respalda test-desiderata "bloquea solo lo grave".
  - https://bryanfinster.substack.com/p/agentic-workflows-do-agents-work
- **Honk (Spotify), serie de 4 partes sobre su agente de background** (1.500+ PRs mergeadas en producción):
  - Los verificadores deterministas **no se exponen al agente** uno a uno: una sola tool `verify`, activada por contenido del componente, que parsea su propia salida y devuelve solo lo relevante. El agente "no necesita entender los detalles de invocar distintos build systems" -> es el argumento de `controles.py controles`.
  - Corren **en cada turno** y otra vez **antes de abrir la PR**, esto último vía **stop hook**: la garantía la da el harness, no el agente -> nuestro equivalente es el backstop del orquestador (una skill no debe instalar hooks globales).
  - El **juez LLM** corre después de todos los verificadores y recibe **el diff y el prompt original, nada más** -> por eso el nuestro no recibe nada de los controles.
  - Veta **~25%** de miles de sesiones y el agente corrige la trayectoria **la mitad** de las veces: es la tasa de calibración que nuestras metricas todavía no saben medir (solo registran el veredicto terminal por slice).
  - **No copiado a propósito**: su parseo por regex es *por build system* sobre un toolchain que ellos controlan y estandarizan; nosotros autodetectamos `make`/`pyproject` en repos ajenos, donde un regex que no matchea **oculta el error real**. Se transfiere el patrón, no la implementación.
  - Su parte 4 confirma el punto ciego que nos queda: donde no había testing automatizado (dbt, BigQuery Runner) **no pudieron verificar** y los equipos dueños tuvieron que testear a mano -> nuestro equivalente son las slices con exención de capa, donde el juez no cubre el modo de fallo "pasa CI pero es incorrecto".
  - https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3

### Ideas para iterar (no construidas)

- Chequeo de independencia entre slices (solape de ficheros/migraciones) para habilitar paralelo seguro.
- Nivel 3 con Workflow fan-out: N implementadores en worktrees, aislamiento de entorno de test por worktree (COMPOSE_PROJECT_NAME/puertos), estrategia de orden de merge (serializar quien toque alembic).
- Convención para archivar/marcar planes ya entregados y que el selector de "siguiente slice" no tropiece con specs stale.

## Como se escribe una convención (lo que se midió)

La regla vive en `docs/conventions/como-se-escribe.md`. Lo que la sostiene se midió en un playground
-un mini-repo con la misma arquitectura, cinco repeticiones por variante-, porque la discusión llevaba
rato siendo de intuiciones:

- **El molde no mejora el acierto; ahorra el descubrimiento.** Con la regla del puerto que solo consume
  la infraestructura, y el precedente del árbol jugando en contra, **las tres formas de darla acertaron
  5/5**: regla sola, regla con puntero al fichero real, y regla con molde embebido. Lo que cambio fue el
  trabajo: **5 turnos con molde frente a 19 sin el**. De ahi que el molde se ponga donde el caso es
  frecuente y no en todas las reglas.
- **El volumen no rompe el cumplimiento.** La misma regla enterrada entre otras ~280 líneas siguió
  acertando 5/5. Por eso partir un documento **no** se justifica por su tamano; se justifica por poder
  cargar un tema sin llevarse los otros, que es otra cosa.
- **El censo es lo que se cobra.** Con una convención que contaba los miembros de un enum y la tarea de
  añadir uno, la convención quedó mintiendo en **1 de 5** intentos. Pedir explicitamente que se
  actualice lo arregla (5/5), pero el dato que decidió el diseño es otro: **con censo, el implementador
  edita `docs/conventions/` en 4 y 5 de cada 5 intentos; sin censo, en 0**. Su propio brief le dice que
  no tiene autoridad para cambiar la vara con la que se le mide, así que una convención que le obliga a
  tocarla ha dejado de ser vara. Con cinco repeticiones la diferencia 4/5 frente a 5/5 no es
  concluyente; la de la última columna, si.

El origen: de 38 hallazgos bloqueantes o medios del dogfooding, **seis eran prosa caducada** -conteos y
listas cerradas que la propia slice invalidaba-, y `infrastructure.md` concentraba 10 de los 18 de
severidad alta.

## Comparar la vara con la de otro repo (lo que se midió)

2026-08-17, contra las convenciones de otro repo propio con la misma arquitectura hexagonal, pero Django
y un contenedor de inyección. Lo que salió:

- **La vara de aquí mide casi el doble.** Sumando los ficheros de capa comparables, 33.325 caracteres
  allí frente a 61.870 aquí, ya recortados. `docs/conventions/infrastructure.md` **sola** es tres cuartos
  de toda la vara del otro repo.
- **Allí se ensena con ejemplo y aquí con prosa**: 29 bloques de código frente a 6 moldes. Cada forma paga
  algo distinto -un ejemplo puede envejecer sin que nada avise; la prosa hace que el motivo compita con la
  regla por la atención-.
- **El otro repo no tiene meta-vara y su vara esta igual de limpia de censo**: una sola ruta real citada,
  cero conteos de miembros del código. Dato incomodo y útil: allí la limpieza no vino de una regla
  escrita, vino de que la vara nació con moldes en vez de con inventario.
- **La regla del estado ausente como miembro del vocabulario se trajo de allí.** Aquí el antipatrón ya
  prohibia `Optional[Enum]` pero no decía con que se sustituye, así que prohibia sin ofrecer.

Y la deriva del código contra la vara de aquí, medida a la vez:

- **Un `| None` que carga dos significados**, pendiente de arreglar: en
  `src/slice_runner/application/queries/read_ci_status.py`, el mismo vacío dice "esto no es indeterminado"
  y "es indeterminado y la propia herramienta no sabia por que". Falta un miembro que diga que la
  herramienta contesto que no sabe. Encima, ese campo y el resultado son dos que tienen que concordar, o
  sea la regla de `docs/conventions/infrastructure.md` incumplida en el mismo sitio.
- **De los puertos del programa, exactamente uno no compra nada**: una implementación, un consumidor de su
  misma capa, y cero sustituciones en todo el árbol de test -el test de su único consumidor inyecta la
  implementación de verdad-. Los demas están doblados o los consume aplicación, así que el reparto en
  muchos ficheros **no** lo explican abstracciones muertas.
- **Lo que si explica el número de ficheros es la regla que contaba clases**, que es la que se reescribió
  para preguntar por la dependencia en vez de contar tipos.

## El worktree del programa (lo que se midió)

2026-08-19, al decidir que el worktree deja de ser una cadena que alguien teclea y pasa a montarlo el
programa. Las mediciones son lo caro de esta decisión: la mitad no se puede deducir leyendo código.

**Un worktree bajo la raíz del repo tiene tres condiciones, y las tres están medidas.**

- **Bajo la raíz, o Docker no lo ve.** Cuando los controles corren en contenedor, el compose monta la raíz
  y el worktree solo existe dentro si cuelga de ella. Medido en los logs de otra persona: sus tests
  reportan `rootdir: /app/.claude/worktrees/<slice>/src`, o sea la raíz montada en `/app` y el worktree
  dentro. Un worktree hermano fuera del repo no estaria montado y los controles no podrían correr.
- **Con punto delante, o los controles se lo comen.** `pytest` y `ruff` **no** recursan dentro de un
  directorio oculto y **si** dentro de uno visible. Probado con un árbol de juguete: de dos copias del
  mismo test, la de `visible/` se recogio y la de `.hidden/` no. Sin el punto, `make test` desde la raíz
  mediria también las copias de cada worktree.
- **Ignorado, porque git no lo hace solo.** Un worktree anidado sale como `?? .wt/` en el
  `git status` del clon principal. La casa de esa regla es `.git/info/exclude`, que es por clon y no se
  versiona, así que no obliga a tocar el `.gitignore` de nadie.

**La clasificación sale del porcelain, nunca de un mensaje de error, porque git traduce.** Con locale
español el mismo fallo dice `fatal: '.w/uno' ya existe` y con `LC_ALL=C` dice `already exists`. Y los
cuatro fallos posibles salen todos con el mismo código, y dos de ellos con el mismo texto, así que el
código no clasifica y el texto no es fiable: quien decide es `git worktree list --porcelain`, que es
legible por maquina, trae la rama con su prefijo `refs/heads/` y lista **también el clon principal**, que
es worktree de si mismo.

**Que el paso falle no crea un callejon: cierra dos que ya existian.** Hoy la primera invocación exige que
la rama **no** exista -precheck de rama existente- y la reanudación exige que **si** exista
-`MissingBranchError`-, y las dos paredes se arreglan a mano y se repiten en cada invocación. Con la ruta y
la rama derivadas las dos de la identidad de la slice, encontrarlas ya hechas es **prueba de que son de
esta slice**: nadie más genera ese par. Solo quedan ambiguos el worktree en otra rama y la ruta ocupada por
otra cosa, y ahi el mensaje de git trae la ruta del conflicto para poder decirla.

**A los prompts no les faltaba información.** Medido sobre 735 comandos de shell del implementador en dos
días de otra persona, **el 93% no lleva un `cd` previo**: el agente confia en su directorio de trabajo y
opera en relativo. Decirle que está en un worktree sería gastar atención en lo que ya descubre. Lo que
faltaba no era texto: era que el programa fuese dueño del directorio.

## Por donde se le entrega una convención (lo que se midió)

La pregunta era si las convenciones rinden más como `.md` que el implementador tiene que leer, o
inyectadas en el prompt, o dentro de una skill. Se midió con el arnés de `playground/` -tarea fija de
siete ficheros, cinco repeticiones, quince reglas comprobadas sobre el árbol resultante con el árbol
sintactico- y **las mismas 565 líneas** entregadas por cuatro canales: ninguno (control), puntero al
fichero, texto integro en el prompt, y skill del repo.

- **El canal no cambia el cumplimiento: empate.** De las quince reglas, cuatro discriminan -dominio
  plano, nombres de test largos, usar mother, y no escribir tests unitarios de dominio-. En esas cuatro:
  puntero **20/20**, inyectado **20/20**, skill **19/20**. No hay razón de eficacia para preferir un
  canal, así que la elección se decide por coste de mantenimiento y por propiedad, no por rendimiento.
- **Lo que si pesa es que el documento llegue.** Sin ninguna convención, esas cuatro reglas caen a
  **0/5, 0/5, 0/5 y 1/5**. El documento no es decorativo; el canal por el que viaja, si.
- **Inyectar gasta menos turnos que apuntar, y es la única diferencia que aguanta.** Inyectado
  **19,6 turnos [18-21]** frente a puntero **24,0 [22-26]**: los rangos no se solapan, y son los `Read`
  que uno paga y el otro no. En dolares los cuatro rangos se solapan -0,68 / 0,89 / 0,80 / 0,74- así que
  con cinco repeticiones **no se puede afirmar** que ninguno sea más barato. El puntero es además el más
  lento (234 s frente a 168-183 s).
- **Once de las quince reglas se cumplen sin convenciones.** El suelo es alto: o el modelo ya las hace, o
  vienen del `CLAUDE.md` global de la maquina. El valor de una convención se concentra en las reglas
  **contraintuitivas**, y escribir las otras once no esta cambiando nada.
- **Sin convenciones se gastan más turnos, no menos** (31 frente a 20-24): el modelo se inventa más
  estructura -subcarpetas por tipo, tests de dominio- que luego hay que deshacer.

**Alcance de lo medido, para no estirarlo.** Es la semilla desnuda: un árbol sin código vecino. En
producción el código de alrededor ensena por imitación y el documento puede añadir menos, y eso lo
mediria la semilla poblada, que esta construida y sin correr. La tarea son siete ficheros, no los veinte
de una slice real.

**Y el coste real de medir no es el que se creia.** Cada llamada de este experimento salió a **0,75 $**,
así que una tanda de cuatro variantes por cinco repeticiones cuesta unos **15 $**, no los dos que se
venian citando. Sigue siendo barato frente a una slice -la más caro registrada, la slice-05 de #117, costó
**28 $** en 396 turnos- pero ya no es calderilla, y decide cuántas hipótesis se pueden permitir.

## El programa (`src/slice_runner/`)

Lo que sigue vivia dentro de `docs/conventions/`, mezclado con las reglas. Se movio aquí cuando
`docs/conventions/como-se-escribe.md` fijo que una convención dice la regla y no narra como se llegó a
ella: el relato no es vara de nada, y leerlo cada vez que se va a escribir código es contexto que no
mide. Las reglas que salen de estas decisiones siguen en su capa.

### De donde salen los números de `Budgets`

- **Los topes de espera de una invocación, que fueron uno solo hasta el 2026-08-13.** El de la
  integración continua sale de que la de este repo está medida entre 15 y 33 segundos sobre 25 runs, así
  que el número no lo fija ella: lo fija el repo destino peor, y hay uno escrito -un `make test` de ~20
  minutos, en `skills/slice-spec/SKILL.md`- que hay que despejar con margen. El de las esperas humanas
  -alineación y merge- sale de otra pregunta distinta: cuanto puede tardar una persona en estar delante
  sin que eso signifique que algo va mal, y ahi una jornada es lo razonable.

  **Fueron el mismo número, con un acumulador único para todo el run, y eso hacía que el último que
  esperaba pagase lo que gastaron los demas.** Medido en la slice-10 de este repo el 2026-08-13: 42
  ticks esperando el `-GO` y 2 la integración continua dejaron **16** para el merge -8 minutos de los
  30-, y el run murió en `WAIT_EXHAUSTED` con la pull request sana, verde y a punto de mergearse. Nada
  de eso se leia en el tope: decía 30 minutos y entregaba 8, con el reparto dependiendo de lo que una
  persona hubiera tardado antes. De ahi salen las dos mitades del arreglo -un tope por clase de espera,
  y el contador reiniciandose en cada paso-, cuya **regla** vive en `docs/conventions/domain.md`.

  La ventana de gracia de la CI indeterminada subió a la vez, y por su propio motivo: 3 ticks son 90
  segundos, que no es una ventana de gracia sino una carrera contra la cola de GitHub Actions.
- **El tope de una llamada a un proceso externo.** Lo más largo que se ha medido llamar son los sobres
  de `claude -p` de `src/slice_runner/tests/payloads/`, cuyo mayor tarda 51 segundos, y lo más largo
  declarado es ese `make test` de ~20 minutos. El valor elegido los despeja a los dos con margen, que es
  lo que se le pide a un backstop: ponerlo bajo no ahorra nada, mata un control sano a mitad.
- **El coste de una slice.** Nació en 25 $ cuando el registro durable no tenía ni un dolar real y lo
  único medido eran las llamadas grabadas en `src/slice_runner/tests/payloads/`, cuya mayor son
  **0.343 $**: dos ordenes de magnitud de margen sobre lo único que se sabia. El número elegido como
  techo inalcanzable resulto estar *dentro* del rango normal -las primeras muestras reales fueron
  **5.14, 10.75, 15.07, 25.46 y 27.73 $**, todas con Opus porque ninguna invocación declaraba modelo
  todavía-, y **dos slices sanas murieron con `abortada:presupuesto`**, las dos justo después de que el
  juez devolviera `PASA`, porque el límite se comprobaba tras pagar la llamada: se tiraba una aprobación
  ya pagada en vez de impedir la siguiente. Con el implementador fijando Sonnet la muestra crecio con
  **8.77 y 13.75 $**, bastante por debajo del rango de Opus, lo que confirma que fijar el modelo barato
  abarata la slice típica sin tocar el backstop. El techo subió a 50 $ **sin tocar que se cuenta**.
- **Los reintentos del juez, y por que se repartieron en vez de recortarse.** La intuición era que llegar
  al segundo reintento significa un problema que ninguna vuelta arregla -una convención mal escrita, un
  criterio mal definido- y que por tanto sobra. Medido sobre el corpus, es al reves: de las cuatro
  secuencias que llegaron a gastar los dos, **en tres el segundo reintento convirtió un veto que habría
  cerrado la slice en algo entregable**, y una necesito además un tercero. Con esa muestra no es
  concluyente, pero desaconseja recortar. Lo que si es solido es el reparto de las 60 verificaciones
  registradas: **21 vetos, 26 correcciones que no bloquean y 13 limpias**, o sea que el 43% de las vueltas
  que pagaba el presupuesto no impedian entregar nada -y además no convergian: hay secuencias que
  devuelven los mismos hallazgos dos veces seguidas-. De ahi que las dos causas dejaran de compartir
  contador, que es la misma regla que ya separaba la higiene de los controles. La reconstrucción se hizo
  por bloques consecutivos del mismo identificador de slice, que es lo único posible mientras el corpus no
  tenga identidad ni instante por fila.
- **Los reintentos de una llamada a `gh`, y la espera entre ellos.** No hay corpus de fallos transitorios
  de la interfaz de programación de GitHub del que medir un percentil, al contrario que el resto de esta
  lista: la intención que trajo la slice es explícita en que se quiere cubrir -"un parpadeo de red, un
  handshake que se corrompe, una conexion que se cae"-, y esos son fallos de segundos, no de minutos. Tres
  intentos con dos segundos entre uno y el siguiente despejan un parpadeo de varios segundos sin que un
  servicio caido de verdad convierta la llamada en una espera larga: el tope de la invocación sigue siendo
  `process_timeout_seconds`, que ya cubre "el proceso no vuelve nunca". Si el corpus de runs reales
  empieza a mostrar fallos transitorios que sobreviven a los tres intentos, este número es el que hay que
  revisar con esa medición delante.
- **El tope de tamano de las fuentes de convención.** Nace con la slice que hace viajar su contenido
  literal dentro del prompt (issue #216) y todavía no tiene corpus de runs reales que medir: lo único
  medido es el propio repo, cuyas seis fuentes que declara este issue suman **80126 caracteres**
  (`wc -c docs/conventions/{code-style,architecture,domain,application,infrastructure,testing}.md`). El
  número elegido, **200000**, deja algo más de dos veces y media de margen sobre ese caso real -la misma
  lógica que el techo de coste, que se fijo con margen sobre lo único medido en su día (arriba)-, y sigue
  siendo un backstop y no una preferencia: existe para que una fuente declarada por error como un
  directorio entero, o un `.md` que crecio sin que nadie lo revisara, pare el run con su motivo en vez de
  mandar un prompt desproporcionado. Cuando el corpus de runs reales tenga fuentes más grandes que las de
  este repo, este número es el que hay que revisar con esa medición delante.

- **Los reintentos de la puesta al día, y por que no comparten contador con nada que ya existiera.** La
  integración continua diagnosticando `bloqueada: conflicto` ya se contaba -PR #221, arriba- pero el run
  cerraba ahi mismo, y las nueve fusiones de `master` hechas a mano en el historial de este repo
  (`git log --grep="Merge remote-tracking branch 'origin/master' into"`) son la medida de lo que costaba
  eso. Repetir `GitBranches.catch_up` -que ya usa `_caught_up_before_conducting` al reanudar- desde
  `AWAIT_CI` cierra ese hueco, pero necesita su propio presupuesto: no es un tick de espera
  (`indeterminate_ticks` cuenta lecturas de la integración continua que todavía no contestaron, y una
  fusión contesta al momento) ni un reintento de la integración continua roja (`ci_retries` paga cuando el
  código está mal y hay que reimplementar; una puesta al día no toca código ni cuesta harness -la ronda de
  controles y la entrega que siguen son deterministas, y el juez ni se invoca-). Compartir cualquiera de
  los dos habría financiado un bucle ajeno al que lo agota, que es la misma razón por la que la higiene ya
  tiene contador propio frente a los controles. El valor, **3**, no tiene corpus de runs reales que medirlo
  -la propia razón de ser de esta slice es que el patrón nunca llegó a automatizarse-, y se eligió con el
  mismo razonamiento que `gh_retries`: unos pocos empujones bastan para poner al día la rama que se movio
  mientras la pull request esperaba, sin dejar que una base que no deja de moverse convierta el run en un
  bucle que solo el coste del juez frenaba hasta ahora.
- **Por que `DeliverSlice` no comitea cuando la entrega viene de una puesta al día.** Un `catch_up` que
  resuelve fusionando ya deja su propio commit de merge en el árbol; comitear de nuevo staggearia un
  índice vacío -o peor, algo que ni el implementador declaró- encima de un commit que ya existe. La
  decisión no la toma "si el índice esta vacío": eso seguiria siendo un fallo ruidoso y deseable en
  cualquier otro camino, incluido un implementador que no produjo nada. La toma un dato explícito,
  `from_catch_up`, que viaja desde la maquina de estados (`Run.catching_up_the_branch`) hasta el caso de
  uso de entrega: el push si es incondicional en los dos casos, porque es lo que hace que la integración
  continua vuelva a arrancar sobre una pull request que ya dejó de estar detrás.
- **Reabrir por conflicto reinicia también `indeterminate_ticks`, no solo `catch_up_retries`.** Un run
  puede acumular ticks de integración continua ilegible, cerrar después por conflicto con esos ticks casi
  agotados, y al reabrirlo la primera lectura ilegible lo cerraria otra vez con un motivo distinto del que
  la persona acaba de resolver a mano. Reabrir es una oportunidad nueva para los dos contadores que pudo
  dejar vivos ese cierre, no solo para el que lo causo.
- **La transición que reintenta la puesta al día espera antes de volver a preguntar, con
  `seconds_between_ticks`.** Justo después de empujar la fusión, GitHub recalcula la mergeabilidad de
  forma asincrona y puede devolver el diagnóstico anterior: sin esa espera, una lectura estancada gasta un
  reintento al instante y paga una ronda entera de controles por vuelta, lo que en un par de minutos agota
  `catch_up_retries` y cierra en `bloqueada:conflicto` -el desenlace que esta pieza existe para evitar-. Va
  en el reintento y no en la lectura de la integración continua porque es el único punto del ciclo con un
  tope garantizado independiente de cuanto tarde la ronda de controles que sigue.

### El descarte de aprobación pagada, y por que hay dos comprobaciones de coste

La comprobación de después de la llamada cierra el bucle del descarte del juez -que no gasta reintento
porque no se toco el código-, y la de antes es la que faltaba para no tirar una aprobación ya pagada.
Preguntarselo al **agregado** en vez de a la llamada tenía el agujero entero dentro: como una llamada sin
medición no añade nada a la suma, bastaba **una** medición previa en la invocación para que el total
quedase medido para siempre, y a partir de ahi cada llamada que muriera sin sobre parseable dejaba el
total congelado por debajo del límite.

### Por que el juez también fija modelo, y por que uno más caro que el implementador

Los 25-28 $ se pagaron con Opus porque ninguna invocación declaraba modelo. La primera corrección fue
asimetrica: el implementador fija el barato porque su trabajo lo revisa otro, y el juez se dejaba heredar
el de quien lanza el run. El problema de esa asimetría no era el argumento: era que "heredar" no es una
política declarada, es la ausencia de una. `RoleModels` no tenía campo `verify`, así que ni el conductor
podía decir con que modelo corria el juez ni la fila durable lo escribia -no se podía saber con que se
juzgo una slice ya cerrada, ni separar su coste del de la sesión que lanzo el run (issue #259)-.

Declarado hay que elegir, y la elección es `"opus"`, frente al `"sonnet"` que fijan `ImplementerInvocation`
y `UnderstandingInvocation`. **No la sostiene ningún corpus**: nada de las 60 verificaciones registradas
(más arriba) compara el mismo diff juzgado por dos modelos distintos. Lo que la sostiene es la asimetría
del coste del error. Un implementador flojo cuesta una ronda de corrección más, que se ve en el momento y
se paga una vez; un juez flojo aprueba una pull request mala, que no se ve y la paga quien venga detrás.
Mientras no haya medición, se prefiere pagar de más en el último control antes que de menos.

Lo que hace que esto sea una decisión reversible y no una preferencia enterrada es la otra mitad de la
slice: `models_by_role.verify` viaja en la fila durable, así que en cuanto haya runs del mismo diff
juzgados por modelos distintos se podran comparar, y bajarlo sera cambiar una constante con los datos
delante. Hay test de las tres cosas: que `RoleModels` no se construye sin `verify`, que
`JudgeInvocation.argv` emite `--model`, y que la fila durable lo trae.

### La duplicación con `skills/`: por que se acepta

Hubo una versión del programa que reutilizaba `escribe_diff_bundle` y `valida_veredicto` de
`controles.py` para no duplicar lógica, y el resultado fue peor: obligaba a que el programa arrastrase el
`pythonpath` del script, a escribir un `files.txt` que solo el flujo viejo necesita, y a pasar el
veredicto por un validador que Pydantic ya hacía redundante. **Acoplar el flujo nuevo al viejo para
ahorrar duplicación sale más caro que la duplicación**, porque el viejo esta condenado.

### El juez como objeto, y no como proveedor de prompt

`Judge(rubric, tools, readable)` sustituye a un `PromptProvider` que solo devolvía texto. Con la rúbrica,
las herramientas y los directorios legibles repartidos por capas distintas, nada obligaba a que
cuadrasen: la rúbrica llegó a ordenar cargar skills que el juez no podía leer, y el veredicto salia igual
de limpio. Un puerto para un valor constante era indirección; el invariante necesitaba un objeto.

### El registro de un paso sale del conductor, y por que no se saco más

`ConductSlice` decidia el flujo del run **y además** componia a mano su telemetria: el evento de cada
transición y la fila durable de cada cierre, esta última en dos sitios distintos. La consecuencia no era
estetica: cualquier slice que anadiera un campo al registro tenía que entrar en la pieza que decide cuando
se implementa, cuando se juzga y cuando se cierra.

**El dato que lo decidió fue el reparto de lo pendiente.** De las nueve slices abiertas en ese momento,
cuatro tocaban el registro (identidad de cada fila, configuración y tamano del cambio, formato de los
almacenes, rastro duplicado) y cuatro tocaban la ejecución y la alineación (desbloquear un run, indultar un
hallazgo, pedir cambios sobre la pull request). Partido justo por la mitad, y las dos mitades colisionando
en el mismo fichero sin tener nada que ver entre si: el paralelismo estaba capado por diseño, no por como
estuvieran priorizadas.

Se extrajo **solo el registro**, no las cinco responsabilidades que tenía. Sacar también la ejecución de
cada paso no compraba nada -esos metodos ya delegaban en casos de uso y no escondian lógica-, y sacar el
repositorio del issue habría obligado a inventar un caso de uso por cada lectura, porque la alineación lo
necesita para publicar el entendimiento, leer la respuesta y pausar.

**Lo que mide el cambio no son las líneas** -el conductor bajo de 599 a 581, apenas nada- sino que dejó de
nombrar ningún tipo de telemetria. Y de paso unifico una regla que estaba escrita en uno de los dos cierres
y no en el otro: un gasto que nunca se midió no entra en la fila, en vez de contar como cero.

### El agrupamiento de dependencias no era del conductor, era de lo que se recorre (2026-08-14)

La desviación se escribió con un ancla equivocada: decía que agrupar los puertos era **del conductor**,
por ser "la única pieza que compone casi todos los puertos del programa". Eso no es una regla, es un
censo de un día, y el propio `docs/conventions/como-se-escribe.md` lo prohibe -una lista cerrada de lo que
hay hoy, presentada como si fuese la regla-.

**Lo destapó un veto.** La slice-01 de #247 necesitaba un sexto puerto en `CheckReadiness` para que el
`doctor` pudiese contrastar de que árbol salieron el programa y las skills. Seis parametros disparan
`PLR0913`, el implementador agrupo, y el juez lo bloqueo con severidad alta citando textualmente la línea
de la desviación. El veto era correcto: la convención decía lo que decía. Lo que no era correcto era la
convención.

Las dos salidas que el juez ofreció -partir la query, o enmendar la convención- **las declaró el mismo
como decisión del repo y no del implementador**, así que el run no podía salir de ahi: cualquier cosa que
eligiera era o un veto nuevo o mover la vara con la que se le mide, que es un antipatrón escrito. Se paró
el run y se decidió fuera.

**El criterio que sustituye al censo es de que es proporcional la lista de puertos.** Un caso de uso que
gana puertos porque hace más cosas tiene una firma larga como síntoma, y se parte. Uno que los gana porque
su trabajo *es* recorrerlos -conducir un run entero, contestar si todas las piezas están en su sitio- no
se arregla partiendolo: la misma lista queda repartida en dos piezas y aparece una tercera que las
compone. El criterio se puede aplicar a un caso de uso que todavía no existe, que es justo lo que el censo
no permitia: con la redacción vieja, cada pieza nueva que cayera de este lado obligaba a editar la
convención para dejarla veraz.

Coste medido del fallo: el run de la slice-01 de #247 se paró a los 36 minutos y 9,76 $, con una llamada
al juez tirada a mitad.

### La forma de una lista, extraida al tercer consumidor

`CountedLines` vivio duplicada a propósito mientras solo la compartian dos prompts: cada uno es un
contrato con un agente distinto y nada exige que se parezcan, así que extraerla habría fijado un parecido
que no era invariante. La convención se escribió a si misma la condición "con un tercer prompt se
extrae", el entendimiento fue ese tercero, y la condición se cumplió -aunque no sola: el juez veto la
slice con severidad `alta` citando esa misma línea-. Que una condición escrita se ejecute importa más que
la regla concreta; la que nadie ejecuta ensena que el fichero donde vive es opinion.

### El commit único por slice era un residuo, y se retira (2026-08-11)

Nadie decidió nunca que una slice fuese un solo commit. Salió de la decisión del 2026-07-30 de mover el
commit **detrás** del veredicto -para que un veredicto negativo no dejara rastro que deshacer-, y "un
solo commit **sin `--amend`**" quedó escrito ahi como la consecuencia barata de ese movimiento, no como
un objetivo. El precio si se registro: la rúbrica del juez tenía un item que pedia que el test precediera
a la implementación, y hubo que retirarlo porque el historial de un commit único nunca puede acreditarlo;
en el smoke del 2026-07-27 los tres agentes contestaron "no puedo constatarlo", o sea ruido garantizado
en todas las slices.

Se retira porque una ronda de corrección fundida con lo que corrige obliga a quien revisa a reconstruir
del diff final que se pidió cambiar. Lo que devuelve la vuelta atras no es solo permiso: es la capacidad
de acreditar en el historial el orden en que se hizo el trabajo, que se había dado por perdida. Lo que
**no** cambia es lo que era decisión propia y no consecuencia: `git add` con rutas explicitas, la higiene
del índice antes de cada commit, y `--merge` al fusionar.

### La pull request deja de nacer en borrador, y gana asignado y co-autor (2026-08-13)

Nacia con `--draft` desde el commit inicial del programa, y el motivo escrito era "el merge lo decide una
persona". Ese motivo **ya lo garantizaba otra cosa**: el programa no mergea, se para en `esperando-merge`
y termina. Lo que el borrador anadia encima no era control, era un paso manual que nada recordaba.

Se pago el mismo día que se retiró: el run de la slice-10 de este repo agoto su espera de merge con la
pull request verde, el veredicto dado y todo hecho, porque nadie la había sacado de borrador. El programa
tuvo que decirlo con un aviso que existia **solo** para compensar el borrador -y que se queda, porque
sigue habiendo esperas que se agotan, pero deja de afirmar que la pull request nace en borrador, que ya no
es cierto-.

Entran a la vez dos cosas que hacen visible quien hizo que: **asignada a quien conduce el run**, porque es
quien tiene que mergear y así le aparece en su lista, y **el commit acreditando a Claude como co-autor**,
que es el mismo mecanismo que usan las pull requests que salen de una sesión de Claude Code. Lo que **no**
entra es Claude como asignado: comprobado contra la interfaz de programación de GitHub, solo se puede
asignar a colaboradores del repo, así que sería una llamada que falla o que se ignora en silencio.

### Que se rompe hoy al reanudar un run, y en que orden vale la pena arreglarlo (2026-08-11)

El `Run` que se persiste en la subissue lleva nueve campos; el progreso que el conductor tiene en memoria,
catorce. Lo que se pierde no es adorno: sin los veredictos, una reanudación en el paso de implementar
manda al implementador sin los hallazgos que tiene que corregir; sin la lista de ficheros que el
implementador declaró, una reanudación en los controles stagea una lista vacía y **acusa de infracción de
higiene a todos los ficheros que si estaban bien**, gastandole un reintento.

Lo que se descubrió al medirlo es que **el mundo ya guarda casi todo**: los veredictos con sus hallazgos
en el corpus, los logs de los controles en disco con nombre determinista, el gasto por llamada en su log,
y la pull request la sabe el foro. Solo tres datos no viven en ningún sitio. Así que el patrón a extender
no es persistir más, sino releer -que es lo que ya hace el entendimiento, la única pieza que sobrevive
limpia a una muerte-. Su precio es que releer necesita poder buscar sin ambiguedad, y eso depende de que
cada fila diga de que run viene.

El orden se decidió poniendo cada arreglo contra un fallo real (un run que gasto quince dolares y murió
al entregar porque su rama no existia):

| | coste | que habría hecho en ese fallo |
|---|---|---|
| Comprobar el suelo al reanudar | quitar una condición, más tests | parar en el segundo cero, sin gastar |
| Caer escribiendo estado | pequeño | dejar dicho que paso en vez de quedarse en curso |
| Releer el mundo | varias lecturas nuevas, y depende de la identidad de las filas | nada: el estado no era el problema |
| Commit por paso | contenido | conservar el código, y fallar igual al entregar |

Lo barato es lo que más valia, así que va primero, y es lo contrario del orden en que se había listado.

### Los hallazgos indultables se publican, y el comentario manda (2026-08-11)

Para indultar un hallazgo en una invocación distinta a la que lo produjo hace falta que el hallazgo
sobreviva con identidad. El veredicto entero ya está escrito en el corpus, así que la opción coherente con
"un segundo sitio donde escribir puede desmentir al primero" era que el corpus mandase y el comentario
fuese solo una vista. Se eligió lo contrario -el comentario de la subissue es la fuente de verdad- por dos
razones: quien indulta es una persona y necesita ver lo que indulta, y el corpus solo se puede buscar sin
ambiguedad cuando sus filas digan de que run vienen, que es trabajo que va por detrás. El corpus se queda
en lo que es hoy, material de medición agregada.

### Donde se va el dinero de un run, medido (2026-08-11)

Sobre 122 sesiones y 342 $ de gasto acumulado, uniendo el rastro de llamadas con el de gasto por sesión:

| paso | % del gasto | $/llamada | turnos/llamada |
|---|---|---|---|
| implementar | 68 | 4,49 | 66 |
| verificar | 21 | 1,91 | 26 |
| entender | 11 | 1,17 | 30 |

Lo que descoloca es la descomposición de esa llamada de implementación: **el 65% es lectura de cache**
-9,7 millones de tokens releidos a lo largo de sus 66 turnos- y **la salida es el 6%**. No se paga por
lo que el modelo escribe, se paga por el contexto que arrastra.

Y el dato que decide donde mirar: comparando la primera llamada de implementación de cada slice con las
siguientes, **cuestan casi lo mismo** (4,70 $ y 10,2 M de lectura frente a 4,38 $ y 9,5 M). Una vuelta de
corrección **redescubre el repo entero**: repite los mismos listados y las mismas lecturas que una
llamada anterior de la misma slice hizo minutos antes. Como dos de cada tres llamadas de implementación
son segundas o posteriores, ahi se va **el grueso de lo que cuesta implementar**.

De ahi salen tres candidatos, y el orden por premio no coincide con el orden por esfuerzo: reanudar la
sesión del arnés entre vueltas -el identificador ya se guarda en el rastro desde siempre y nunca se ha
usado-, bajar de modelo al que produce -coherente con que su trabajo lo revise otro-, e inyectar las
convenciones en vez de apuntarlas. El tercero **no se aplica por ahora**: lo que se midió inyectaba un
documento, y la vara real son decenas de miles de tokens repartidos en varios ficheros, o sea fuera del
rango medido. Los otros dos se miden en el playground antes de tocar nada.

**El riesgo de reanudar no es el que parecia.** La objeción inicial -que la sesión vieja contamine con
decisiones previas- se cambio por una más concreta y medible: un implementador reanudado **defiende su
propio diseño** cuando el hallazgo contradice lo que eligió. La tarea `implementer-resume` lo mide con dos
hallazgos a la vez, uno que añade trabajo -donde reanudar debería ganar- y otro que revierte una decisión
suya -donde debería perder-.

### Reanudar la sesión parte los turnos por la mitad y no ahorra nada (2026-08-11)

Medido con `implementer-resume`, cinco repeticiones por variante, dos vueltas por celda:

| segunda vuelta | llamada nueva | sesión reanudada |
|---|---|---|
| turnos | 24,4 (rango 22-26) | 11,0 (rango 9-14) |
| coste | 0,370 $ (0,348-0,397) | 0,403 $ (0,347-0,473) |
| lectura de cache | 292 k | 440 k |
| segundos | 121,9 | 127,1 |

Los rangos de **turnos no se solapan**; los de **coste se solapan enteros**, con la sesión reanudada
tendiendo a más cara. El mecanismo está en la lectura de cache: cada turno reanudado arrastra la
conversación anterior entera -unos 40 k por turno frente a 12 k-, así que se cambian muchos turnos
pequeños por pocos turnos grandes y **el producto sale igual**. Tampoco gana en reloj.

La consecuencia para donde buscar ahorro es que **el coste es turnos por contexto**, y reanudar mueve los
dos factores en direcciones opuestas. Lo que si mueve el producto es el precio del token -o sea el
modelo- o el contexto que se arrastra por turno. Reanudar se queda como herramienta de **latencia en
número de pasos**, no de dinero, y en un repo más grande debería salir **peor**, no mejor: la sesión de
la primera vuelta es ahi mucho más larga, así que lo que arrastra cada turno reanudado crece con ella.

Y el riesgo que se había elevado a hipótesis principal **no apareció**: el hallazgo que revierte la
decisión del propio implementador lo corrigieron **las dos variantes en las cinco repeticiones**. Las seis
reglas salieron 5/5 en ambas, así que reanudar tampoco degrada. Simplemente no compra lo que se buscaba.

### Haiku implementando: 78% más barato, y 2 de cada 5 salen defectuosas (2026-08-11, sin cerrar)

Misma tarea `implementer-resume`, misma semilla, solo la variante de llamada nueva, cinco repeticiones
por modelo. Antes de medir se añadió la regla que faltaba y que es la única que dice si el código
**funciona**: ejecutar los tests que el propio modelo escribió. Las seis anteriores comprueban forma, y
un modelo más flojo puede cumplirlas todas y escribir algo que no arranca.

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
tests y el otro lo caza el juez, así que **el coste de fallar es una vuelta extra**, no código malo
mergeado. Y el punto de equilibrio calculado sobre el gasto real dice que el modelo barato tendría que
subir la media de vueltas extra de 1,04 a **2,8** para dejar de ahorrar; un 40% de defectuosas la deja
alrededor de 1,5-1,9. Compensa, y con margen.

**Por que no se ha decidido.** Dos fallos sobre cinco dejan la tasa real en cualquier sitio entre el 10% y
el 70%, y es el número del que depende todo. Afinarlo cuesta unos 3 $ -cada celda del barato son 0,20 $-,
que es lo que hay que gastar antes de tocar nada:

```bash
python3 playground/harness.py implementer-resume --label haiku --variants fresh \
  --seeds seed-populated --repetitions 20 --model haiku
```

Y aunque salga bien, **el experimento no mide el factor que decide**: cuántas vueltas de corrección pide
el modelo barato contra el juez de verdad, en un repo grande. Eso solo se ve conduciendo dos o tres slices
reales y mirando los reintentos, no en el banco.

### Un esquema sin suelo deja publicar el relleno (lo que se midió)

El 2026-08-13 una slice público como entendimiento esto: resumen `test`, un paso `a` con motivo `b`,
esbozo `test`. Se público con la firma del programa, y le paso lo mismo a otra persona ese mismo día.

**Lo que la transcripción de la sesión enseno.** El modelo llamo a `StructuredOutput` **cuatro veces**:
el informe bueno con el JSON mal escapado (rechazado por no parsear), dos intentos corregidos a los que
**se les había caido `steps`** (rechazados por el esquema), y un cuarto minimizado a valores de relleno
que **si valido**. El programa se queda con el último. No es que el modelo no trabajase: esa llamada
gasto 49.691 tokens de salida y 2,67 $, **más que el entendimiento bueno que vino después** (48.059 y
2,25 $). Minimizar tras tres rechazos es lo que hace cualquiera para aislar un fallo; lo que no puede
pasar es que el mínimo se publique.

**No era no determinismo: era una regresión con fecha.** Sobre las 115 sesiones de arnés con
transcripción, contando las que necesitaron más de un intento de salida estructurada:

| Paso | Sesiones | Con más de un intento |
|---|---|---|
| `verify` | 39 | 0 |
| `implement` | 45 | 4 (repartidas por todo el histórico) |
| `understand`, esquema de un campo de texto | 25 | **0** |
| `understand`, esquema de tres campos | 6 | **5** |

El corte es el commit que partio el entendimiento en `summary`/`steps`/`sketch`, donde `sketch` pedia
firmas de código. Escribir código dentro de un JSON es donde se rompe el escapado, y por eso `verify`
-cuyo esquema son campos cortos- no falla nunca.

**Y el esquema no tenía con que parar el relleno.** Tras retirar los cuatro topes maximos por no
haberselos contado al modelo, quedó sin ninguna restricción: `{"summary": "test", ...}` era formalmente
valido, así que el arnés contesto `Structured output provided successfully`. La respuesta fueron suelos
minimos -120 caracteres de resumen, 2 pasos, 1 pieza-, calibrados contra los cinco entendimientos buenos
del formato nuevo (resumenes de **669 a 1.075** caracteres y **7 u 8** pasos, o sea 5,5 veces de margen
para el más ajustado) y publicados en el brief para que no se descubriesen a base de rechazo.

**Duraron un día, y por que es la lección de verdad.** Esa misma tarde el agente los uso como diana:
tras rechazarle informes de **2.113 y 3.654** caracteres entrego uno de **85** y otro de **434**,
calibrados para pasar justo los suelos que el brief le había contado. La instrucción que lo prohibia
estaba escrita en ese mismo brief -"no lo reduzcas para que pase"- y perdio contra tres rechazos
seguidos. Medido sobre 728 transcripciones: 44 rechazos, **ninguno** causado por un mínimo, y las dos
degradaciones a relleno solo en el entendimiento, que era el único papel con suelo en el esquema **y**
con los números publicados. Donde no hay diana no hay a que encoger: implementador y juez reintentan al
mismo tamano (ratios de 1,0 a 1,2) y aciertan.

Así que el pendulo dio la vuelta entera -maximos secretos que rechazaban trabajo bueno, minimos
publicados que ensenaban cuan poco basta- y los dos extremos acabaron retirados. **El instrumento era el
error**: `minLength` y `minItems` no los puede hacer cumplir la generación estructurada de la API -solo
tipos, enums y `required`-, así que solo existen como rechazo posterior, y miden forma y longitud, que
no son entendimiento. Lo que se queda es lo que mide vacío y no brevedad: el esquema exige los campos
por `required`, y `_usable_text` rechaza el informe que traiga alguno en blanco.

**El esbozo se veia mal por otra cosa, y también se arreglo aquí:** el programa pegaba el texto crudo
bajo `## Esbozo` sin envolverlo, así que markdown fundia las líneas de dos espacios con el párrafo
anterior y convertia las de cuatro en bloque. Ahora viaja como **lista de piezas** y el bloque lo compone
el programa: el modelo escribe datos y no markdown, que de paso es menos texto libre que escapar. En el
mismo movimiento que retiró los suelos, `steps` y `sketch` se fundieron en un único `plan` con
`signature`, `does` y `reason`: pedian el mismo contenido cuando la slice es mecánica, y **18 de los 44**
rechazos medidos fueron `falta 'steps'`, el agente entregando una sola de las dos listas.

**Lo que sigue sin cerrarse:** el programa no ve la pelea. Sabe que hubo cuatro intentos y tres
rechazos solo porque alguien leyó la transcripción a mano. Se cierra a medias marcando en el registro
durable de usos de herramienta las llamadas que el arnés rechazo (`failed`), que es lo que deja contar
la tasa sin abrir un `.jsonl` de sesión; falta el **tamano** de cada intento, sin el cual la ratio entre
lo aceptado y lo rechazado -el 4% y el 12% de arriba- no se puede calcular sin volver a la transcripción.
Frenar por esa ratio se descarto: sería un tercer suelo secreto, aplicado después de pagar la llamada y
calibrado con dos casos, los dos del mecanismo que se acaba de retirar.

### El gasto que se consulta deja de depender del `Run` persistido (2026-08-21)

`status` y la fila que cierra una slice (`ClosedSliceRecord.spend`) leian el gasto de `Run.spend`,
acumulado en memoria por el conductor tick a tick. Una invocación que muere justo después de que el
arnés conteste -la llamada ya quedó grabada en `spend.jsonl`- pero antes de que el tick escriba el
`Run` de vuelta dejaba ese coste huerfano: ni la consulta ni la fila volvian a verlo. La retrospectiva
de 2026-08-20 lo midió en dos slices reales: la #330 registro 1,95 $ cuando sus seis llamadas sumaban
6,71 $, y la #332 registro 16,28 $ cuando sus nueve sumaban 24,46 $.

El arreglo cruza el rastro de llamadas (`CallTrace`) con el registro de gasto por sesión
(`CallSpendLog`) -la misma lectura que ya usaban `SpendByRole`/`SpendOfStep` para otro caso de uso-, en
vez de leer `Run.spend`. `Run.spend` sigue existiendo y sigue siendo la cuenta en vivo que aborta un run
por presupuesto durante la conducción; lo que cambio es de donde sale el número que se **escribe** al
cerrar y el que se **muestra** al consultar.

Ese cambio dejó sin lector el campo `Run.spend_before_reopening`, que acumulaba el gasto de vueltas
anteriores cada vez que una slice se reabria tras un `ABORTED_BUDGET`: nadie fuera del propio campo lo
leia para producir un resultado, así que se retiró del dominio entero (`Run`, `StateMachine.reopened`).
`RunPayload` sigue declarando la clave `spend_before_reopening` -sin ella, `extra="forbid"` rechazaria
un bloque de estado que una slice en vuelo ya escribió con ese campo-, pero `from_domain()` ya no la
emite nunca y `to_domain()` la lee y la descarta en vez de pasarla a `Run(...)`. Es compatibilidad de
lectura pura: se puede retirar la clave del payload en cuanto no quede ningún run persistido de antes de
esta fecha que todavía la lleve.

## deploy-watch

### Decisiones clave

- **Fase post-approve, invocación manual, read-only sobre prod.** Disparador manual elegido para cero polling en vacío.
- **Compone, no reinventa**: el agente orquesta por tick las skills de observabilidad (catalogo abierto) + agente `sre`; la decisión la hace un core puro (`deploy_core.py`: umbrales relativos, confirmación sostenida, scorecard, veredicto). Antes delegaba en una skill `deploy-monitor` suelta (script HTTP bloqueante), **absorbida en 2026-07-23**.
- **Veredicto por 4 señales**: rollout k8s, recursos (OOM/restarts/CPU), errores/latencia HTTP vs baseline, Sentry (issues nuevas del release). Sano solo si las 4 están ok toda la ventana de estabilización.
- **Ante anomalia**: agente `sre` para RCA read-only + rollback redactado (git revert del merge + redeploy según slicing.md), sin ejecutar.
- **Seguridad**: nunca ejecuta rollback ni toca backends; max_runtime + circuit breaker; merge y rollback los decide el usuario.
- **El encadenado esta apagado desde 2026-08-13, y se apago por el cableado.** El programa lleva `MutedDeployWatch` inyectado en vez de `ClaudeDeployWatch`, así que mergear una slice ya no lanza `claude -p '/deploy-watch ...'`. El motivo es de calendario, no de diseño: la skill todavía no esta pulida -es la única pieza del pipeline que nunca se ha medido contra un despliegue real de otra persona- y el equipo empieza a probar el flujo esta semana; una llamada que cuesta dinero, tarda y puede confundir a quien nunca ha visto la herramienta es exactamente lo que no debe encontrarse en su primera slice. **Lo que no se apago**: la línea `SENAL:` se sigue disenando en el slicing, se sigue exigiendo, y su emisión sigue siendo criterio de aceptación que el juez mide antes de mergear -o sea que lo que se pierde es la comprobación post-deploy, no la observabilidad de la slice-. Se eligió el adaptador mudo sobre las otras dos formas por lo que cuesta **volver**: una bandera de línea de comandos anadia superficie que habría que retirar después, y borrar la llamada de `ConductSlice` dejaba el puerto sin consumidor y obligaba a reescribir código y test para reencender. El detalle de la decisión de capa vive en `docs/conventions/infrastructure.md`; cuando se pula, se reencienden la línea de `cli.py`, el paso 4 del `README.md` y su diagrama.

### La regla que se aplico tres veces y nunca se escribió (2026-08-21)

Vaciar el conductor de trabajo que era de un caso de uso se hizo en #295 (los dos pasos que esperan),
#302 -"que ejecutar los controles deje de estar a medias entre el conductor y un caso de uso"- y #308
(entender). Tres veces el mismo movimiento, y la regla se quedó en el `git log`: `application.md` solo
recogio el caso particular de la telemetria.

La recaida llegó con la puesta al día de la rama. El entendimiento que la persona aprobo con `-GO`
prometia un caso de uso propio para ella; la implementación llamo al puerto desde el conductor, y además
metio ahi la proyección de su vocabulario a `Outcome`. Nada lo freno, y no por descuido de nadie:

- **El juez no tenía con que.** Su vara principal son las fuentes de convención que recibe, y la regla no
  estaba escrita en ninguna. Con `domain.md` en la mano si cazo la proyección **dentro** del conductor
  -bloqueo por la rama por omisión de un `match`- pero no que la proyección entera no fuese suya.
- **Los criterios de aceptación hablaban solo de comportamiento.** Fusiona, no rebasa, cierra sin gastar
  arnés. Ninguno decía donde vive la pieza, así que el mapeo criterio-test no tenía nada que exigir ahi.
- **El plan aprobado no lo verifica nadie.** El `-GO` es un contrato entre la persona y el programa, y el
  juez -a propósito- no recibe narrativas del implementador. Contrastar las rutas que el plan promete con
  las que el diff toca es trabajo determinista que hoy no existe.

De ahi salen las dos cosas que se hicieron a la vez que esta nota: la regla en `application.md`
-atemporal, sin contar precedentes, que es lo que esta nota si puede hacer- y la exigencia en `slice-spec`
de que un criterio pueda fijar donde vive una pieza. La tercera, el contraste entre el plan y el diff,
queda como trabajo declarado.

## Una regla de negocio se escribe una vez (lo que se midió)

La regla vive en `docs/conventions/architecture.md`. Esta nota es de donde salió, porque el número es
lo que sostiene la vara y la vara no se escribe con precedentes dentro.

**Que se midió.** Un barrido del programa buscando expresiones booleanas y ramas de `match` repetidas
(`src/slice_runner/`, sin `tests/`) devolvio 26 repeticiones. Clasificadas a mano, **la mayoria es idioma
de frontera y no toca**: `output.code != 0` en once adaptadores que lanzan procesos,
`not isinstance(data, dict)` en once modelos que validan un sobre. Ningún cambio de negocio obliga a
tocar dos de esos a la vez.

Lo que quedó después de ese filtro, y es el inventario del que salen los arreglos pendientes:

- **La regla que ya fallo**: "una slice sin estado persistido no se puede reabrir", en
  `SelectSlice._awaiting_retry` y otra vez en `ReopenSlice.execute`. Redacciones distintas, desenlaces
  distintos -una devuelve `None` y sale como "no hay slice", la otra lanza-, y el mensaje que produce la
  primera manda a escribir un `-RETRY` que la segunda no habría aceptado nunca. Costó dos runs, y el
  comentario que se público siguiendo el mensaje hubo que desarmarlo.
- **Los cinco marcadores de comentario no forman conjunto.** Cinco clases con su `MARKER` y un
  `is_the_marker` copiado literal. Como el conjunto no existe, "que marcadores cierran un ciclo" no se
  puede declarar en ningún sitio, y por eso la ventana que lee el `-RETRY` corta en el de *reabierta* y no
  en el de *reseteada*: una instrucción escrita antes de un reset le sobrevive y se aplica al bloqueo
  siguiente. No es un olvido, es lo que pasa cuando no hay donde escribirlo.
- **"Como se lee la respuesta de una persona", dos veces.** `AlignmentResponse.of_the_comments` y
  `RetryResponse.of_the_comments` son el mismo cuerpo: recorrer al reves, devolver la primera
  interpretable, si ninguna entonces "todavía no".
- **"Un repo eximido de controles", cuatro formulaciones.** `Controls` tiene el campo y no la pregunta, así
  que `RunControls` la formula por un lado y los dos sobres de agente por otro -con el literal de la línea
  duplicado-.
- **La partición de `Step` declarada cuatro veces**, en `StateMachine` y en `ConductSlice`, más dos
  particiones distintas del mismo enum en `IssueLabel` y en la propia `StateMachine`.
- **"Que cuenta como hallazgo", cuatro sitios**: `Verdict.count_of`, las dos cuentas de `ClosedSlice` y el
  filtro de bloqueantes de `Verdict`. Hoy coinciden, así que no hay fallo. Lo habra en cuanto entre la
  slice que indulta un hallazgo, que es la que cambia exactamente eso y tiene cuatro sitios donde acertar.

**Por que en este repo pasa más.** El programa lo escribe un arnés que no puede aprender: cada invocación
empieza sin memoria de las anteriores. Cuando necesita una regla que ya existe en otro fichero no la
reutiliza -no sabe que está ahi-, la **vuelve a derivar** donde le hace falta. De ahi la propiedad que
gobierna la vara: **las copias casi nunca son literales**. El caso que fallo está escrito de dos formas
que no se parecen, así que un detector de duplicado no lo habría encontrado nunca, y por eso la vara es la
pregunta del cambio -¿cuántos ficheros hay que tocar?- y no el parecido del texto.

**Y por que la regla de tres no le vale.** Esperar a la tercera copia es correcto cuando el coste de
equivocarse es código feo. Cuando el coste es que el programa se contradiga -y el síntoma aparezca donde
alguien creyo la copia, no donde esta-, el umbral correcto es cero. Es la misma asimetría que ya gobierna
otras decisiones de aquí: el precio del falso positivo es una extracción de más, el del falso negativo es
un run muerto sin diagnóstico.

**Que se hizo y que no.** Se escribió la regla, sus antipatrones, y el reconocimiento explícito de que el
`match` exhaustivo protege del olvido pero no del reparto -obliga a mencionar un miembro nuevo, no a
clasificarlo igual en los cuatro sitios-. **Los seis arreglos del inventario quedan como trabajo
declarado**, no hechos: la convención no los ejecuta. El orden que se recomendo es el hallazgo que ya
tiene fecha de caducidad primero -el de contar hallazgos, por la slice del indulto- y el de los
marcadores después, porque ya había que tocarlo.

## La vara dice la regla; el codigo dice su forma (lo que se midio)

`docs/conventions/infrastructure.md` describia, en dos vinetas, como estaban montados tres adaptadores
concretos: que agrupaban su telemetria en un objeto, que el rastro lo escribia "el adaptador que la
hace", y dos motivos que razonaban sobre cuantos puertos le caben a una firma antes de que salte el
linter. Las dos vinetas eran verdad el dia que se escribieron.

**Que se midio.** Dejaron de serlo con la slice que puso la secuencia de una llamada al arnes en un solo
sitio, y **nada aviso**: `make check` siguio verde, la integracion continua paso, el juez no dijo nada.
El fallo se encontro a mano, leyendo la capa despues de mergear, y lo que habria pasado si no es
concreto: el siguiente rol se escribe leyendo esa capa -el `CLAUDE.md` lo hace obligatorio-, asi que la
convencion le habria dicho que inyectase la telemetria y registrase por su cuenta, justo lo que el
invariante iba a ponerle en rojo. Una vara que instruye a hacer lo que otra vara prohibe es peor que
no tener ninguna.

**Por que caduco, y no es mala suerte.** Una convencion de este repo **viaja dentro del prompt** de los
tres agentes, asi que no es un documento que se consulta: es contexto que se carga entero, siempre. Cada
frase que describe la forma del codigo compite por la atencion con la regla y, a diferencia del codigo,
no se actualiza cuando la forma cambia. Escribirla ahi es congelar en prosa un dato que quien lea el
arbol puede descubrir mejor -y que, al descubrirlo, encontrara al dia-.

De ahi el reparto que esta nota fija: **la convencion dice lo que el codigo no puede decir de si mismo**
-que esta prohibido, por que se eligio, que consecuencia se acepto- y **el codigo dice su propia forma**.
La regla que sobrevivio a la poda es la que cumple eso: el rastro lo escribe la capa que ve la respuesta
y no la que orquesta, sin nombrar quien ni con cuantos puertos.

**Que se hizo.** Se retiro la vineta de agrupar la telemetria -su regla de fondo, agrupar dependencias
cuando la lista es el trabajo, ya vive en `application.md`, y aqui solo era su aplicacion a un caso- y
se podo la del rastro dejando la regla, su motivo atemporal y la consecuencia sobre el identificador de
sesion. **No se anadio nada**: lo que impide que el rol siguiente registre por su cuenta no es una frase,
es la firma -sin la telemetria en el constructor no tiene con que- y el invariante de alcance total. Y la
regla general de que una decision se escribe una vez ya vive en `architecture.md`.

**Lo que queda declarado.** Que esto vuelva a pasar no lo impide nada todavia: ninguna vara mide si una
frase de una convencion sigue describiendo el arbol. El contrato de rutas comprueba que una ruta citada
existe, no que una afirmacion sobre el codigo siga siendo cierta, y por diseno no puede -comparar prosa
con arbol es lo que este repo evita en el otro sentido-. Lo unico que baja el riesgo es la regla de esta
nota: no escribir la afirmacion.

## Roadmap de autonomia (pendiente)

Estado actual: **Nivel 1** — una slice por invocación, todo bajo control manual. Subir de nivel solo cuando el anterior sea fiable; el cuello de botella nunca es implementar, es la calidad del gate de verificación.

- **Nivel 2 — semi-autonomo con `/loop`.** Envolver slice-runner en `/loop`: al terminar una slice (PR + CI verde), coge la siguiente pendiente sola. Guardrails a añadir antes de activarlo:
  - Circuit breaker: `max_consecutive_failures` (parar tras N slices bloqueadas seguidas).
  - `max_runtime` / tope de slices por sesión (evitar loop eterno).
  - Checkpoint humano opcional entre slices.
  - Requisito previo: confianza en el verificador; es lo que sostiene el loop sin supervisión.
- **Nivel 3 — Workflow fan-out (paralelo).** Solo para slices independientes. Requiere: chequeo de independencia (solape de ficheros/migraciones), aislamiento de entorno de test por worktree (`COMPOSE_PROJECT_NAME`/puertos), y orden de merge (serializar quien toque el head de alembic).
- **Encadenar slice-runner -> deploy-watch.** Tras el merge, disparar deploy-watch automaticamente. Hoy deploy-watch es manual por decisión (cero polling en vacío); la versión encadenada poll-earia el estado del PR/merge para arrancar sola.
- **deploy-watch autonomo.** Opción descartada de momento: un `/loop` que vigila el merge y arranca la monitorización solo. Reconsiderar si el volumen de slices crece.
- **Aislamiento mecánico del orquestador (fase 2 del coste de contexto).** La fase 1 (2026-07-31) bajo lo que cuesta el orquestador por slice, pero **no** lo saco de la sesión de la persona: el contexto limpio por slice sigue dependiendo de que ella abra sesión nueva. Lo único que lo haría mecánico es que cada slice corra en un contexto propio -un proceso `claude -p` por slice lanzado desde un script, o un orquestador subagente-, y las dos formas chocan con el **go/no-go del paso 3**. Que es justo lo que hay que decidir explicitamente, porque bajo `/loop` **ese control humano ya es ficción**: nadie responde una alineación en un run desatendido, así que Nivel 2 ya renuncio a el de facto sin escribirlo en ninguna parte. Cualquier diseño de fase 2 tiene que elegir entre recuperarlo (checkpoint humano real entre slices) o declarar que a partir de Nivel 2 no existe; heredarlo por descuido es la peor de las tres.

## Preferencias transversales

- Respuestas y skills sin emojis (preferencia del usuario) -> el testigo de contexto es un marcador de texto `[skill-name]`, no un emoji.
- Idioma: cuerpo de las skills y comunicación en castellano; código/commits/PRs en ingles (convención de los repos).
