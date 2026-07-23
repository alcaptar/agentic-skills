"""Tests de la puerta determinista pr-hygiene (gates.py).

Es la unica puerta que queda: el diff staged solo puede llevar los ficheros que
declaro el implementador, nunca artefactos del run ni la spec. El commit-msg ya no
se valida por script (lo redacta el agente).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import gates


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "test")
    return tmp_path


def _stage(repo: Path, rel: str, content: str = "x") -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-f", rel)


def test_subconjunto_declarado_pasa(repo: Path) -> None:
    _stage(repo, "src/a.py")
    _stage(repo, "tests/test_a.py")
    res = gates.check_pr_hygiene(str(repo), ["src/a.py", "tests/test_a.py"], None)
    assert res.passed
    assert res.hallazgos == []


def test_fail_closed_sin_allow(repo: Path) -> None:
    _stage(repo, "src/a.py")
    res = gates.check_pr_hygiene(str(repo), [], None)
    assert not res.passed
    assert any("no se declaro ninguna ruta" in h for h in res.hallazgos)


def test_nada_staged(repo: Path) -> None:
    res = gates.check_pr_hygiene(str(repo), ["src/a.py"], None)
    assert not res.passed
    assert any("nada staged" in h for h in res.hallazgos)


def test_artefacto_prohibido_aunque_este_en_allow(repo: Path) -> None:
    # .slice-runner/ es FORBIDDEN: falla aunque se declare en --allow.
    _stage(repo, "src/a.py")
    _stage(repo, ".slice-runner/state.json")
    res = gates.check_pr_hygiene(
        str(repo), ["src/a.py", ".slice-runner/state.json"], None
    )
    assert not res.passed
    assert any("artefacto prohibido" in h for h in res.hallazgos)


def test_spec_prohibida_explicitamente(repo: Path) -> None:
    _stage(repo, "src/a.py")
    _stage(repo, "spec.md")
    res = gates.check_pr_hygiene(str(repo), ["src/a.py", "spec.md"], "spec.md")
    assert not res.passed
    assert any("spec no puede entrar" in h for h in res.hallazgos)


def test_staged_fuera_de_lo_declarado(repo: Path) -> None:
    _stage(repo, "src/a.py")
    _stage(repo, "src/extra.py")
    res = gates.check_pr_hygiene(str(repo), ["src/a.py"], None)
    assert not res.passed
    assert any("src/extra.py" in h for h in res.hallazgos)


def test_main_json_funciona_tras_el_subcomando(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Regresion #1: --json debe aceptarse DESPUES del subcomando (como documenta el uso).
    _stage(repo, "src/a.py")
    code = gates.main(["pr-hygiene", "--repo", str(repo), "--allow", "src/a.py", "--json"])
    assert code == 0
    assert '"veredicto": "PASA"' in capsys.readouterr().out


def test_main_exit_1_si_falla(repo: Path) -> None:
    _stage(repo, "src/a.py")
    code = gates.main(["pr-hygiene", "--repo", str(repo)])  # sin --allow -> fail-closed
    assert code == 1


def test_no_existe_puerta_commit_msg() -> None:
    # La puerta commit-msg y la lista de types se eliminaron.
    assert not hasattr(gates, "check_commit_msg")
    assert not hasattr(gates, "COMMIT_TYPES")
