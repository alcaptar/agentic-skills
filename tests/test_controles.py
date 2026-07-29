"""Tests de los controles deterministas de slice-runner (controles.py).

- `pr-hygiene`: el diff staged solo puede llevar los ficheros que declaro el
  implementador, nunca artefactos del run ni la spec.
- `controles`: ejecuta los comandos que el issue declara y devuelve exit code y
  donde esta la salida, para que el output crudo de build no entre en el contexto
  de ningun agente. El juez adversarial no ejecuta controles, y con `--out` el
  orquestador tampoco ve su salida: solo reenvia rutas.
- `diff-bundle`: materializa el diff para el verificador, que no tiene `Bash`.

El commit-msg no se valida por script (lo redacta el agente).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import controles


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
    res = controles.comprueba_higiene_pr(str(repo), ["src/a.py", "tests/test_a.py"], None)
    assert res.passed
    assert res.hallazgos == []


def test_fail_closed_sin_allow(repo: Path) -> None:
    _stage(repo, "src/a.py")
    res = controles.comprueba_higiene_pr(str(repo), [], None)
    assert not res.passed
    assert any("no se declaro ninguna ruta" in h for h in res.hallazgos)


def test_nada_staged(repo: Path) -> None:
    res = controles.comprueba_higiene_pr(str(repo), ["src/a.py"], None)
    assert not res.passed
    assert any("nada staged" in h for h in res.hallazgos)


def test_artefacto_prohibido_aunque_este_en_allow(repo: Path) -> None:
    # Un design-doc bajo docs/superpowers/specs/ es FORBIDDEN: falla aunque se declare en --allow.
    _stage(repo, "src/a.py")
    _stage(repo, "docs/superpowers/specs/x-design.md")
    res = controles.comprueba_higiene_pr(
        str(repo), ["src/a.py", "docs/superpowers/specs/x-design.md"], None
    )
    assert not res.passed
    assert any("artefacto prohibido" in h for h in res.hallazgos)


def test_spec_prohibida_explicitamente(repo: Path) -> None:
    _stage(repo, "src/a.py")
    _stage(repo, "spec.md")
    res = controles.comprueba_higiene_pr(str(repo), ["src/a.py", "spec.md"], "spec.md")
    assert not res.passed
    assert any("spec no puede entrar" in h for h in res.hallazgos)


def test_staged_fuera_de_lo_declarado(repo: Path) -> None:
    _stage(repo, "src/a.py")
    _stage(repo, "src/extra.py")
    res = controles.comprueba_higiene_pr(str(repo), ["src/a.py"], None)
    assert not res.passed
    assert any("src/extra.py" in h for h in res.hallazgos)


def test_main_json_funciona_tras_el_subcomando(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regresion #1: --json debe aceptarse DESPUES del subcomando (como documenta el uso).
    _stage(repo, "src/a.py")
    code = controles.main(["pr-hygiene", "--repo", str(repo), "--allow", "src/a.py", "--json"])
    assert code == 0
    assert '"veredicto": "PASA"' in capsys.readouterr().out


def test_main_exit_1_si_falla(repo: Path) -> None:
    _stage(repo, "src/a.py")
    code = controles.main(["pr-hygiene", "--repo", str(repo)])  # sin --allow -> fail-closed
    assert code == 1


def test_no_existe_control_commit_msg() -> None:
    # El control commit-msg y la lista de types se eliminaron.
    assert not hasattr(controles, "check_commit_msg")
    assert not hasattr(controles, "COMMIT_TYPES")


# --- control `controles` -------------------------------------------------------


def test_parse_control_spec_separa_nombre_y_comando() -> None:
    assert controles.parse_control_spec("lint=make linting") == ("lint", "make linting")


def test_parse_control_spec_parte_por_el_primer_igual() -> None:
    # El comando puede llevar `=` (variables de make): solo el primero separa.
    assert controles.parse_control_spec("tests=make test ARGS=-x") == ("tests", "make test ARGS=-x")


@pytest.mark.parametrize("spec", ["sin-igual", "=make test", "lint="])
def test_parse_control_spec_rechaza_malformado(spec: str) -> None:
    with pytest.raises(ValueError):
        controles.parse_control_spec(spec)


def test_tail_devuelve_las_ultimas_lineas() -> None:
    assert controles.tail("l1\nl2\nl3\nl4", 2) == "l3\nl4"


def test_tail_no_recorta_si_cabe() -> None:
    assert controles.tail("l1\nl2", 5) == "l1\nl2"


def test_control_que_pasa_no_trae_salida(repo: Path) -> None:
    # En PASA solo interesa el veredicto: la salida se descarta (mensaje corto de exito).
    res = controles.ejecuta_controles(
        str(repo), [("ok", "echo mucho ruido de build")], tail_lines=30, timeout=10
    )
    assert res.passed
    assert res.controles[0].exit_code == 0
    assert res.controles[0].salida == ""


def test_control_que_falla_trae_salida_truncada(repo: Path) -> None:
    res = controles.ejecuta_controles(
        str(repo), [("types", "seq 1 10; exit 1")], tail_lines=3, timeout=10
    )
    assert not res.passed
    assert res.controles[0].exit_code == 1
    assert res.controles[0].salida == "8\n9\n10"


def test_corre_todos_los_controles_sin_fail_fast(repo: Path) -> None:
    # Recolectar todos los fallos en una pasada ahorra vueltas al implementador,
    # que cuestan mas que volver a correr la suite.
    res = controles.ejecuta_controles(
        str(repo),
        [("lint", "exit 1"), ("types", "exit 1"), ("tests", "exit 0")],
        tail_lines=30,
        timeout=10,
    )
    assert not res.passed
    assert [c.veredicto for c in res.controles] == ["FALLA", "FALLA", "PASA"]


def test_timeout_es_falla_con_motivo(repo: Path) -> None:
    res = controles.ejecuta_controles(str(repo), [("tests", "sleep 3")], tail_lines=30, timeout=1)
    assert not res.passed
    assert res.controles[0].salida == "timeout tras 1s"


def test_controles_to_dict_tiene_el_contrato_documentado(repo: Path) -> None:
    res = controles.ejecuta_controles(str(repo), [("lint", "exit 0")], tail_lines=30, timeout=10)
    assert res.to_dict() == {
        "control": "controles",
        "veredicto": "PASA",
        "controles": [
            {
                "nombre": "lint",
                "comando": "exit 0",
                "veredicto": "PASA",
                "exit_code": 0,
                "salida": "",
                "log": "",
            }
        ],
    }


# Con `--out`, la salida entera va a disco y el resultado solo lleva su ruta. Es lo que
# saca el output de build del contexto del orquestador: reenvia la ruta sin leerla, y el
# implementador recibe el log completo en vez de la cola truncada.


def test_con_out_la_salida_va_al_log_y_no_al_resultado(repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "logs"
    res = controles.ejecuta_controles(
        str(repo), [("tests", "seq 1 10; exit 1")], tail_lines=3, timeout=10, out=str(out)
    )
    control = res.controles[0]
    assert control.salida == ""
    assert control.log == str(out / "tests.log")
    # Entero, no truncado a `tail_lines`: el implementador necesita el error completo.
    assert Path(control.log).read_text(encoding="utf-8").splitlines() == [
        str(i) for i in range(1, 11)
    ]


def test_con_out_un_control_que_pasa_no_deja_log(repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "logs"
    res = controles.ejecuta_controles(
        str(repo), [("lint", "echo ruido")], tail_lines=30, timeout=10, out=str(out)
    )
    assert res.passed
    assert res.controles[0].log == ""
    assert not (out / "lint.log").exists()


def test_con_out_el_nombre_del_log_se_sanea(repo: Path, tmp_path: Path) -> None:
    # El nombre llega por linea de comandos: no puede componer una ruta fuera de `--out`.
    out = tmp_path / "logs"
    res = controles.ejecuta_controles(
        str(repo), [("../escapa", "exit 1")], tail_lines=30, timeout=10, out=str(out)
    )
    assert Path(res.controles[0].log).parent == out


def test_main_controles_con_out_json_trae_la_ruta(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "logs"
    code = controles.main(
        [
            "controles",
            "--repo",
            str(repo),
            "--control",
            "tests=exit 1",
            "--out",
            str(out),
            "--json",
        ]
    )
    assert code == 1
    control = json.loads(capsys.readouterr().out)["controles"][0]
    assert control["log"] == str(out / "tests.log")
    assert control["salida"] == ""


def test_main_controles_exit_0_y_json(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = controles.main(["controles", "--repo", str(repo), "--control", "lint=exit 0", "--json"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["veredicto"] == "PASA"


def test_main_controles_exit_1_si_alguna_falla(repo: Path) -> None:
    code = controles.main(["controles", "--repo", str(repo), "--control", "lint=exit 1"])
    assert code == 1


def test_main_controles_exit_2_si_el_spec_es_malo(repo: Path) -> None:
    # Error de uso, no FALLA de control: confundirlos haria que el orquestador
    # reintentara el paso 5 por un fallo que esta en su propia invocacion.
    code = controles.main(["controles", "--repo", str(repo), "--control", "sin-igual"])
    assert code == 2


def test_main_controles_exit_2_sin_ningun_control(repo: Path) -> None:
    code = controles.main(["controles", "--repo", str(repo)])
    assert code == 2


# --- control `diff-bundle` --------------------------------------------------
#
# Existe para que el verificador no necesite `Bash`: el orquestador le deja el diff
# y la lista de ficheros en disco, y el agente solo los lee. Ademas quita de encima
# el footgun de `..` vs `...` al derivar el rango.


@pytest.fixture
def repo_con_rama(repo: Path) -> Path:
    _stage(repo, "src/a.py", "def f() -> int:\n    return 1\n")
    _stage(repo, "tests/test_a.py", "def test_f() -> None:\n    assert f() == 1\n")
    _git(repo, "commit", "-m", "baseline")
    _git(repo, "switch", "-c", "slice/01-x")
    _stage(repo, "src/a.py", "def f() -> int:\n    return 2\n")
    _stage(repo, "tests/test_a.py", "def test_f() -> None:\n    assert f() is not None\n")
    _git(repo, "commit", "-m", "slice")
    return repo


def test_diff_bundle_escribe_diff_y_lista(repo_con_rama: Path, tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    res = controles.escribe_diff_bundle(str(repo_con_rama), "master", str(out))
    assert res.passed
    assert sorted((out / "files.txt").read_text(encoding="utf-8").split()) == [
        "src/a.py",
        "tests/test_a.py",
    ]
    diff = (out / "slice.diff").read_text(encoding="utf-8")
    # El debilitamiento del test preexistente tiene que ser visible como linea `-`:
    # es lo unico con lo que el verificador puede cazarlo sin `git`.
    assert "-    assert f() == 1" in diff
    assert "+    assert f() is not None" in diff


def test_diff_bundle_usa_el_rango_de_tres_puntos(repo_con_rama: Path, tmp_path: Path) -> None:
    # Un commit en la base posterior al branch-point NO debe aparecer en el bundle:
    # con `..` saldria como borrado y el verificador cazaria un fantasma.
    _git(repo_con_rama, "switch", "master")
    _stage(repo_con_rama, "src/otro.py", "x = 1\n")
    _git(repo_con_rama, "commit", "-m", "avanza la base")
    _git(repo_con_rama, "switch", "slice/01-x")

    out = tmp_path / "bundle"
    controles.escribe_diff_bundle(str(repo_con_rama), "master", str(out))
    assert "src/otro.py" not in (out / "files.txt").read_text(encoding="utf-8")


def test_diff_bundle_falla_si_la_base_no_existe(repo_con_rama: Path, tmp_path: Path) -> None:
    res = controles.escribe_diff_bundle(str(repo_con_rama), "no-existe", str(tmp_path / "b"))
    assert not res.passed
    assert any("no-existe" in h for h in res.hallazgos)


def test_diff_bundle_falla_si_el_diff_esta_vacio(repo: Path, tmp_path: Path) -> None:
    # Sin cambios respecto a la base no hay nada que verificar: fail-closed, como
    # `pr-hygiene` con nada staged.
    _stage(repo, "src/a.py")
    _git(repo, "commit", "-m", "baseline")
    res = controles.escribe_diff_bundle(str(repo), "master", str(tmp_path / "b"))
    assert not res.passed
    assert any("sin cambios" in h for h in res.hallazgos)


def test_main_diff_bundle_json_imprime_las_rutas(
    repo_con_rama: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "bundle"
    code = controles.main(
        [
            "diff-bundle",
            "--repo",
            str(repo_con_rama),
            "--base",
            "master",
            "--out",
            str(out),
            "--json",
        ]
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["control"] == "diff-bundle"
    assert data["veredicto"] == "PASA"
    assert data["slice_diff"] == str(out / "slice.diff")
    assert data["files"] == str(out / "files.txt")
    assert data["n_files"] == 2


def test_main_diff_bundle_exit_1_si_falla(repo_con_rama: Path, tmp_path: Path) -> None:
    code = controles.main(
        [
            "diff-bundle",
            "--repo",
            str(repo_con_rama),
            "--base",
            "nope",
            "--out",
            str(tmp_path / "b"),
        ]
    )
    assert code == 1
