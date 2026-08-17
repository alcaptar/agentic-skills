# Seguridad

## Que hace esto en tu maquina

Antes de reportar nada, conviene saber que es lo que se instala. Esto no es una libreria: son skills
de Claude Code y un programa que **conduce agentes sobre tu repo**. Con la instalacion por defecto:

- **Lanza `claude -p`** -llamadas sin estado a Claude Code- que escriben ficheros en el worktree
  donde lo corres, crean ramas y commitean. El merge no lo hace nunca: se para y lo decides tu.
- **Ejecuta los comandos que declara el issue** en su seccion `## Controles` (tipicamente `make
  linting`, `make check-types`, `make test`). Los declara una persona al crear el issue, no los
  deduce ningun agente en tiempo de ejecucion, pero son comandos de tu repo corriendo en tu maquina.
- **Llama a `gh`** con tu sesion autenticada para leer y escribir issues, etiquetas y pull requests
  del repositorio que le indiques.
- **Escribe fuera del repo**, en `~/.claude/slice-runner/`, el rastro de cada llamada y el registro
  durable de metricas.

Nada de eso sale a la red por su cuenta mas alla de la interfaz de programacion de Claude y de la de
GitHub. Si eso no es aceptable en tu entorno, la respuesta es no instalarlo, no configurarlo distinto.

`docs/arranque.md` cuenta el detalle: que teclear, que cuesta y que hace en tu repo sin preguntar.

## Reportar un fallo de seguridad

Usa **Security > Report a vulnerability** en este repositorio (private vulnerability reporting de
GitHub), que abre un aviso privado. No abras un issue publico para eso.

Que ayuda en el reporte: que version o commit, que hace falta para reproducirlo, y que consigue quien
lo explota. Contesto cuando puedo: esto es un proyecto personal, sin acuerdo de nivel de servicio ni
programa de recompensas.

## Que cuenta como fallo de seguridad aqui

- Que una skill o el programa ejecuten algo que el repositorio **no ha declarado** -un comando que no
  sale de `## Controles`, un fichero escrito fuera del worktree y de `~/.claude/slice-runner/`-.
- Que el contenido de un issue, de una pull request o de una respuesta del modelo consiga **cambiar
  el flujo de control** del programa: saltarse un control, forzar un veredicto, mergear.
- Que algo escriba credenciales, tokens o rutas de tu maquina en el registro durable, en un issue o
  en el cuerpo de una pull request.

No cuenta que un agente escriba codigo malo o que el juez se equivoque en un veredicto: eso es la
calidad del pipeline y se discute en un issue normal.
