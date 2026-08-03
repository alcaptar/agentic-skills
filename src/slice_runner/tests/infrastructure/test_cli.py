"""Tests de la linea de comandos: el veredicto por salida estandar y el codigo de salida.

Van de punta a punta con el repo de verdad -el diff se empaqueta con `git`- y con el payload del
harness grabado, que es la unica pieza que se sustituye. Los codigos de salida se escriben como
literales a proposito: son el contrato de la orden, no un detalle del programa.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from slice_runner.infrastructure.cli import build_parser, ejecuta_verificar
from slice_runner.tests.infrastructure.soporte import (
    ProcesoGrabado,
    con_veredicto,
    payload,
    repo_con_slice_staged,
    repo_sin_nada_staged,
)
from slice_runner.tests.repo_de_prueba import RAMA_BASE

_HALLAZGO_ALTA = {
    "regla": "boundaries",
    "path": "mod.py",
    "severidad": "alta",
    "evidencia": "requests en el dominio",
    "detalle": "la I/O va detras de un puerto",
}


def test_un_pasa_sale_con_cero_y_emite_el_veredicto_por_salida_estandar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """El veredicto va a salida estandar como JSON porque lo consume un programa, no una persona."""
    repo = repo_con_slice_staged(tmp_path)
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": []}))

    codigo = ejecuta_verificar(repo=str(repo), base=RAMA_BASE, proceso=proceso)

    assert codigo == 0
    assert json.loads(capsys.readouterr().out) == {"veredicto": "PASA", "hallazgos": []}


def test_un_falla_sale_con_uno_y_emite_los_hallazgos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Los cuatro hallazgos de la llamada grabada tienen que llegar enteros a la salida: quien
    reintenta la slice los necesita, y un veredicto sin hallazgos no dice que arreglar."""
    repo = repo_con_slice_staged(tmp_path)
    proceso = ProcesoGrabado(payload("receta-completa"))

    codigo = ejecuta_verificar(repo=str(repo), base=RAMA_BASE, proceso=proceso)

    assert codigo == 1
    emitido = json.loads(capsys.readouterr().out)
    assert emitido["veredicto"] == "FALLA"
    assert [h["severidad"] for h in emitido["hallazgos"]] == ["alta", "alta", "media", "media"]


def test_un_veredicto_incoherente_sale_con_dos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Un `PASA` con un hallazgo alta cumple el esquema y contradice el contrato.

    Sale con 2 y no con 0 porque lo que hay no es un veredicto: tratarlo como PASA es mergear con
    un hallazgo bloqueante encima de la mesa.
    """
    repo = repo_con_slice_staged(tmp_path)
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": [_HALLAZGO_ALTA]}))

    codigo = ejecuta_verificar(repo=str(repo), base=RAMA_BASE, proceso=proceso)

    assert codigo == 2
    salida = capsys.readouterr()
    assert salida.out == ""
    assert "alta" in salida.err


def test_sin_nada_staged_sale_con_tres_y_no_invoca_al_juez(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Fail-closed antes de gastar una invocacion del harness.

    Y con un codigo propio: confundirlo con el 1 haria pasar un `git add` olvidado por un veto del
    juez, que es la lectura que manda a arreglar el codigo equivocado.
    """
    repo = repo_sin_nada_staged(tmp_path)
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": []}))

    codigo = ejecuta_verificar(repo=str(repo), base=RAMA_BASE, proceso=proceso)

    assert codigo == 3
    assert proceso.llamadas == 0
    assert "staged" in capsys.readouterr().err


def test_una_base_que_no_resuelve_no_sale_con_el_codigo_del_indice_vacio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--base main` en un repo cuya rama es `master` es un flag mal escrito, no un indice vacio.

    Los dos salian con 3 y con el mismo mensaje, asi que quien ramifica por codigo de salida -y eso
    es lo que hara el orquestador- se iba a buscar un `git add` que nunca falto. Una persona lo
    distinguia leyendo el texto de git en stderr; un programa no.
    """
    repo = repo_con_slice_staged(tmp_path)
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": []}))

    codigo = ejecuta_verificar(repo=str(repo), base="no-existe", proceso=proceso)

    assert codigo == 4
    assert proceso.llamadas == 0
    assert "no-existe" in capsys.readouterr().err


def test_un_repo_que_no_resuelve_sale_con_cuatro_sin_culpar_a_la_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un `--repo` que no es un repo git es el mismo error de uso -sale 4-, pero no es la base.

    El mensaje se lee para arreglar la invocacion, asi que afirmar que la base no existe manda a
    corregir el flag que estaba bien mientras el que sobra o falta es el otro.
    """
    fuera_de_git = tmp_path / "no-es-un-repo"
    fuera_de_git.mkdir()
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": []}))

    codigo = ejecuta_verificar(repo=str(fuera_de_git), base=RAMA_BASE, proceso=proceso)

    assert codigo == 4
    assert proceso.llamadas == 0
    assert "el repo o la base" in capsys.readouterr().err


def test_el_juez_recibe_el_diff_de_la_slice_ya_materializado(tmp_path: Path) -> None:
    """El bundle existe en disco cuando el juez lo lee, y trae el cambio del indice.

    Es lo que hace que el juez pueda juzgar sin `Bash`: si el prompt llevara rutas de un bundle
    que nadie escribio, sus `Read` fallarian y el veredicto saldria de la nada.
    """
    repo = repo_con_slice_staged(tmp_path)
    proceso = ProcesoGrabado(payload("receta-completa"))

    ejecuta_verificar(repo=str(repo), base=RAMA_BASE, proceso=proceso)

    rutas = [linea.split(": ", 1)[1] for linea in proceso.entrada.splitlines() if linea.startswith("- `slice.diff`")]
    assert len(rutas) == 1
    diff = Path(rutas[0]).read_text(encoding="utf-8")
    assert "+    return 2" in diff


def test_la_orden_documentada_se_parsea_con_el_repo_y_la_base() -> None:
    """`verificar --repo <ruta> --base <rama>` es la orden que el contrato de la linea de comandos
    fija, asi que renombrar un flag rompe a quien la invoca."""
    args = build_parser().parse_args(["verificar", "--repo", "/repos/proyecto", "--base", "master"])

    assert (args.repo, args.base) == ("/repos/proyecto", "master")


def test_la_base_no_tiene_valor_por_defecto() -> None:
    """Fail-closed: una base adivinada -`master` cuando el repo usa `main`- da un diff que no es el
    de la slice, y el juez lo verifica sin poder notarlo."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["verificar", "--repo", "/repos/proyecto"])
