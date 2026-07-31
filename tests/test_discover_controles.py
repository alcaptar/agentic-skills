"""Tests del descubrimiento de candidatos a control (discover_controles.py).

El helper NO decide: lista lo que el arbol deja ver para que el agente lo filtre y la
persona lo confirme. Lo que se testea es que no invente, que no se deje targets reales, y
que lo que descarta lo descarte por una razon (no es invocable como control).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import escribe

from discover_controles import Candidato, discover_candidates

if TYPE_CHECKING:
    from pathlib import Path


def test_repo_vacio_no_devuelve_candidatos(tmp_path: Path) -> None:
    """Lista vacia significa "hay que preguntarlo", no "este repo no tiene controles": eso ultimo se declara
    con `ninguno` en el issue.
    """
    assert discover_candidates(tmp_path) == []


def test_lista_los_targets_del_makefile_en_orden(tmp_path: Path) -> None:
    escribe(
        tmp_path,
        "Makefile",
        "linting:\n\truff check .\n\ntest:\n\tpytest\n",
    )
    assert discover_candidates(tmp_path) == [
        Candidato(nombre="linting", comando="make linting", fuente="makefile"),
        Candidato(nombre="test", comando="make test", fuente="makefile"),
    ]


def test_el_comentario_de_encima_viaja_como_pista(tmp_path: Path) -> None:
    """Sin la pista, el filtrado del agente seria a ciegas entre targets de nombre opaco."""
    escribe(tmp_path, "Makefile", "# corre la suite entera\ntest:\n\tpytest\n")
    assert discover_candidates(tmp_path)[0].pista == "corre la suite entera"


def test_una_linea_en_blanco_corta_la_pista(tmp_path: Path) -> None:
    escribe(tmp_path, "Makefile", "# cabecera del fichero\n\ntest:\n\tpytest\n")
    assert discover_candidates(tmp_path)[0].pista == ""


def test_ignora_targets_ocultos_variables_y_reglas_patron(tmp_path: Path) -> None:
    escribe(
        tmp_path,
        "Makefile",
        ".PHONY: test\nSHELL := /bin/bash\n%.o: %.c\n\tcc $<\ntest:\n\tpytest\n",
    )
    assert [c.nombre for c in discover_candidates(tmp_path)] == ["test"]


def test_no_repite_un_target_declarado_dos_veces(tmp_path: Path) -> None:
    escribe(tmp_path, "Makefile", "test:\n\tpytest\ntest: extra\n\techo x\n")
    assert [c.nombre for c in discover_candidates(tmp_path)] == ["test"]


def test_no_confunde_una_receta_con_un_target(tmp_path: Path) -> None:
    """Las lineas de receta empiezan por tabulador; un `foo:` dentro de una no declara nada."""
    escribe(tmp_path, "Makefile", "test:\n\techo algo: con dos puntos\n")
    assert [c.nombre for c in discover_candidates(tmp_path)] == ["test"]


def test_senala_las_herramientas_configuradas_en_pyproject(tmp_path: Path) -> None:
    escribe(
        tmp_path,
        "pyproject.toml",
        "[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n",
    )
    candidatos = discover_candidates(tmp_path)
    assert [c.nombre for c in candidatos] == ["ruff", "mypy"]
    assert all(c.fuente == "pyproject" for c in candidatos)


def test_pyproject_sin_herramientas_no_aporta_candidatos(tmp_path: Path) -> None:
    escribe(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    assert discover_candidates(tmp_path) == []


def test_pyproject_ilegible_no_esconde_los_del_makefile(tmp_path: Path) -> None:
    """Fallar aqui dejaria sin candidatos un repo que si los tiene: el descubrimiento degrada, no revienta."""
    escribe(tmp_path, "Makefile", "test:\n\tpytest\n")
    escribe(tmp_path, "pyproject.toml", "esto no es toml [[[\n")
    assert [c.nombre for c in discover_candidates(tmp_path)] == ["test"]


def test_el_makefile_va_antes_que_pyproject(tmp_path: Path) -> None:
    """En muchos repos todo corre en Docker via make y lanzar pytest directo fallaria: el orden es la senal
    de por donde empezar a mirar.
    """
    escribe(tmp_path, "Makefile", "test:\n\tdocker compose run pytest\n")
    escribe(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = []\n")
    assert [c.fuente for c in discover_candidates(tmp_path)] == ["makefile", "pyproject"]


def test_tox_ini_es_una_senal(tmp_path: Path) -> None:
    escribe(tmp_path, "tox.ini", "[tox]\nenvlist = py311\n")
    assert discover_candidates(tmp_path) == [Candidato(nombre="tox", comando="tox", fuente="tox", pista="hay tox.ini")]
