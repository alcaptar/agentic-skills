#!/usr/bin/env python3
"""Controles deterministas de slice-runner (patron offload-deterministic).

Se offloada a script la regla mecanica con coste de error alto que el modelo no
garantiza por si mismo. Redactar un conventional commit lo hace bien el agente, asi
que no hay control para eso. Hay tres subcomandos:

    pr-hygiene   el diff staged solo puede contener los ficheros de codigo/test
                 que declaro el implementador; nunca planes ni design-docs (la spec
                 vive en el issue de GitHub, no como fichero).

    controles    ejecuta los controles declarados en el issue (`## Controles`) y
                 devuelve, por control, exit code y donde esta su salida. Existe para
                 que el output crudo de build no entre en el contexto de ningun agente:
                 el juez adversarial no ejecuta controles ni ve su salida, y con `--out`
                 el orquestador tampoco -recibe rutas y las reenvia, y el implementador
                 lee el log entero-. Es el patron de los verificadores de Honk (Spotify);
                 su parseo por regex por herramienta NO se copia, porque aqui los
                 comandos los declara cada repo y un regex que no matchea oculta el
                 error real.

    diff-bundle  materializa `slice.diff` y `files.txt` (rango `<base>...HEAD`) en un
                 directorio fuera del repo. Existe para que el verificador adversarial
                 no necesite `Bash`: recibe el diff en disco en vez de calcularlo, lo
                 que hace **estructural** su incapacidad de ejecutar controles (un
                 `allowed-tools` en el frontmatter del agente NO bloquea lo no listado;
                 se comprobo en smoke). De paso el rango lo fija el script -tres
                 puntos, desde el branch-point- y no el juicio de un modelo.

El script no sabe nada de toolchains: solo ejecuta los `nombre=comando` que se le pasan,
que salen de la seccion `## Controles` del issue (los descubre `slice-spec` una vez y los
confirma una persona). Por eso no hay autodeteccion aqui dentro.

Exit code 0 = PASA, 1 = FALLA, 2 = error de uso. Con --json imprime el resultado
estructurado en stdout para que el orquestador lo consuma sin parsear prosa.

Uso:
    controles.py pr-hygiene --repo . --allow src/a.py --allow test/a.py [--spec ruta] [--json]
    controles.py controles --repo . --control lint="make linting" --control tests="make test" \\
        [--out /tmp/slice-02/logs] [--tail 30] [--timeout 600] [--json]
    controles.py diff-bundle --repo . --base master --out /tmp/slice-02 [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Truncado de la salida de un control que falla (solo sin `--out`), y tope de duracion.
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

# Todo lo que no sea alfanumerico, punto, guion o guion bajo, al nombrar el fichero de log.
_UNSAFE_FILENAME_RE = re.compile(r"[^\w.-]+")


@dataclass
class Resultado:
    """Resultado de un control determinista de veredicto unico (higiene del diff staged)."""

    control: str
    passed: bool
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": self.control,
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


def comprueba_higiene_pr(
    repo: str,
    allow: list[str],
    spec: str | None,
) -> Resultado:
    """El diff staged debe ser subconjunto de lo declarado y no tocar artefactos."""
    staged = [_norm(p) for p in _staged_files(repo)]
    result = Resultado(control="pr-hygiene", passed=True)

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
        # Fail-closed: sin lista declarada, nada esta permitido. El control nunca
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
class ResultadoControl:
    """Resultado de un control ejecutado (lint, tipos, tests... lo que declare el repo).

    `salida` y `log` son excluyentes: con `--out`, la salida entera va al fichero `log` y
    `salida` queda vacia, que es lo que permite al orquestador reenviar una ruta en vez de
    tragarse output de build. Sin `--out`, `salida` lleva la cola truncada, que es lo util
    cuando lo lanza una persona en un terminal.
    """

    nombre: str
    comando: str
    passed: bool
    exit_code: int
    salida: str = ""
    log: str = ""

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
            "log": self.log,
        }


@dataclass
class ResultadoControles:
    """Resultado agregado de todos los controles ejecutados."""

    controles: list[ResultadoControl] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.controles)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": "controles",
            "veredicto": "PASA" if self.passed else "FALLA",
            "controles": [c.to_dict() for c in self.controles],
        }


def parse_control_spec(spec: str) -> tuple[str, str]:
    """`nombre=comando` -> (nombre, comando). Parte por el PRIMER `=`.

    El comando puede llevar `=` (p. ej. `make test ARGS=-x`), asi que solo el primero
    separa. Nombre y comando vacios son error de uso, no un control que falla.
    """
    nombre, sep, comando = spec.partition("=")
    if not sep or not nombre.strip() or not comando.strip():
        raise ValueError(f"--control mal formado, se esperaba nombre=comando: {spec!r}")
    return nombre.strip(), comando.strip()


def tail(text: str, lines: int) -> str:
    """Las ultimas `lines` lineas de `text`, sin salto final."""
    return "\n".join(text.rstrip("\n").splitlines()[-lines:])


def _log_path(out: str, nombre: str) -> Path:
    """Ruta del log de un control. El nombre se sanea: llega por linea de comandos."""
    return Path(out) / f"{_UNSAFE_FILENAME_RE.sub('_', nombre) or 'control'}.log"


def ejecuta_control(
    repo: str,
    nombre: str,
    comando: str,
    tail_lines: int,
    timeout: int,
    out: str | None = None,
) -> ResultadoControl:
    """Ejecuta un control y devuelve exit code y, solo si falla, donde esta su salida."""
    try:
        # `shell=True` es deliberado: el comando lo declara el issue del propio repo
        # (`make test`, `uv run pytest`...) y llega como una linea de shell, no como argv.
        # `check=False` tambien: el exit code ES el resultado que devolvemos, no una excepcion.
        proc = subprocess.run(
            comando,
            shell=True,
            check=False,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        exit_code, salida = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        exit_code, salida = -1, f"timeout tras {timeout}s"

    # En PASA la salida se descarta: el mensaje corto de exito evita meter ruido de
    # build en el contexto de quien consuma esto.
    if exit_code == 0:
        return ResultadoControl(nombre, comando, True, 0)

    if out is None:
        return ResultadoControl(nombre, comando, False, exit_code, salida=tail(salida, tail_lines))

    # Con `--out`, el log entero va a disco y aqui solo viaja su ruta: el orquestador la
    # reenvia sin leerla y el implementador recibe el error completo, no 30 lineas.
    destino = _log_path(out, nombre)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(salida, encoding="utf-8")
    return ResultadoControl(nombre, comando, False, exit_code, log=str(destino))


def ejecuta_controles(
    repo: str,
    specs: list[tuple[str, str]],
    tail_lines: int,
    timeout: int,
    out: str | None = None,
) -> ResultadoControles:
    """Ejecuta TODOS los controles, sin fail-fast.

    Una vuelta al implementador (spawn de agente + contexto) cuesta mas que volver a
    correr la suite, asi que se recolectan todos los fallos en una pasada.
    """
    return ResultadoControles(
        [ejecuta_control(repo, n, c, tail_lines, timeout, out) for n, c in specs]
    )


@dataclass
class ResultadoBundle:
    """Resultado de materializar el diff de la slice en disco."""

    passed: bool
    slice_diff: str = ""
    files: str = ""
    n_files: int = 0
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": "diff-bundle",
            "veredicto": "PASA" if self.passed else "FALLA",
            "slice_diff": self.slice_diff,
            "files": self.files,
            "n_files": self.n_files,
            "hallazgos": self.hallazgos,
        }


def escribe_diff_bundle(repo: str, base: str, out: str) -> ResultadoBundle:
    """Escribe `slice.diff` y `files.txt` en `out` para que el verificador los lea.

    El verificador no tiene `Bash`: recibe el diff en disco en vez de calcularlo. De
    paso el rango lo fija el script y no el juicio de un modelo: siempre
    `base...HEAD` (tres puntos, desde el branch-point), porque con `..` los commits
    que la base haya avanzado desde entonces apareceran como borrados y el
    verificador cazaria violaciones fantasma.
    """
    rango = f"{base}...HEAD"
    result = ResultadoBundle(passed=True)
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
        return ResultadoBundle(
            passed=False,
            hallazgos=[f"no se pudo diffear contra {base!r}: {exc.stderr.strip() or exc}"],
        )

    ficheros = [line for line in names.splitlines() if line.strip()]
    if not ficheros:
        # Fail-closed, igual que `pr-hygiene` con nada staged: sin cambios no hay
        # nada que verificar, y un bundle vacio haria que el verificador diera PASA
        # sobre la nada.
        return ResultadoBundle(
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


def _emit_bundle(result: ResultadoBundle, as_json: bool) -> int:
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


def _emit(result: Resultado, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        veredicto = "PASA" if result.passed else "FALLA"
        print(f"[{result.control}] {veredicto}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def _emit_controles(result: ResultadoControles, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[controles] {'PASA' if result.passed else 'FALLA'}")
        for c in result.controles:
            print(f"  {c.veredicto} {c.nombre} ({c.comando})")
            if c.log:
                print(f"    log: {c.log}")
            for line in c.salida.splitlines():
                print(f"    {line}")
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control determinista de slice-runner")
    sub = parser.add_subparsers(dest="subcomando", required=True)

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

    ctl = sub.add_parser("controles", help="ejecuta los controles declarados en el issue")
    ctl.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    ctl.add_argument(
        "--control",
        action="append",
        default=[],
        help="control como nombre=comando, p. ej. lint='make linting' (repetible)",
    )
    ctl.add_argument(
        "--out",
        default=None,
        help="directorio FUERA del repo donde escribir el log entero de cada control fallido",
    )
    ctl.add_argument(
        "--tail",
        type=int,
        default=DEFAULT_TAIL,
        help=f"lineas de salida en fallo cuando no hay --out (default {DEFAULT_TAIL})",
    )
    ctl.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"segundos por control (default {DEFAULT_TIMEOUT})",
    )
    ctl.add_argument("--json", action="store_true", help="salida estructurada JSON")

    bun = sub.add_parser("diff-bundle", help="materializa el diff de la slice para el verificador")
    bun.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    bun.add_argument("--base", required=True, help="rama base (el rango es <base>...HEAD)")
    bun.add_argument("--out", required=True, help="directorio destino, FUERA del repo")
    bun.add_argument("--json", action="store_true", help="salida estructurada JSON")

    args = parser.parse_args(argv)

    if args.subcomando == "pr-hygiene":
        return _emit(comprueba_higiene_pr(args.repo, args.allow, args.spec), args.json)

    if args.subcomando == "diff-bundle":
        return _emit_bundle(escribe_diff_bundle(args.repo, args.base, args.out), args.json)

    # Error de uso (exit 2), no FALLA de control: confundirlos haria que el orquestador
    # reintentara el paso 5 por un fallo que esta en su propia invocacion.
    if not args.control:
        print("error: controles necesita al menos un --control nombre=comando", file=sys.stderr)
        return 2
    try:
        specs = [parse_control_spec(s) for s in args.control]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _emit_controles(
        ejecuta_controles(args.repo, specs, args.tail, args.timeout, args.out), args.json
    )


if __name__ == "__main__":
    sys.exit(main())
