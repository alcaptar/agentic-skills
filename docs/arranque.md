# Arranque

Que teclear para usar esto por primera vez. El **por que** está en `README.md`; las reglas de código,
en `docs/conventions/`.

Una idea se trocea en rebanadas con criterios de aceptación, que viven en un issue de GitHub (uno
padre, una subissue por rebanada). `slice-runner` coge una, ensena lo que ha entendido, espera tu
visto bueno, implementa, la juzga otro agente distinto, abre pull request y para. **El merge lo
decides tu.** Una rebanada cuesta entre 1 y 11 dolares de tu cuota de Claude.

## Prerequisitos

Este repo no los instala:

| | |
|---|---|
| `uv` | Toolchain de Python. Sin el, `make install` falla |
| `gh` autenticado | `gh auth login` |
| `claude` | Claude Code, con suscripción que pague las llamadas |
| Plugin `superpowers` | Lo invoca `slice-spec` en su primer paso |
| Acceso de lectura a este repo | Es privado |

## Instalar

```bash
git clone git@github.com:alcaptar/agentic-skills.git
cd agentic-skills
make install
slice-runner doctor
```

Si `doctor` sale con código distinto de cero, arregla lo que diga antes de seguir: imprime el comando.

## El ciclo

En el repo donde vas a trabajar:

| | |
|---|---|
| 1 | `/slice-spec` en una sesión de Claude Code. Ensena la spec por terminal antes de crear nada |
| 2 | Desde la raíz del clon: `slice-runner run <issue-padre> --repo <org>/<repo> --base master [--slice <identificador>]` |
| 3 | Publica lo que ha entendido en la subissue y **termina** con el código 17. Contesta con `slice-runner go <subissue> --repo <org>/<repo>`, o con `slice-runner review <subissue> --repo <org>/<repo> <correccion>`; un comentario `-GO` o `-REVIEW <correccion>` sigue valiendo |
| 4 | Vuelve a lanzar el paso 2. Con `go` implementa; con `review` rehace el entendimiento, lo publica y vuelve a parar |
| 5 | Implementa, controles, juez, pull request, integración continua |
| 6 | `gh pr ready <n>` y `gh pr merge <n> --merge --delete-branch` |

- El número del paso 2 es el del issue **padre**, no el de la subissue. Pasar el de una subissue no
  falla con un mensaje útil: sale con "no queda ninguna rebanada" (código 9).
- El programa monta el worktree de la rebanada en `.worktrees/<NN-nombre>`, colgando de la raíz del clon, y
  no hace falta decirle dónde. Si lo lanzas desde otro directorio, `--repo-root <ruta>` señala el clon;
  `--worktree <ruta>` solo es para un árbol montado a mano. Si la rama ya la tiene tomada otro árbol, el run
  se cierra en `bloqueada:worktree` y dice en qué ruta está el conflicto.
- Al cerrar, el programa retira el worktree y su rama local solo si el run se fusionó, o abortó sin haber
  tocado código, **y** el árbol no tiene nada sin comitear ni commits que solo existan en local. Si algo de eso
  falla, o no se puede comprobar, el árbol se queda: el comentario de cierre y la fila de métricas dicen en qué
  ruta y por qué. Un árbol que sobra de un run anterior no se reutiliza ni se pisa: la invocación siguiente se
  cierra en `bloqueada:worktree-sin-retirar` con el comando para quitarlo a mano (`git worktree remove <ruta>`).
- `--slice <identificador>` elige cual conducir; sin el, coge la siguiente ejecutable en orden. El
  identificador es `slice-NN`, o `<CLAVE>-NN` (`STAFF-124-01`) si la feature declara historia de
  usuario: con clave, pedir `slice-NN` falla diciendo que esa slice no existe.
- `go`, `review` y `retry` escriben la orden en el estado del run y dejan un comentario en la subissue que
  dice qué orden se dio. No lanzan el run ni invocan al modelo. Dos `review` seguidos dejan solo la segunda
  corrección. Una orden sobre una slice que no está en el estado que necesita sale con el código 18 y no
  escribe nada.
- Los comentarios siguen valiendo como segunda vía, y se leen en el siguiente `run`, no mientras espera:
  `-GO` se lee por coincidencia exacta -con texto detrás **no arranca**-, `-REVIEW <correccion>` pide
  rehacer el entendimiento y `-RETRY <instruccion>` reabre una slice bloqueada. Con varias respuestas, gana
  la última escrita.
- Las pull requests nacen **listas para revisar** y **asignadas a ti**, con los commits acreditando a
  Claude como co-autor. Mergear sigue siendo tuyo: el programa nunca mergea.

## Permisos

El implementador corre con `--permission-mode bypassPermissions` y con `Bash` en el repo que le
indiques. Sin preguntar: escribe y borra ficheros, ejecuta comandos, crea ramas, commitea, empuja,
crea etiquetas, abre pull requests y comenta en la subissue.

Nunca: mergear ni hacer rollback.

## Cuando parezca roto

| Síntoma | Que es |
|---|---|
| Código de salida 7 | Se agoto la espera (30 min). Reinvoca: retoma donde estaba |
| Código de salida 17 | Espera tu orden: `go` o `review` -o un comentario `-GO` o `-REVIEW`-. Reinvocar sin darla termina igual |
| Parece parado | Espera tu `go`, la integración continua o el merge. Mira la etiqueta de la subissue |
| La pull request no se mergea sola | Correcto: el merge lo decides tu |
| Otro código de salida | Tabla en `README.md`, apartado "El paso que ya es un programa" |

El estado vive en el issue: puedes cerrar el terminal y reinvocar mañana. Si mergeas por tu cuenta
mientras espera, la siguiente invocación lo detecta y cierra la rebanada.

## La trampa

`--base master` resuelve tu rama **local**. Si esta atrasada, la rebanada nace de un árbol viejo y se
mide con las convenciones viejas de ese árbol: no falla nada y no avisa nadie.

Comprueba antes de lanzar, y ponla al día si hace falta:

```bash
slice-runner doctor --repo <org>/<repo> --worktree . --base master
```
