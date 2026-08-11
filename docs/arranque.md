# Arranque

Que teclear para usar esto por primera vez. El **por que** esta en `README.md`; las reglas de codigo,
en `docs/conventions/`.

Una idea se trocea en rebanadas con criterios de aceptacion, que viven en un issue de GitHub (uno
padre, una subissue por rebanada). `slice-runner` coge una, ensena lo que ha entendido, espera tu
visto bueno, implementa, la juzga otro agente distinto, abre pull request y para. **El merge lo
decides tu.** Una rebanada cuesta entre 1 y 11 dolares de tu cuota de Claude.

## Prerequisitos

Este repo no los instala:

| | |
|---|---|
| `uv` | Toolchain de Python. Sin el, `make install` falla |
| `gh` autenticado | `gh auth login` |
| `claude` | Claude Code, con suscripcion que pague las llamadas |
| Plugin `superpowers` | Lo invoca `slice-spec` en su primer paso |
| Acceso de lectura a este repo | Es privado |

## Instalar

```bash
git clone git@github.com:alcaptar/agentic-skills.git
cd agentic-skills
make install
slice-runner doctor
```

Si `doctor` sale con codigo distinto de cero, arregla lo que diga antes de seguir: imprime el comando.

## El ciclo

En el repo donde vas a trabajar:

| | |
|---|---|
| 1 | `/slice-spec` en una sesion de Claude Code. Ensena la spec por terminal antes de crear nada |
| 2 | `slice-runner run <issue-padre> --repo <org>/<repo> --base master [--slice slice-NN]` |
| 3 | Publica lo que ha entendido en la subissue. Contesta en otro comentario: `-GO`, o `-REVIEW <correccion>` |
| 4 | Implementa, controles, juez, pull request, integracion continua |
| 5 | `gh pr ready <n>` y `gh pr merge <n> --merge --delete-branch` |

- El numero del paso 2 es el del issue **padre**, no el de la subissue. Pasar el de una subissue no
  falla con un mensaje util: sale con "no queda ninguna rebanada" (codigo 9).
- `--slice slice-NN` elige cual conducir. Sin el, coge la siguiente ejecutable en orden.
- `-GO` se lee por coincidencia exacta: con texto detras **no arranca**. Con varias respuestas, gana
  la ultima escrita.
- Las pull requests nacen en borrador. Reinvocar no las saca de ahi.

## Permisos

El implementador corre con `--permission-mode bypassPermissions` y con `Bash` en el repo que le
indiques. Sin preguntar: escribe y borra ficheros, ejecuta comandos, crea ramas, commitea, empuja,
crea etiquetas, abre pull requests y comenta en la subissue.

Nunca: mergear ni hacer rollback.

## Cuando parezca roto

| Sintoma | Que es |
|---|---|
| Codigo de salida 7 | Se agoto la espera (30 min). Reinvoca: retoma donde estaba |
| Parece parado | Espera tu `-GO`, la integracion continua o el merge. Mira la etiqueta de la subissue |
| La pull request no se mergea sola | Correcto: el merge lo decides tu |
| Otro codigo de salida | Tabla en `README.md`, apartado "El paso que ya es un programa" |

El estado vive en el issue: puedes cerrar el terminal y reinvocar manana. Si mergeas por tu cuenta
mientras espera, la siguiente invocacion lo detecta y cierra la rebanada.

## La trampa

`--base master` resuelve tu rama **local**. Si esta atrasada, la rebanada nace de un arbol viejo y se
mide con las convenciones viejas de ese arbol: no falla nada y no avisa nadie.

Comprueba antes de lanzar, y ponla al dia si hace falta:

```bash
slice-runner doctor --repo <org>/<repo> --worktree . --base master
```
