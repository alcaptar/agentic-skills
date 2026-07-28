#!/usr/bin/env python3
"""Puertas deterministas de slice-runner (patron offload-deterministic).

Se offloada a script la regla mecanica con coste de error alto que el modelo no
garantiza por si mismo. Redactar un conventional commit lo hace bien el agente, asi
que no hay puerta para eso. Hay tres:

    pr-hygiene   el diff staged solo puede contener los ficheros de codigo/test
                 que declaro el implementador; nunca planes ni design-docs (la spec
                 vive en el issue de GitHub, no como fichero).

    checks       ejecuta lint/tipos/tests con los comandos que autodetecto el paso 2
                 y devuelve, por puerta, exit code y salida truncada. Existe para que
                 el output crudo de build no entre en el contexto de ningun agente: el
                 juez adversarial no ejecuta puertas ni ve su salida, y el
                 implementador recibe el error ya acotado. Es el patron de los
                 verificadores de Honk (Spotify); su parseo por regex por herramienta
                 NO se copia, porque aqui los comandos se autodetectan por repo y un
                 regex que no matchea oculta el error real.

    diff-bundle  materializa `slice.diff` y `files.txt` (rango `<base>...HEAD`) en un
                 directorio fuera del repo. Existe para que el verificador adversarial
                 no necesite `Bash`: recibe el diff en disco en vez de calcularlo, lo
                 que hace **estructural** su incapacidad de ejecutar puertas (un
                 `allowed-tools` en el frontmatter del agente NO bloquea lo no listado;
                 se comprobo en smoke). De paso el rango lo fija el script -tres
                 puntos, desde el branch-point- y no el juicio de un modelo.

Exit code 0 = PASA, 1 = FALLA, 2 = error de uso. Con --json imprime el resultado
estructurado en stdout para que el orquestador lo consuma sin parsear prosa.

Uso:
    gates.py pr-hygiene --repo . --allow src/a.py --allow test/a.py [--spec ruta] [--json]
    gates.py checks --repo . --check lint="make linting" --check tests="make test" \\
        [--tail 30] [--timeout 600] [--json]
    gates.py diff-bundle --repo . --base master --out /tmp/slice-02 [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Truncado de la salida de una puerta que falla, y tope de duracion por puerta.
DEFAULT_TAIL = 30
DEFAULT_TIMEOUT = 600

# Prefijos/patrones de artefactos que jamas pueden entrar en la PR (documentos de
# diseno y planes de brainstorming/writing-plans). Backstop ademas del allow-list.
# El estado del run ya no vive en el repo (vive en el issue de GitHub), asi que no
# hay `.slice-runner/` que prohibir.
FORBIDDEN_PREFIXES = (
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


@dataclass
class CheckResult:
    """Resultado de una puerta ejecutada (lint, tipos o tests)."""

    nombre: str
    comando: str
    passed: bool
    exit_code: int
    salida: str

    @property
    def veredicto(self) -> str:
        return "PASA" if self.passed else "FALLA"

    def to_dict(self) -> dict[str, object]:
        return {
            "nombre": self.nombre,
            "comando": self.comando,
            "veredicto": self.veredicto,
            "exit_code": self.exit_code,
            "salida": self.salida,
        }


@dataclass
class ChecksResult:
    """Resultado agregado de todas las puertas ejecutadas."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": "checks",
            "veredicto": "PASA" if self.passed else "FALLA",
            "checks": [c.to_dict() for c in self.checks],
        }


def parse_check_spec(spec: str) -> tuple[str, str]:
    """`nombre=comando` -> (nombre, comando). Parte por el PRIMER `=`.

    El comando puede llevar `=` (p. ej. `make test ARGS=-x`), asi que solo el primero
    separa. Nombre y comando vacios son error de uso, no una puerta que falla.
    """
    nombre, sep, comando = spec.partition("=")
    if not sep or not nombre.strip() or not comando.strip():
        raise ValueError(f"--check mal formado, se esperaba nombre=comando: {spec!r}")
    return nombre.strip(), comando.strip()


def tail(text: str, lines: int) -> str:
    """Las ultimas `lines` lineas de `text`, sin salto final."""
    return "\n".join(text.rstrip("\n").splitlines()[-lines:])


def run_check(repo: str, nombre: str, comando: str, tail_lines: int, timeout: int) -> CheckResult:
    """Ejecuta una puerta y devuelve exit code + salida truncada solo si falla."""
    try:
        # `shell=True` es deliberado: el comando lo autodetecta el paso 2 del propio repo
        # (`make test`, `uv run pytest`...) y llega como una linea de shell, no como argv.
        # `check=False` tambien: el exit code ES el resultado que devolvemos, no una excepcion.
        out = subprocess.run(
            comando,
            shell=True,
            check=False,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(nombre, comando, False, -1, f"timeout tras {timeout}s")
    passed = out.returncode == 0
    # En PASA la salida se descarta: el mensaje corto de exito evita meter ruido de
    # build en el contexto de quien consuma esto.
    return CheckResult(
        nombre, comando, passed, out.returncode, "" if passed else tail(out.stdout, tail_lines)
    )


def run_checks(
    repo: str,
    specs: list[tuple[str, str]],
    tail_lines: int,
    timeout: int,
) -> ChecksResult:
    """Ejecuta TODAS las puertas, sin fail-fast.

    Una vuelta al implementador (spawn de agente + contexto) cuesta mas que volver a
    correr la suite, asi que se recolectan todos los fallos en una pasada.
    """
    return ChecksResult([run_check(repo, n, c, tail_lines, timeout) for n, c in specs])


@dataclass
class BundleResult:
    """Resultado de materializar el diff de la slice en disco."""

    passed: bool
    slice_diff: str = ""
    files: str = ""
    n_files: int = 0
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": "diff-bundle",
            "veredicto": "PASA" if self.passed else "FALLA",
            "slice_diff": self.slice_diff,
            "files": self.files,
            "n_files": self.n_files,
            "hallazgos": self.hallazgos,
        }


def write_diff_bundle(repo: str, base: str, out: str) -> BundleResult:
    """Escribe `slice.diff` y `files.txt` en `out` para que el verificador los lea.

    El verificador no tiene `Bash`: recibe el diff en disco en vez de calcularlo. De
    paso el rango lo fija el script y no el juicio de un modelo: siempre
    `base...HEAD` (tres puntos, desde el branch-point), porque con `..` los commits
    que la base haya avanzado desde entonces apareceran como borrados y el
    verificador cazaria violaciones fantasma.
    """
    rango = f"{base}...HEAD"
    result = BundleResult(passed=True)
    try:
        diff = subprocess.run(
            ["git", "-C", repo, "diff", rango],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        names = subprocess.run(
            ["git", "-C", repo, "diff", "--name-only", rango],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        return BundleResult(
            passed=False,
            hallazgos=[f"no se pudo diffear contra {base!r}: {exc.stderr.strip() or exc}"],
        )

    ficheros = [line for line in names.splitlines() if line.strip()]
    if not ficheros:
        # Fail-closed, igual que `pr-hygiene` con nada staged: sin cambios no hay
        # nada que verificar, y un bundle vacio haria que el verificador diera PASA
        # sobre la nada.
        return BundleResult(
            passed=False, hallazgos=[f"sin cambios respecto a {base}: nada que verificar"]
        )

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    slice_diff = out_dir / "slice.diff"
    files_txt = out_dir / "files.txt"
    slice_diff.write_text(diff, encoding="utf-8")
    files_txt.write_text("\n".join(ficheros) + "\n", encoding="utf-8")

    result.slice_diff = str(slice_diff)
    result.files = str(files_txt)
    result.n_files = len(ficheros)
    return result


def _emit_bundle(result: BundleResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[diff-bundle] {'PASA' if result.passed else 'FALLA'}")
        if result.passed:
            print(f"  slice.diff  {result.slice_diff}")
            print(f"  files.txt   {result.files} ({result.n_files} ficheros)")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def _emit(result: GateResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        veredicto = "PASA" if result.passed else "FALLA"
        print(f"[{result.gate}] {veredicto}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def _emit_checks(result: ChecksResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[checks] {'PASA' if result.passed else 'FALLA'}")
        for c in result.checks:
            print(f"  {c.veredicto} {c.nombre} ({c.comando})")
            if c.salida:
                for line in c.salida.splitlines():
                    print(f"    {line}")
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

    chk = sub.add_parser("checks", help="ejecuta lint/tipos/tests y devuelve salida truncada")
    chk.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    chk.add_argument(
        "--check",
        action="append",
        default=[],
        help="puerta como nombre=comando, p. ej. lint='make linting' (repetible)",
    )
    chk.add_argument(
        "--tail",
        type=int,
        default=DEFAULT_TAIL,
        help=f"lineas de salida en fallo (default {DEFAULT_TAIL})",
    )
    chk.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"segundos por puerta (default {DEFAULT_TIMEOUT})",
    )
    chk.add_argument("--json", action="store_true", help="salida estructurada JSON")

    bun = sub.add_parser("diff-bundle", help="materializa el diff de la slice para el verificador")
    bun.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    bun.add_argument("--base", required=True, help="rama base (el rango es <base>...HEAD)")
    bun.add_argument("--out", required=True, help="directorio destino, FUERA del repo")
    bun.add_argument("--json", action="store_true", help="salida estructurada JSON")

    args = parser.parse_args(argv)

    if args.gate == "pr-hygiene":
        return _emit(check_pr_hygiene(args.repo, args.allow, args.spec), args.json)

    if args.gate == "diff-bundle":
        return _emit_bundle(write_diff_bundle(args.repo, args.base, args.out), args.json)

    # Error de uso (exit 2), no FALLA de puerta: confundirlos haria que el orquestador
    # reintentara el paso 5 por un fallo que esta en su propia invocacion.
    if not args.check:
        print("error: checks necesita al menos un --check nombre=comando", file=sys.stderr)
        return 2
    try:
        specs = [parse_check_spec(s) for s in args.check]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _emit_checks(run_checks(args.repo, specs, args.tail, args.timeout), args.json)


if __name__ == "__main__":
    sys.exit(main())
