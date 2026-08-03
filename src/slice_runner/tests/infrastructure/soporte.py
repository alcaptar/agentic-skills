"""Soporte de los tests de infraestructura: payloads grabados, doble de proceso y repos de prueba.

Vive aparte porque lo comparten dos ficheros de test, y un doble copiado en los dos deriva. No es
un `conftest.py` porque nada de esto es una fixture de pytest: son un cargador, una clase y un
constructor de escenario que se llaman explicitamente.
"""

from __future__ import annotations

import json
from pathlib import Path

from slice_runner.infrastructure.proceso import Proceso, SalidaDeProceso
from slice_runner.tests.repo_de_prueba import git, inicializa_repo

_PAYLOADS = Path(__file__).parent / "payloads"

GRABADOS = ("receta-completa", "sin-acotar-herramientas")
"""Los dos payloads del spike: la receta completa de flags y la misma llamada sin acotar
herramientas. Se leen los dos porque la forma del sobre no depende de los flags, y si algun dia
depende hay que enterarse aqui."""


def payload(nombre: str) -> dict[str, object]:
    """Un payload grabado, tal cual salio de `claude -p --output-format json`."""
    datos = json.loads((_PAYLOADS / f"{nombre}.json").read_text(encoding="utf-8"))
    assert isinstance(datos, dict)
    return datos


def con_veredicto(estructura: dict[str, object], *, grabado: str = "receta-completa") -> dict[str, object]:
    """Un payload real con otro veredicto dentro, para cubrir las ramas que el spike no grabo.

    La mutacion queda a la vista en el test en vez de guardarse como un fichero que aparenta
    haberse grabado; el sobre sigue siendo el medido.
    """
    return dict(payload(grabado)) | {"structured_output": estructura}


class ProcesoGrabado(Proceso):
    """Devuelve un payload ya grabado y recuerda con que lo llamaron.

    Sustituye solo el salto al proceso externo: la receta de flags, la composicion del prompt y la
    lectura del sobre siguen siendo las de produccion.
    """

    def __init__(self, salida: dict[str, object], *, codigo: int = 0) -> None:
        self._salida = salida
        self._codigo = codigo
        self.argv: list[str] = []
        self.entrada = ""
        self.llamadas = 0

    def corre(self, argv: list[str], *, entrada: str) -> SalidaDeProceso:
        self.argv = argv
        self.entrada = entrada
        self.llamadas += 1
        return SalidaDeProceso(codigo=self._codigo, stdout=json.dumps(self._salida), stderr="")


def repo_con_slice_staged(raiz: Path) -> Path:
    """Un repo con un commit de base y el cambio de la slice en el indice, sin commitear.

    Es el estado exacto en el que se verifica: el commit va **despues** del veredicto, asi que lo
    que hay que poder diffear es el indice contra la base.
    """
    repo = inicializa_repo(raiz / "repo")
    (repo / "mod.py").write_text("def f() -> int:\n    return 1\n", encoding="utf-8")
    git(repo, "add", "mod.py")
    git(repo, "commit", "-m", "base")
    git(repo, "switch", "-c", "slice/01-x")
    (repo / "mod.py").write_text("def f() -> int:\n    return 2\n", encoding="utf-8")
    git(repo, "add", "mod.py")
    return repo


def repo_sin_nada_staged(raiz: Path) -> Path:
    """El mismo repo con el indice limpio: el sintoma de haberse olvidado el `git add`."""
    repo = repo_con_slice_staged(raiz)
    git(repo, "reset", "--hard")
    return repo
