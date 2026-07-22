#!/usr/bin/env python3
"""Puertas deterministas de slice-runner (patron offload-deterministic).

Lo que es una regla exacta NO se delega al juicio semantico del verificador: se
resuelve aqui con un exit code autoritativo. Dos puertas:

    pr-hygiene   el diff staged solo puede contener los ficheros de codigo/test
                 que declaro el implementador; nunca spec, .slice-runner/, planes
                 ni design-docs.
    commit-msg   el mensaje debe ser un conventional commit `type(name): resumen`
                 con el `name` de la slice como scope exacto.

Exit code 0 = PASA, 1 = FALLA, 2 = error de uso. Con --json imprime el resultado
estructurado en stdout para que el orquestador lo consuma sin parsear prosa.

Uso:
    gates.py pr-hygiene --repo . --allow src/a.py --allow test/a.py [--spec ruta] [--json]
    gates.py commit-msg --name cantidad-vo --message "feat(cantidad-vo): ..." [--json]
    gates.py commit-msg --name cantidad-vo --message-file MSG [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# Prefijos/patrones de artefactos que jamas pueden entrar en la PR (estado efimero
# del run y documentos de diseno). Backstop ademas del allow-list.
FORBIDDEN_PREFIXES = (
    ".slice-runner/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
)

# Types validos de conventional commits.
COMMIT_TYPES = (
    "feat",
    "fix",
    "refactor",
    "chore",
    "docs",
    "test",
    "perf",
    "build",
    "ci",
    "style",
    "revert",
)


@dataclass
class GateResult:
    """Resultado de una puerta determinista."""

    gate: str
    passed: bool
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "veredicto": "PASA" if self.passed else "FALLA",
            "hallazgos": self.hallazgos,
        }


def _staged_files(repo: str) -> list[str]:
    """Ficheros en el index (git diff --cached --name-only), rutas POSIX."""
    out = subprocess.run(
        ["git", "-C", repo, "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _norm(path: str) -> str:
    """Normaliza una ruta relativa a POSIX para comparar de forma estable."""
    return PurePosixPath(path).as_posix()


def check_pr_hygiene(
    repo: str,
    allow: list[str],
    spec: str | None,
) -> GateResult:
    """El diff staged debe ser subconjunto de lo declarado y no tocar artefactos."""
    staged = [_norm(p) for p in _staged_files(repo)]
    result = GateResult(gate="pr-hygiene", passed=True)

    if not staged:
        result.passed = False
        result.hallazgos.append("nada staged: no hay ficheros de codigo/test que abrir en PR")
        return result

    allowed = {_norm(p) for p in allow}
    forbidden = set(FORBIDDEN_PREFIXES)
    spec_norm = _norm(spec) if spec else None

    for path in staged:
        if any(path.startswith(pref) for pref in forbidden):
            result.passed = False
            result.hallazgos.append(f"artefacto prohibido staged: {path}")
            continue
        if spec_norm and path == spec_norm:
            result.passed = False
            result.hallazgos.append(f"la spec no puede entrar en la PR: {path}")
            continue
        # Fail-closed: sin lista declarada, nada esta permitido. La puerta nunca
        # debe abrirse por omision del --allow (seria un falso negativo peligroso).
        if path not in allowed:
            result.passed = False
            motivo = (
                "staged pero no se declaro ninguna ruta (--allow vacio)"
                if not allowed
                else "staged fuera de lo declarado por el implementador"
            )
            result.hallazgos.append(f"{motivo}: {path}")

    return result


def _conventional_re(name: str) -> re.Pattern[str]:
    types = "|".join(COMMIT_TYPES)
    scope = re.escape(name)
    # `!` opcional antes de los dos puntos: marcador de breaking change de Conventional Commits.
    return re.compile(rf"^(?:{types})\({scope}\)!?: .+")


def check_commit_msg(name: str, message: str) -> GateResult:
    """El titulo debe ser `type(name): resumen` con name como scope exacto."""
    result = GateResult(gate="commit-msg", passed=True)
    title = message.strip().splitlines()[0].strip() if message.strip() else ""

    if not title:
        result.passed = False
        result.hallazgos.append("mensaje de commit vacio")
        return result

    if not _conventional_re(name).match(title):
        result.passed = False
        result.hallazgos.append(
            f"'{title}' no es conventional commit `type({name}): resumen` "
            f"(types validos: {', '.join(COMMIT_TYPES)}; scope debe ser '{name}')"
        )

    return result


def _emit(result: GateResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        veredicto = "PASA" if result.passed else "FALLA"
        print(f"[{result.gate}] {veredicto}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Puertas deterministas de slice-runner")
    parser.add_argument("--json", action="store_true", help="salida estructurada JSON")
    sub = parser.add_subparsers(dest="gate", required=True)

    hyg = sub.add_parser("pr-hygiene", help="el diff staged solo lleva codigo/test de la slice")
    hyg.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    hyg.add_argument(
        "--allow",
        action="append",
        default=[],
        help="ruta declarada por el implementador (repetible)",
    )
    hyg.add_argument("--spec", default=None, help="ruta de la spec, para prohibirla explicitamente")

    cm = sub.add_parser("commit-msg", help="conventional commit con name como scope")
    cm.add_argument("--name", required=True, help="name de la slice = scope del commit")
    grp = cm.add_mutually_exclusive_group(required=True)
    grp.add_argument("--message", help="mensaje del commit (se valida la primera linea)")
    grp.add_argument("--message-file", help="fichero con el mensaje del commit")

    args = parser.parse_args(argv)

    if args.gate == "pr-hygiene":
        result = check_pr_hygiene(args.repo, args.allow, args.spec)
    else:
        if args.message_file:
            with open(args.message_file, encoding="utf-8") as fh:
                message = fh.read()
        else:
            message = args.message
        result = check_commit_msg(args.name, message)

    return _emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
