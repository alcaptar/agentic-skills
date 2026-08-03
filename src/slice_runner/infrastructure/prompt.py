"""Los prompts de los agentes, leidos de su fichero versionado.

Que el prompt sea una **entrada de la llamada** y no un agente registrado en la sesion es lo que
elimina el gotcha que `CLAUDE.md` documenta: el registro de agentes se cacheaba al primer load, asi
que editar un prompt exigia sesion nueva para probarlo. Leido aqui, el fichero es la version que
corre.
"""

from __future__ import annotations

import re
from pathlib import Path

RUTA_DEL_PROMPT_DEL_JUEZ = Path(__file__).resolve().parents[3] / "agents" / "slice-verifier.md"
"""El prompt del juez adversarial dentro de este repo.

Sigue siendo verdad que la rama en la que estas decide que codigo corre, y con esta ruta tambien
que prompt: se resuelve relativa al fichero, no al directorio desde el que se invoque.
"""

_CABECERA = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
"""La cabecera YAML de un agente definido. Anclada al principio para que un `---` que aparezca mas
abajo -un separador cualquiera del documento- no se lleve por delante media rubrica."""


def lee_prompt_del_agente(path: Path) -> str:
    """El cuerpo del prompt, sin la cabecera de configuracion.

    La cabecera declaraba `name`, `description`, `model` y `tools` para el registro de agentes, y en
    esta invocacion no configura nada: las herramientas las concede `--tools`
    (`argv_del_verificador`, que las mantiene alineadas con lo que la cabecera declara) y el modelo
    es el que traiga por defecto la linea de comandos, porque la llamada no lo fija. Pasarla como
    instrucciones seria darle al juez ordenes que no lo son.
    """
    return _CABECERA.sub("", path.read_text(encoding="utf-8")).strip()
