# El orquestador pasa a ser un programa

Fecha: 2026-07-31. Sustituye el orquestador en prosa de `skills/slice-runner/SKILL.md` por un programa
Python. **Documento de traspaso**: esta escrito para que se pueda implementar en una sesion nueva sin
re-derivar ninguna decision.

Auditoria y mediciones que lo sostienen: `docs/12-factor.md`. Este documento **no repite** los numeros
del spike; los referencia.

## Intencion

Hoy el orquestador son ~600 lineas de prosa que un modelo interpreta **dentro de la sesion de la
persona**. De ahi salen tres cosas que no se arreglan escribiendo mejor prosa:

- **El contexto no se puede gestionar.** El orquestador acumula el run entero y hay que abrir sesion
  nueva a mano entre slices; compactar a mitad deja al orquestador decidiendo con el contexto mutilado,
  que es el fallo que este repo existe para evitar.
- **El estado de ejecucion no existe fuera del contexto.** Los presupuestos (2 reintentos de controles,
  2 de verificacion, 3 ticks de gracia) viven en la cabeza del agente: al reanudar vuelven a cero sin
  que nada avise, una slice `en-curso` no tiene guion de reanudacion, y bajo `/loop` una slice bloqueada
  se re-elige indefinidamente.
- **La logica mas load-bearing del repo depende de que un modelo no se salte una linea.** La secuencia
  de pasos y los presupuestos son prosa, con `selective-hearing` como riesgo permanente, mientras el
  principio declarado del repo es que lo que es regla exacta pasa a script **sin excepciones**.

Si se borra este cambio, lo que queda roto es la promesa de contexto limpio por slice, que hoy solo se
cumple de los subagentes y no del orquestador.

## Lo que NO cambia

- **El criterio de corte por skill**: si el valor esta en la conversacion, sigue siendo skill; si esta en
  el loop, pasa a programa. Por eso `slice-spec` **sigue siendo skill** (su valor es el brainstorming con
  una persona) y `deploy-watch` se queda como esta en esta fase.
- **El encadenado automatico de `deploy-watch`** (preferencia explicita del usuario, registrada en
  `docs/design-notes.md`): se conserva porque un comando con barra **si resuelve** en modo no interactivo
  -verificado-, asi que el programa lo lanza con `claude -p '/deploy-watch <args>'`. Corolario general:
  un programa puede llamar a una skill, asi que el criterio de corte es **composable**.
- **El que implementa no verifica**, los controles deterministas, las convenciones del repo como vara, la
  pull request que cuenta la intencion, y el control humano en merge y rollback.

## Decision 1 — Aislamiento del implementador: worktree con `Bash` libre, declarado

**Worktree con permisos amplios, sin portero y sin contenedor.** Y **declarado por escrito**: la fase 1
es *confiada, no acotada*.

El motivo es una disyuntiva medida (detalle en `docs/12-factor.md`): **correr los tests de un proyecto
es ejecutar codigo arbitrario**, porque `pytest` ejecuta el `conftest.py`, `make` ejecuta el `Makefile` y
`python3` es obvio. De ahi:

| | Ciclo rojo-verde real | Frontera real |
|---|---|---|
| Worktree con `Bash` libre | si | no |
| Sin ejecucion (el orquestador corre los controles) | no | si |
| Portero por lista de comandos | si | no |
| Contenedor | si | si |

- **Sin ejecucion se descarto** porque rompe el ciclo de desarrollo guiado por tests, que es la
  metodologia sobre la que esta construido el repo entero: los controles declarados son de suite
  (`tests: make test`), no por test, asi que cada iteracion costaria la suite completa -veinte minutos en
  un caso real citado en `docs/design-notes.md`-.
- **El portero por lista de comandos se descarto medido**: cayo en un turno con `python3 << 'EOF'`. No es
  un fallo de ese portero concreto, es inherente. Se descarto tambien como guardarrail contra accidentes:
  lo que pararia ya lo cubren `--tools` (le quita las herramientas de red), `pr-hygiene` (caza lo staged
  fuera de lo declarado) y git (recupera lo borrado), y a cambio metia una pieza nueva en el camino de
  cada invocacion mas una sensacion de frontera que no es.
- **El contenedor se descarto para esta fase**, no por su valor -es la unica opcion con las dos
  propiedades- sino porque su coste de entrada bloquea el resto: los repos objetivo corren sus controles
  a traves de Docker, asi que haria falta Docker dentro de Docker o montar el socket (que es equivalente
  a root en el anfitrion), y la autenticacion de suscripcion no viaja al contenedor. **No se escribe
  diseno especulativo de esto**: el puerto es el sitio donde entraria un adaptador distinto, y eso es
  arquitectura hexagonal normal, no un plan.

**El dato que hace aceptable la eleccion**: esta exposicion no la crea el cambio. Hoy el subagente
implementador tambien corre los tests, o sea que tambien ejecuta codigo arbitrario; la unica diferencia
es el prompt de permiso, que bajo `/loop` no contesta nadie. Lo que cambia es que ahora esta escrito.

## Decision 2 — Estado: una subissue por slice

**Una feature = un issue padre + una subissue por slice.** Cambia el principio "una feature = un issue",
escrito hoy en `CLAUDE.md`, `README.md` y `docs/design-notes.md`.

| Donde | Que guarda |
|---|---|
| Issue padre | `## Intencion`, `## Fuentes de convencion`, `## Controles` (por repo). Las slices son sus subissues; la barra de progreso la calcula GitHub |
| Titulo de la subissue | `slice-01 (cantidad-vo): resumen` — id, `name`, `type` y titulo. **El orden se deriva del id del titulo**, no del orden que devuelva la API |
| Cuerpo de la subissue | `INTENCION:`, `ACEPTACION:`, `SENAL:`, `REPO:`, y un bloque de **estado de ejecucion** propiedad de la maquina |
| Etiquetas de la subissue | El **estado macro**: `estado:pendiente`, `estado:en-curso`, `estado:esperando-alineacion`, `estado:esperando-merge`, `bloqueada:controles`, `bloqueada:verify`, `bloqueada:ci-roja`, `bloqueada:ci-indeterminada`, `bloqueada:sin-subagentes`, `abortada:presupuesto` |
| Cerrada | `mergeada`. Lo hace **GitHub** al mergear la pull request con `Closes #<subissue>` |

El reparto load-bearing es **etiquetas para lo que se consulta, cuerpo para lo que se reanuda**: una
transicion de estado pasa a ser una escritura atomica de etiqueta, sin lectura-modificacion-escritura de
ningun documento.

Que gana, y por que no basta con un comentario en el issue actual:

1. **Desaparece una clase de bug entera.** Cada slice escribe solo su cuerpo, asi que el fail-closed de
   `issue_body.py` -que existe porque *"un `gh issue view` que devuelve vacio seguido de un `edit` borra
   la spec entera"*- deja de proteger contra algo posible.
2. **`mergeada` pasa a ser nativo**, asi que el paso final ya no tiene que tickear el merge para
   actualizar estado (solo para encadenar `deploy-watch`).
3. **Las slices bloqueadas se consultan** con `gh issue list --label bloqueada:controles`, que es lo que
   necesita el `max_consecutive_failures` que hoy falta y no se puede hacer sin parsear el cuerpo.
4. **Los comentarios son por slice**, asi que el veredicto de `deploy-watch` va en su slice.

**Soporte verificado** en `gh` 2.96.0: `gh issue create --parent`, `gh issue edit --parent /
--add-sub-issue / --remove-parent`, y en `--json` los campos `parent`, `subIssues` (`{nodes, totalCount}`)
y `subIssuesSummary` (`{completed, percentCompleted, total}`).

**Coste aceptado**: la spec deja de ser un documento que se lee de un tiron. Lo mitiga que `slice-spec`
muestre la spec completa en el terminal antes de crear nada, que es lo que ya hace. **No** se arregla
repitiendo el detalle de las slices en el cuerpo del padre: eso es estado duplicado que deriva.

**Migracion: ninguna.** Los issues abiertos con checklist se terminan con la skill actual y solo despues
se cambia el formato. No se soportan los dos, por el mismo argumento con el que se elimino el Formato B:
*"no aportaba poder expresivo pero si superficie transversal"*.

## Decision 3 — Forma del programa

### La maquina de estados es una funcion pura

```python
def siguiente(run: Run, resultado: Resultado) -> Transicion
```

Sin entrada/salida. Devuelve el paso siguiente, el delta de estado, y el cierre si toca. Los presupuestos
pasan de prosa a un `Presupuestos` frozen. **Es donde van las ~600 lineas del `SKILL.md`**, y lo que
compra no es elegancia: se puede enumerar cada par (paso, resultado) en una tabla de tests.

Consecuencia directa: **desaparece la excepcion confesada de la ventana de gracia de la integracion
continua**. Se dejo en prosa porque *"la ventana es una cuenta entre invocaciones y `ci-status` es de un
tiro y sin estado a proposito"*; ahora hay donde contarla, y `ci-status` sigue sin estado.

### Los puertos

Dos puertos separados para los agentes, no uno: **"el que implementa no verifica" pasa a estar en los
tipos** (firmas, esquemas y conjuntos de herramientas distintos).

| Puerto | Adaptador | Configuracion medida |
|---|---|---|
| `Implementador` | `claude -p` en el worktree | `--permission-mode bypassPermissions --tools 'Read,Write,Edit,Bash,Grep,Glob' --strict-mcp-config` |
| `Verificador` | `claude -p` | `--tools 'Read,Grep,Glob' --strict-mcp-config --json-schema <esquema del veredicto>` |
| `RepositorioDeRun` | `gh` | padre, subissues, etiquetas, comentarios |
| `Controles` | la logica que ya existe | invocada como modulo, no como subproceso |
| `Git` | subproceso | rama, stage, commit, push |
| `Foro` | `gh` | pull request y comentarios |
| `RegistroDeMetricas` | `metrics.py` | con coste real del JSON del harness |

**Los flags son variadicos y se tragan el prompt posicional**: forma con comas y prompt por entrada
estandar, siempre.

Los prompts (`agents/slice-implementer.md`, `agents/slice-verifier.md`) pasan a ser **entradas de una
llamada**, leidas por el adaptador. Eso hace el factor 2 de verdad -versionados y evaluables- y **elimina
el gotcha** que `CLAUDE.md` documenta: ya no hay registro de agentes cacheado ni symlink a
`~/.claude/agents/`, asi que editar un prompt ya no exige sesion nueva para probarlo.

### Que sobrevive y que muere

- **Sobrevive con sus tests**: la logica pura de `controles.py` (`clasifica_ci`, ejecutar controles,
  `pr-hygiene`, `diff-bundle`), `metrics.py`, y `deploy_core.py` intacto. `discover_controles.py` y
  `discover_conventions.py` siguen sirviendo a `slice-spec`.
- **Muere**: el parser del checklist de `issue_body.py` y la prosa de orquestacion del `SKILL.md`.
- **`verify-verdict` NO queda obsoleto**: `--json-schema` garantiza la **forma**, no la **coherencia**, y
  un `PASA` que convive con un hallazgo `alta` es valido contra el esquema. Conserva los checks
  semanticos y pierde solo el de la prosa envolvente.

### Donde se gana la confianza

Cambia de sitio: la mayor parte pasa a tests offline exhaustivos sobre la maquina de estados pura, y el
smoke se queda con lo que solo el puede ver -entrada/salida real contra `gh`, integracion continua de
verdad, y el JSON real de `claude -p`, del que el spike dejo payloads grabados para fixtures-.

Adaptadores con `create_autospec(spec_set=True)` sobre los puertos. Lo que llega de fuera -el JSON del
harness- se valida al entrar con un `from_dict` que rechaza clave desconocida y tipo equivocado, como ya
hacen `deploy_core` y `metrics`. **Nada de `cast`.**

## Decision 4 — Contacto humano durable

En un programa no hay chat, asi que el "espera go/no-go" del paso 3 hay que rediseñarlo. El gate hacia
**dos cosas** y solo una necesita a una persona.

**Mitad determinista, siempre, sin pausa** (lo que cazo el gate en el dry-run real que
`docs/design-notes.md` registra -una slice ya mergeada- no era un juicio):

- ¿la subissue ya esta cerrada?
- ¿existe ya la rama `slice/NN-<name>`?
- ¿hay ya una pull request abierta que la referencia?
- ¿faltan fuentes de convencion o controles para el repo de la slice? (ya es fail-closed)

**Mitad de juicio**: el entendimiento del agente se escribe **siempre** como comentario en la subissue.
Eso desacopla producir el artefacto de esperar por el, y hace que en cualquier run se pueda leer despues
que entendio -hoy imposible: vive en un chat que se tira-.

**Solo se construye el camino que bloquea**: etiqueta `estado:esperando-alineacion`, se asigna la
subissue al usuario (GitHub notifica, factor 11 sin construir canales) y el programa **sale**. Reanuda
cuando se responde. **No se construye el modo desatendido**, ni como flag: sin el, el Nivel 2 no se
puede activar por descuido, que es lo que pide `docs/maturity-map.md`.

**El merge ya es durable** y no hay que tocarlo. Pero cae una regla cuyo motivo desaparece: la
prohibicion de esperas bloqueantes existia porque una shell colgada congela la **sesion del agente**; en
un programa un bucle de sondeo es normal y no cuesta contexto. **Se relaja para el orquestador y se
escribe como consecuencia**, porque una regla que sigue escrita cuando su razon ya no aplica es de las que
se "arreglan" en la direccion equivocada. Se mantiene el tope de tiempo total.

**Lo que se pierde**: dejas de poder hablarle a mitad de ejecucion. Es un cambio real de ergonomia y es
el precio de que el contexto sea manejable. Lo que queda en su lugar son artefactos sobre los que hablar
despues, y la conversacion se concentra en `slice-spec`.

## Decision 5 — Las tres que estaban aparcadas

**Pre-flight de controles: la decision de `docs/design-notes.md` se mantiene sin cambios.** Se rechazo
para no añadir heuristica, y un programa **no** la hace determinista: comprobar que un comando declarado
arbitrario resuelve exige conocimiento por toolchain (`make -n` no sirve para `uv run pytest` ni para
`tox`), que es justo lo que el repo se niega a tener en tiempo de ejecucion. Se sigue cazando en
`slice-spec validate`, y una slice quemada sigue siendo el precio aceptado.

**`--descartes-verify` se estrecha, no se quita.** El esquema mata el modo de fallo de la prosa
envolvente, pero no el del veredicto **incoherente** (`PASA` con un hallazgo `alta`), ni el de la llamada
fallida del harness. Se **conserva la clave** del log durable -renombrar no puede borrar historico, como
ya paso con `puertas`- y se añade un campo de **causa** opcional, para distinguir las dos de aqui en
adelante sin romper la serie vieja. `from_row` acepta su ausencia en los registros antiguos.

**El hook observador no se construye.** Queria cerrar el punto ciego que el paso 6 declara -*"no ves sus
tool calls, solo su mensaje final en prosa"*- pero hay una via sin pieza nueva en el camino critico:
**`--output-format stream-json`** en la llamada al implementador. **A verificar al construir**: no se ha
medido. Y no elimina el backstop de los controles, cuya razon es que el auto-reporte no es fuente de
verdad.

## Alcance de la fase 1

**Dentro:**

- El programa orquestador: maquina de estados, los siete puertos, los dos adaptadores de `claude -p`,
  el repositorio de subissues, los prechecks deterministas y la pausa de alineacion.
- **`slice-spec` adaptada** para crear padre y subissues. No es opcional: sin eso nada produce el formato
  que el programa lee.
- **Registrar cada par (diff, veredicto)** de cada run real. Una linea ahora; es el corpus de los evals
  del juez construyendose gratis, y retrofitearlo despues significa reconstruirlo a mano.
- Entrypoint de linea de comandos con `uv`, mas un enlace en `~/.local/bin`. **Sigue siendo verdad que la
  rama en la que estas decide que codigo corre**, y hay que escribirlo donde se instala.

**Fuera**, dicho para que nadie lo asuma incluido: `deploy-watch` como programa, el aislamiento por
contenedor, el modo desatendido, los niveles 2 y 3, y los evals del juez (solo se recoge su corpus).

**Como se construye**: con el `slice-runner` actual, sobre un issue en formato checklist. Lo ultimo que
hace la herramienta vieja es construir su reemplazo, y de paso es la prueba real que le faltaba. Cuando
el programa este verde se cambia el formato y la skill vieja se borra.

## Lo que hay que verificar al construir

Ninguna cambia una decision; todas cambian detalles de implementacion.

1. Que campos trae de verdad `subIssues.nodes`, y si el padre y las slices salen en una llamada o en dos.
2. Que `--output-format stream-json` da las tool calls del implementador de forma parseable.
3. Que `claude -p '/deploy-watch <args>'` funciona con argumentos reales (el mecanismo esta verificado;
   la invocacion concreta no).
