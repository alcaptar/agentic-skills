# El contexto del orquestador (fase 1)

Fecha: 2026-07-31

## Intencion

El README afirma que "cada slice arranca con contexto limpio, asi que ninguna sesion vive lo
suficiente para degradarse". En la practica no se pueden correr todas las slices de una feature en
una sesion: hay que compactar a mitad del run, y a partir de ahi las decisiones del orquestador se
toman con el contexto ya mutilado -justo el fallo que este repo existe para evitar-.

La afirmacion es cierta **solo de los subagentes**. El implementador y el verificador nacen y mueren
por invocacion, y su contexto es desechable de verdad. El **orquestador** no: vive en la sesion de la
persona y acumula todo el run. Y `/loop` (Nivel 2) reinyecta el prompt **en la misma conversacion**
con el contexto intacto a proposito, asi que el nivel donde el README promete contexto limpio es
precisamente donde no lo hay.

Coste por slice del orquestador, medido:

- `skills/slice-runner/SKILL.md`: 8.500 palabras (~13k tokens), recargadas **en cada invocacion**.
- el prompt del implementador, que el paso 5 le hace redactar entero (metodologia incluida), mas su
  mensaje final; otra vez por cada reintento.
- los ticks de integracion continua y de merge, uno por resultado de Bash.
- `deploy-watch` encadenado en el paso 10, en la misma sesion.

## Alcance

Fase 1: **bajar el coste por slice** y **dejar de afirmar lo que no es**. El aislamiento mecanico
-que el orquestador viva fuera de la sesion- es fase 2 y se decide aparte.

Dos palancas de las cuatro identificadas. Las descartadas, con su motivo:

- **Desencadenar `deploy-watch` del paso 10** (~6-10k tokens): descartada por ahora por decision del
  usuario. `deploy-watch` se queda encadenado como esta.
- **Esperas con `Monitor` en vez de N ticks** (~1-3k tokens): descartada, el ahorro no paga el cambio.

## Decision 1: el implementador pasa a agente definido

Nuevo `agents/slice-implementer.md`, hermano de `agents/slice-verifier.md`. Su *system prompt*
lleva la metodologia, verbatim en cada invocacion: el ciclo TDD delegado en
`superpowers:test-driven-development`, los cinco deltas (exencion de capa, integridad de tests
preexistentes, refactor tras cada verde, el esfuerzo va al test, la senal se construye aqui), el
auto-check de wiring, los controles verdes antes de entregar, la prohibicion de tocar el issue, y la
forma de lo que devuelve.

El paso 5 del `SKILL.md` se queda con **los datos del run** y nada mas: slice id y name, intencion,
criterios de aceptacion, `SENAL`, fuentes de convencion ya filtradas, controles como
`nombre=comando`, ruta del repo de trabajo, y -si es reintento- los hallazgos del verificador o los
controles en FALLA con la ruta de su log.

**Por que no rompe la razon por la que hoy es `general-purpose`.** Ese parrafo rechazaba un agente
**prestado**, que arrastra la metodologia de otro flujo. Un agente propio con `model: inherit` y
`Bash` conserva las tres propiedades que el parrafo pedia -modelo fuerte de la sesion, puede
ejecutar, todo el criterio se lo damos nosotros- y anade la que ya justifico mover el verificador a
agente definido: **la metodologia no se puede parafrasear ni saltar items**, porque no la relata el
orquestador. La frase del paso 5 se reescribe para que se lea asi y no como una incoherencia.

Sus `tools` son `Read, Write, Edit, Bash, Grep, Glob, Skill`: al contrario que el verificador, aqui
`Bash` es el cometido (correr el ciclo TDD y los controles), no una fuga.

Arrastres, todos obligatorios:

- symlink nuevo en la seccion de instalacion del README, y fila nueva en su tabla de piezas.
- el control de subagentes del paso 3 pasa a cubrir **los dos** agentes definidos: hoy solo nombra
  `slice-verifier` como caso de "sin resolver por symlink ausente".
- el gotcha de "los agentes no se releen en caliente" pasa de singular a plural en `CLAUDE.md` y en
  el README: ahora son dos las definiciones que una sesion en curso puede estar usando viejas.

## Decision 2: adelgazar `SKILL.md` moviendo el relato a `references/`

Criterio de corte explicito, para que no degenere en "resumir":

- **Se queda** la regla y **su por que en una frase**. Eso es lo que impide que un agente lea una
  regla desnuda como arbitraria y la "arregle" hacia el lado facil, y es lo que decidio el
  2026-07-28 al escribir las conclusiones en cada skill en vez de solo un puntero.
- **Se va** el relato: que smoke lo descubrio y con que fecha, que alternativas se descartaron y por
  que, la historia del renombrado de "puerta" a "control", las creencias que se refutaron en un
  playground, las cifras de la evidencia empirica citada.

Destino: `skills/slice-runner/references/por-que.md`, **no** `docs/design-notes.md`. El symlink de
instalacion apunta al directorio de la skill, asi que desde otro repo `docs/` no existe y un puntero
ahi seria un enlace roto en el unico momento en que alguien lo seguiria. `references/` viaja con la
skill, como ya hacen `slicing.md` y `observabilidad.md`.

Objetivo medible: de 8.500 palabras a **4.500 o menos**. Con la decision 1, el orquestador se ahorra
del orden de 8k tokens por invocacion.

### Invariantes que el adelgazamiento no puede romper

`tests/test_skill_contracts.py` extrae vocabulario del `SKILL.md`, asi que hay partes que **no son
prosa movible**. Antes de mover nada:

- los cinco marcadores `` `bloqueada: X` `` siguen citados en el `SKILL.md`.
- el paso 9 sigue siendo un `### 9.` con una vineta `- **estado**:` por cada uno de los cinco
  estados de integracion continua.
- sigue habiendo **exactamente un** literal `--veredicto <...>` y **exactamente un** bloque
  ` ```json `, con la misma forma que el de `agents/slice-verifier.md`.
- sigue habiendo **exactamente una** pregunta en negrita con el criterio de degradacion, identica
  palabra por palabra a la de `deploy-watch`, y el `SKILL.md` sigue citando `deploy-watch`.
- toda ruta de este repo citada en backticks -tambien en el `references/por-que.md` nuevo- existe.

## Decision 3: decir la verdad sobre el contexto

Tres afirmaciones se corrigen, en vez de matizarse:

- `README.md`, "Trabajo troceado en rebanadas verticales": el contexto desechable es el de los
  subagentes; el orquestador vive en la sesion de la persona y acumula.
- `README.md`, cierre del ejemplo ("Contexto limpio, `slice-02`"): entre slices, **sesion nueva**.
- `skills/slice-runner/SKILL.md`, principio "Contexto fresco por slice": lo que persiste entre
  slices es el issue, y eso es lo que **permite** tirar la sesion -no lo que hace que se tire sola-.
  Y `/loop` **no** da contexto limpio: reinyecta en la misma conversacion.

## Fuera de alcance, anotado como pendiente

En `docs/design-notes.md`, como decision pendiente de fase 2:

- **Aislamiento mecanico del orquestador**: sacarlo de la sesion (proceso `claude -p` por slice, o
  un orquestador subagente) es la unica forma de que el contexto limpio por slice deje de depender
  de que la persona haga `/clear`.
- **El go/no-go del paso 3 ya es ficcion bajo `/loop`**: nadie responde una alineacion en un run
  desatendido, asi que Nivel 2 ya renuncia de facto a ese control humano. Cualquier diseno de fase 2
  tiene que decidir esto explicitamente en vez de heredarlo por descuido.

## Verificacion

- `make check` verde: incluye los contratos sobre los `.md` y la existencia de las rutas citadas.
- Recuento de palabras del `SKILL.md` <= 4.500.
- El agente nuevo **no se puede probar en la sesion que lo escribe**: el registro de agentes se
  cachea al primer load. Su prueba real es el smoke en sesion nueva.
