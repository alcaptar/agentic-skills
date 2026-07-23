#!/usr/bin/env python3
"""Puerta determinista de slice-runner (patron offload-deterministic).

Se offloada a script solo la regla mecanica con coste de error alto que el modelo
no garantiza por si mismo. Redactar un conventional commit lo hace bien el agente,
asi que no hay puerta para eso; lo que si es un backstop mecanico es la higiene del
diff staged:

    pr-hygiene   el diff staged solo puede contener los ficheros de codigo/test
                 que declaro el implementador; nunca spec, .slice-runner/, planes
                 ni design-docs.

Exit code 0 = PASA, 1 = FALLA, 2 = error de uso. Con --json imprime el resultado
estructurado en stdout para que el orquestador lo consuma sin parsear prosa.

Uso:
    gates.py pr-hygiene --repo . --allow src/a.py --allow test/a.py [--spec ruta] [--json]
"""

from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Puerta determinista de slice-runner")
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
    hyg.add_argument("--json", action="store_true", help="salida estructurada JSON")

    args = parser.parse_args(argv)

    result = check_pr_hygiene(args.repo, args.allow, args.spec)
    return _emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
