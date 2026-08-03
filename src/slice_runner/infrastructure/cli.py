"""La linea de comandos del programa: por ahora, verificar una slice ya implementada.

Es tambien el sitio donde se cablean los adaptadores. Nada mas abajo elige implementacion: el caso
de uso recibe sus dos puertos y no sabe que detras hay `git` y `claude`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from slice_runner.application.verificar_slice import VerificarSlice, VerificarSliceParams
from slice_runner.domain.diff import DiffNoEmpaquetableError, RepoOBaseNoResolubleError
from slice_runner.domain.veredicto import Dictamen, VeredictoInvalidoError
from slice_runner.infrastructure.diff import EmpaquetadorGit
from slice_runner.infrastructure.proceso import Proceso, ProcesoLocal
from slice_runner.infrastructure.prompt import RUTA_DEL_PROMPT_DEL_JUEZ, lee_prompt_del_agente
from slice_runner.infrastructure.verificador import VerificadorClaude

SALIDA_POR_DICTAMEN = {Dictamen.PASA: 0, Dictamen.FALLA: 1}
"""Los dos codigos que fija el contrato de la orden: el veredicto es el codigo de salida."""

SALIDA_VEREDICTO_INVALIDO = 2
"""No hay veredicto utilizable: el harness fallo o lo que devolvio incumple el contrato.

Las dos cosas se cuentan juntas aqui porque para quien decide el merge significan lo mismo -no hay
juicio-, y aparte del PASA y del FALLA porque tratarlas como un veredicto es lo unico grave.
"""

SALIDA_SIN_DIFF = 3
"""El indice no traia nada que verificar. Separado del FALLA a proposito: un `git add` olvidado
leido como veto del juez manda a arreglar el codigo equivocado."""

SALIDA_ERROR_DE_USO = 4
"""La invocacion no se sostiene: el repo o la base que se le pasaron no resuelven.

Cubre los dos argumentos porque `git` falla igual con una base que no existe y con un `--repo` que
no es un repo git, sin decir cual de los dos sobra: el codigo de salida es el mismo -revisar la
invocacion- y el mensaje no puede asegurar mas de lo que consta.

Aparte del 3 porque no es un indice vacio -el cambio puede estar entero y staged- y quien ramifica
por codigo de salida en vez de leer stderr se iria a buscar un `git add` que nunca falto. Y aparte
del 2, que afirma que hubo llamada al juez y su respuesta no valia: aqui no se llega a llamarlo.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m slice_runner",
        description="Orquestador de slices. Ver `docs/superpowers/specs/` para el diseno.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    verificar = sub.add_parser("verificar", help="juzga el indice de una slice contra su base")
    verificar.add_argument("--repo", required=True, help="ruta del repo de la slice")
    verificar.add_argument("--base", required=True, help="rama base contra la que se diffea")
    return parser


def ejecuta_verificar(*, repo: str, base: str, proceso: Proceso) -> int:
    """Empaqueta el diff, pide veredicto y lo emite por salida estandar.

    El bundle va a un directorio temporal **fuera** del repo: es material de la verificacion, no
    del cambio, y dentro del arbol acabaria staged en la pull request.

    El `except` de la invocacion que no resuelve va **antes** del de la familia porque es uno de sus
    miembros: al reves lo atraparia el general y el codigo de salida volveria a mentir.
    """
    accion = VerificarSlice(
        empaquetador=EmpaquetadorGit(destino=Path(tempfile.mkdtemp(prefix="slice-runner-"))),
        verificador=VerificadorClaude(proceso=proceso),
    )
    params = VerificarSliceParams(
        repo=repo,
        base=base,
        instrucciones=lee_prompt_del_agente(RUTA_DEL_PROMPT_DEL_JUEZ),
    )
    try:
        veredicto = accion.execute(params)
    except RepoOBaseNoResolubleError as exc:
        print(f"el repo o la base que se pidieron no resuelven: {exc}", file=sys.stderr)
        return SALIDA_ERROR_DE_USO
    except DiffNoEmpaquetableError as exc:
        print(f"no hay diff que verificar: {exc}", file=sys.stderr)
        return SALIDA_SIN_DIFF
    except VeredictoInvalidoError as exc:
        print(f"el juez no dejo un veredicto utilizable: {exc}", file=sys.stderr)
        return SALIDA_VEREDICTO_INVALIDO

    print(json.dumps(veredicto.to_dict(), ensure_ascii=False))
    return SALIDA_POR_DICTAMEN[veredicto.dictamen]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return ejecuta_verificar(repo=args.repo, base=args.base, proceso=ProcesoLocal())
