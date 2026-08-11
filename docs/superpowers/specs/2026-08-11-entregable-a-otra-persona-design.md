# El proyecto se puede dar a otra persona

Fecha: 2026-08-11. **Documento de traspaso**: esta escrito para que se pueda implementar en una sesion
nueva sin re-derivar ninguna decision.

Vara de exito, fijada por el usuario: **un companero de Mercadona conduce una slice en su propio repo**
-escribe la spec con `/slice-spec`, lanza el run, ve el entendimiento, da el `-GO`, y acaba con una pull
request-. No basta con que instale ni con que entienda leyendo: tiene que conducir.

## Intencion

Hoy este proyecto no se le puede dar a nadie. No hay un comando de instalacion, no hay forma de saber si
el entorno esta listo antes de gastar dinero, y no hay ninguna pagina que diga que teclear el primer dia.
Lo unico que existe es un README que explica el **por que** y una seccion de instalacion que describe los
symlinks de las skills, no del programa.

Y hay una consecuencia mas silenciosa: **esto nunca se ha ejecutado fuera de este repo**. Las
convenciones, la rubrica del juez y los scripts de descubrimiento estan afinados aqui. Mientras no haya
forma barata de que otra persona lo lance sobre otro repo, no hay forma de saber si el pipeline generaliza
o si esta acoplado al sitio donde nacio.

Si se borra este cambio, lo que queda imposible es la primera ejecucion de este programa por alguien que
no lo escribio.

## Lo que NO cambia

- **El estado del run vive en el issue de GitHub.** Nada de lo que hay aqui introduce una segunda fuente
  de verdad.
- **El merge y el rollback los decide la persona.**
- **El flujo y la maquina de estados.** Este documento no toca `RunState`, `Step`, `IssueLabel`, ni el
  canal de texto del `-GO`. La interfaz para los puntos de intervencion humana es el tema **siguiente**,
  y esta separada a proposito: empaquetar primero significa aceptar que la guia de arranque describira un
  flujo que va a cambiar.
- **Las skills siguen siendo symlinks vivos** desde el checkout. Editar el repo sigue cambiando el
  comportamiento de Claude Code al instante.

## Decision 0 — Entregable antes que interfaz, aunque haya que reescribirlo

Hay dos proyectos independientes: **entregable** (instalacion, prerequisitos, documentacion de arranque) e
**interfaz** (botones en los puntos de intervencion humana). No dependen uno del otro.

Se hace **primero el entregable**, decidido por el usuario con el motivo explicito de tener algo que
mostrar cuanto antes, aceptando que luego haya que cambiarlo.

Queda registrado el argumento contrario, que se descarto: la guia de arranque que se escriba ahora
describira los tokens `-GO` que quiza dejen de existir, asi que parte de este trabajo se reescribira.

## Decision 1 — Se distribuye clonando el repo, no como paquete suelto

**Un `git clone` mas un `make install`.** No se empaqueta las skills dentro de la rueda, ni se distribuye
por el mecanismo de plugins de Claude Code.

El motivo es de sincronizacion, no de esfuerzo. El entregable son **dos mitades que se instalan de formas
distintas**: el programa es una rueda de Python (`pyproject.toml` empaqueta `src/slice_runner`) y las
skills son ficheros que viven en `~/.claude/skills`. Meter las skills en la rueda obliga a decidir
versionado y rompe la propiedad de que son symlinks vivos, justo mientras se estan cambiando a diario
-diez slices abiertas tocan este flujo-. El clon no introduce ese problema, y si en dos semanas el camino
resulta ser la interfaz, no se ha tirado nada.

Lo que se pierde y se acepta: la unidad de distribucion sigue siendo un `git clone` de un repo privado, o
sea que no es "un paquetito".

Alternativas descartadas, con su motivo:

| Alternativa | Por que no |
|---|---|
| Skills dentro de la rueda mas `slice-runner install` | Obliga a versionado y rompe los symlinks vivos en el momento de maxima inestabilidad |
| Plugin de Claude Code para las skills | Es el mecanismo correcto a largo plazo, pero hoy no da nada que el clon no de |

## Decision 2 — `uv tool install` es comodidad, no habilitador

Se instala el programa como herramienta (`uv tool install .`), y hay que decir con precision **que compra
eso**, porque la primera lectura era falsa.

**No** habilita conducir slices de otros repos: todo el programa esta parametrizado por `--worktree` -
`git -C` en `git_workspace.py:46`, `cwd=repo` en `local_control_runner.py:23`-, asi que hoy ya se puede
conducir una slice de otro repo desde este checkout.

Lo que compra son dos cosas: que quien lo usa **no tenga que saber donde vive el checkout**, y que no le
muerda "la rama en la que estas decide que codigo corre", que es una propiedad util para quien desarrolla
el programa y una trampa para quien solo lo usa.

## Decision 3 — `make install` para las dos mitades, e idempotente de verdad

Un target nuevo que hace tres cosas:

```
uv tool install .                                  # slice-runner en el PATH
ln -s $PWD/skills/slice-spec    ~/.claude/skills/  # autoria de specs
ln -s $PWD/skills/deploy-watch  ~/.claude/skills/  # se encadena al mergear
```

Dos exigencias sobre el target:

- **Si un symlink ya existe apuntando a otro sitio, lo dice y para.** No lo sobrescribe: quien ya tenga
  algo montado ahi lo tiene montado por una razon, y esta el caso real del symlink de `slice-runner`
  apuntando a `agentic-skills-legacy`.
- **Respeta `CLAUDE_CONFIG_DIR`** si esta puesto, igual que el programa (`claude_config.py:14`). Si no, el
  target miente en cuanto alguien lo use con la configuracion movida.

`deploy-watch` entra y **no es opcional**: al mergear una slice con `SENAL:` no exenta, el programa lanza
`claude -p` con `/deploy-watch` (`deploy_watch_invocation.py`), y sin la skill esa llamada se gasta sin
hacer nada y nadie se entera.

## Decision 4 — `slice-runner doctor`, un subcomando y no un script

La disposicion del entorno se comprueba con un **subcomando del programa**, no con un script de `skills/`.
El motivo: es la disposicion del propio programa, y su **codigo de salida es el contrato** -la misma razon
por la que lo mecanico de este repo vive en cosas cuyo exit code es autoritativo-.

```
$ slice-runner doctor --repo mercadona/mi-servicio --worktree . --base master
listo   git                    2.51.0
listo   gh                     autenticado como acapdev
listo   acceso al repo         mercadona/mi-servicio
listo   claude                 2.1.4
listo   skill slice-spec       ~/.claude/skills/slice-spec
falta   skill deploy-watch     no esta en ~/.claude/skills
        ln -s <checkout>/skills/deploy-watch ~/.claude/skills/deploy-watch
aviso   base master            3 commits por detras de origin/master
        git -C . branch -f master origin/master
```

### Los tres argumentos son opcionales

`--repo`, `--worktree` y `--base` son **opcionales**, al contrario que en `run`. Sin ellos se corren solo
los chequeos que no necesitan un repo -los ejecutables y las skills-, que es justo lo que hace falta la
primera vez: comprobar si esto se puede instalar **antes** de tener un issue con el que probarlo. Con
ellos se anaden el acceso al repo y el estado de la base.

### Tres veredictos, y la diferencia importa

- **`listo`** — comprobado.
- **`falta`** — impide conducir. Hace que el subcomando salga con un codigo de salida propio.
- **`aviso`** — deja conducir, pero es lo que arruina un run sin que nadie entienda por que.

El `aviso` del ejemplo no es decorativo: **`--base master` resuelve la rama local**, asi que con la base
atrasada la slice nace de un arbol viejo **y se mide con las convenciones viejas**. Costo dinero real en
la sesion del 2026-08-11 y es exactamente lo que un recien llegado no puede diagnosticar, asi que el
chequeo entra en la primera version y no en una segunda.

### Que comprueba

| Chequeo | Como | Veredicto si falla |
|---|---|---|
| `git` disponible | version | falta |
| `gh` disponible y autenticado | version, mas quien es el usuario | falta |
| Acceso de lectura al repo del issue | leer el repo por `gh` | falta |
| `claude` disponible | version, **no** una llamada real: una llamada cuesta dinero | falta |
| `skills/slice-spec` en la configuracion de Claude Code | esta el directorio | falta |
| `skills/deploy-watch` en la configuracion de Claude Code | esta el directorio | falta |
| La base no esta por detras de su remoto | comparar la rama local con `origin/<base>` | aviso |

### El doctor no arregla nada

Imprime el comando y se calla. Arreglar el entorno de otra persona sin preguntar no es lo que hace este
repo, y un doctor que escribe es un doctor en el que no se puede confiar para diagnosticar.

### Forma en capas

- **Dominio**: `Readiness` y `ReadinessCheck` como objetos de valor, `CheckVerdict` como vocabulario
  cerrado con los tres veredictos.
- **Aplicacion**: un caso de uso de consulta que compone los chequeos y devuelve `Readiness`.
- **Puertos**: `Forum` gana "quien soy" y "puedo leer este repo"; `Branches` gana "esta rama esta por
  detras de su remoto"; `SkillLibrary` ya sabe mirar la configuracion de Claude Code
  (`local_skill_library.py`); y hace falta **un puerto nuevo** para "¿existe este ejecutable y que version
  trae?".
- **Infraestructura**: el subcomando en `Subcommand`, el cableado en `cli.py`, y **un codigo de salida
  nuevo** en `ExitCode` para "el entorno no esta listo" -no se reutiliza `USAGE_ERROR`, que significa otra
  cosa: la invocacion estaba mal escrita-.

## Decision 5 — La guia de arranque es un documento nuevo, con su fila en la tabla de lectores

`docs/arranque.md`, apuntado desde arriba del `README.md`. La seccion `## Instalacion` actual del README se
convierte en **puntero**, para que no haya dos verdades sobre como se instala.

Y una **fila nueva en la tabla "Quien lee cada cosa"** del `CLAUDE.md`: esta guia no es una convencion ni
una nota de diseno, la lee **quien va a usar esto por primera vez**. Esa tabla existe justo para que no se
confundan las cuatro clases de documento, y anadir un quinto lector sin declararlo es reintroducir la
confusion que la tabla resuelve.

Contenido, en este orden:

1. **Que es y que te va a costar**, en tres frases. Una slice cuesta entre 1 y 15 dolares **de tu cuota**.
2. **Prerequisitos**, comprobables con `slice-runner doctor`.
3. **Instalacion**: `git clone` mas `make install`.
4. **El primer ciclo, teclado**: `/slice-spec` en tu repo -> `slice-runner run N --repo … --base …` ->
   responder `-GO` al comentario del entendimiento -> esperar -> `gh pr ready N` y mergear tu.
5. **Lo que hace en tu repo sin preguntar.** El implementador corre con `--permission-mode
   bypassPermissions` y con `Bash` (`implementer_invocation.py:36`): escribe ficheros, crea ramas, crea
   etiquetas, hace commits, empuja y abre pull requests. Y lo que **no** hace nunca: mergear. Esto va en
   voz alta y con su nombre, no enterrado.
6. **Que esperar cuando parece roto**: sale con codigo 7 tras 30 minutos esperando tu `-GO`
   (`Budgets.total_wait_seconds`) y se relanza; las pull requests nacen en draft y hay que sacarlas con
   `gh pr ready`.
7. **La tabla de codigos de salida.**

## Como se mide

- **El doctor**, con tests unitarios normales: dobles por `create_autospec(spec_set=True)` y mothers para
  los objetos de valor nuevos, como el resto de `src/slice_runner/tests/`.
- **Los symlinks de `make install`**, con un test marcado `integration` que apunta `CLAUDE_CONFIG_DIR` a un
  `tmp_path` y comprueba donde caen. Incluye el caso de un symlink preexistente apuntando a otro sitio.
- **El `uv tool install .` no se testea**, y queda declarado: instalar en el entorno de la maquina no cabe
  en la suite.
- **Dos cosas salen gratis** y no hay que escribirlas: `test_pipeline_invariants.py` ya comprueba que toda
  ruta de este repo citada en un `.md` existe, asi que vigila la guia sola; y la tabla de codigos de salida
  de la guia es un contrato escrito dos veces, que es lo que `test_skill_contracts.py` compara.

## Fuera de alcance, a proposito

- Versionado y publicacion en un indice de paquetes.
- Plugin de Claude Code.
- Cualquier interfaz, de escritorio o de terminal.
- Preparar el repo del companero: las etiquetas `estado:*` **se crean solas**
  (`gh_run_repository.py:212`), y las convenciones y los controles los descubre `/slice-spec` con el
  confirmandolos.
- Que el doctor arregle algo.

## Como se construye

Partido, por lo que cada mitad puede acreditar:

- **El doctor es una slice.** Tiene dominio, aplicacion, infraestructura y criterios de aceptacion
  falsables, y conducirla ensaya justo el flujo que se quiere entregar.
- **`make install` y la guia van a mano, en una pull request de documentacion.** No tienen criterio
  falsable ni senal, y pasarlos por el pipeline es pagar un implementador y un juez para redactar prosa.
