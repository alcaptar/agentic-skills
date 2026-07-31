#!/usr/bin/env python3
"""Controles deterministas de slice-runner (patron offload-deterministic).

Se offloada a script la regla mecanica con coste de error alto que el modelo no
garantiza por si mismo. Redactar un conventional commit lo hace bien el agente, asi
que no hay control para eso. Hay cinco subcomandos:

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

    diff-bundle  materializa `slice.diff` y `files.txt` (el diff del INDICE contra el
                 branch-point) en un directorio fuera del repo. Existe para que el
                 verificador adversarial no necesite `Bash`: recibe el diff en disco en
                 vez de calcularlo, lo que hace **estructural** su incapacidad de
                 ejecutar controles (un `allowed-tools` en el frontmatter del agente NO
                 bloquea lo no listado; se comprobo en smoke). De paso el rango lo fija
                 el script y no el juicio de un modelo.

    ci-status    estado de la CI de una PR, en un tiro y sin polling. Encapsula la
                 invocacion de `gh`, sus nombres de campo y su mapeo de exit codes,
                 porque el primer smoke real demostro que dejarselos a la memoria del
                 agente cuelga el loop en silencio: `gh pr checks --json` NO tiene campo
                 `conclusion` -pero `gh run list --json` si-, y pedirlo hace que `gh`
                 responda un error que se lee igual que "todavia no hay checks".

    verify-verdict  valida que el mensaje final del juez es su contrato JSON, y devuelve
                 los conteos por severidad. La regla de "si vuelve envuelto en prosa se
                 reinvoca" ya cubria el caso obvio; esto cubre el que no: un JSON
                 estructuralmente plausible pero equivocado (`"veredicto": "PASS"`, una
                 `severidad` inventada, un hallazgo sin `evidencia`), que el orquestador
                 leeria como bueno. Comprobar un esquema es regla exacta, no juicio.

El script no sabe nada de toolchains: solo ejecuta los `nombre=comando` que se le pasan,
que salen de la seccion `## Controles` del issue (los descubre `slice-spec` una vez y los
confirma una persona). Por eso no hay autodeteccion aqui dentro.

Exit codes. En `pr-hygiene`, `controles` y `diff-bundle`: 0 = PASA, 1 = FALLA, 2 = error de
uso. `ci-status` no es binario y usa uno por rama del paso 9, para que un tick de shell
pueda decidir sin parsear: 0 = verde, 1 = rojo, 2 = error de uso, 3 = pendiente (sigue
tickeando), 4 = indeterminado (`sin-checks` o `desconocido`). El 4 **no es un veredicto ni
un cierre**: los dos estados aparecen tambien de forma transitoria en la ventana entre abrir
la PR y que GitHub registre los checks, asi que cuenta como un tick de la ventana de gracia
que fija el paso 9 -3 ticks indeterminados consecutivos, 30 s o mas entre tick y tick- y
solo al agotarla se cierra `bloqueada: ci-indeterminada`. Esa cuenta la lleva quien tickea,
no el script: `ci-status` es de un tiro y no guarda estado entre invocaciones, porque un
script que poll-ea es la shell bloqueante que la skill prohibe. Lo que el 4 si garantiza en
todo caso es que no se finja un veredicto: nunca colapsa en verde. A diferencia de
`gh pr checks`, aqui el 1 significa **solo** CI roja: una invocacion mal formada es 2 y una
respuesta ilegible es 4, nunca 1. Con --json imprime el resultado estructurado en stdout
para que el orquestador lo consuma sin parsear prosa.

Uso:
    controles.py pr-hygiene --repo . --allow src/a.py --allow test/a.py [--spec ruta] [--json]
    controles.py controles --repo . --control lint="make linting" --control tests="make test" \\
        [--out /tmp/slice-02/logs] [--tail 30] [--timeout 600] [--json]
    controles.py diff-bundle --repo . --base master --out /tmp/slice-02 [--json]
    controles.py ci-status --repo . --pr 42 [--json]
    controles.py verify-verdict --file /tmp/slice-02/veredicto.json [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_TAIL = 30
DEFAULT_TIMEOUT = 600
"""Truncado de la salida de un control que falla (solo sin `--out`), y tope de duracion."""

FORBIDDEN_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
)
"""Artefactos que jamas pueden entrar en la PR: documentos de diseno y planes.

Backstop ademas del allow-list. El estado del run ya no vive en el repo -vive en el issue de
GitHub-, asi que no hay `.slice-runner/` que prohibir.
"""

_UNSAFE_FILENAME_RE = re.compile(r"[^\w.-]+")
"""Todo lo que no sea alfanumerico, punto, guion o guion bajo, al nombrar el fichero de log."""


class Veredicto(StrEnum):
    """El veredicto binario de un control determinista: lo que lee el orquestador."""

    PASA = "PASA"
    FALLA = "FALLA"


def _veredicto_de(passed: bool) -> Veredicto:
    return Veredicto.PASA if passed else Veredicto.FALLA


@dataclass(frozen=True, kw_only=True, slots=True)
class Resultado:
    """Resultado de un control determinista de veredicto unico (higiene del diff staged)."""

    control: str
    passed: bool
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": self.control,
            "veredicto": str(_veredicto_de(self.passed)),
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


def _motivo_de_rechazo(path: str, allowed: set[str], spec: str | None) -> str | None:
    """Por que este fichero staged no puede entrar en la PR, o `None` si puede.

    Una regla por fichero y en un solo sitio: antes era el cuerpo de un bucle que iba
    mutando el `Resultado` a medias, con un `continue` por rama.

    La ultima rama es fail-closed: sin lista declarada nada esta permitido, porque el control
    nunca debe abrirse por omision del `--allow` -seria un falso negativo peligroso-.
    """
    if any(path.startswith(pref) for pref in FORBIDDEN_PREFIXES):
        return f"artefacto prohibido staged: {path}"
    if spec is not None and path == spec:
        return f"la spec no puede entrar en la PR: {path}"
    if path not in allowed:
        motivo = (
            "staged pero no se declaro ninguna ruta (--allow vacio)"
            if not allowed
            else "staged fuera de lo declarado por el implementador"
        )
        return f"{motivo}: {path}"
    return None


def comprueba_higiene_pr(repo: str, allow: list[str], spec: str | None) -> Resultado:
    """El diff staged debe ser subconjunto de lo declarado y no tocar artefactos."""
    staged = [_norm(p) for p in _staged_files(repo)]
    if not staged:
        return Resultado(
            control="pr-hygiene",
            passed=False,
            hallazgos=["nada staged: no hay ficheros de codigo/test que abrir en PR"],
        )

    allowed = {_norm(p) for p in allow}
    spec_norm = _norm(spec) if spec else None
    hallazgos = [m for path in staged if (m := _motivo_de_rechazo(path, allowed, spec_norm)) is not None]
    return Resultado(control="pr-hygiene", passed=not hallazgos, hallazgos=hallazgos)


@dataclass(frozen=True, kw_only=True, slots=True)
class OpcionesControl:
    """Como se ejecutan los controles: donde, cuanto se espera y donde va la salida.

    Agrupadas porque son las mismas para toda la pasada y viajaban como cuatro parametros
    sueltos por dos funciones. `out` es lo que decide si la salida de un control fallido
    viaja como texto o como ruta (ver `ResultadoControl`).
    """

    repo: str = "."
    tail_lines: int = DEFAULT_TAIL
    timeout: int = DEFAULT_TIMEOUT
    out: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
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
    def veredicto(self) -> Veredicto:
        return _veredicto_de(self.passed)

    def to_dict(self) -> dict[str, object]:
        return {
            "nombre": self.nombre,
            "comando": self.comando,
            "veredicto": str(self.veredicto),
            "exit_code": self.exit_code,
            "salida": self.salida,
            "log": self.log,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class ResultadoControles:
    """Resultado agregado de todos los controles ejecutados."""

    controles: list[ResultadoControl] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.controles)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": "controles",
            "veredicto": str(_veredicto_de(self.passed)),
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


def ejecuta_control(nombre: str, comando: str, opciones: OpcionesControl) -> ResultadoControl:
    """Ejecuta un control y devuelve exit code y, solo si falla, donde esta su salida.

    `shell=True` es deliberado: el comando lo declara el issue del propio repo (`make test`,
    `uv run pytest`...) y llega como una linea de shell, no como argv. `check=False` tambien:
    el exit code ES el resultado que devolvemos, no una excepcion.

    En PASA la salida se descarta, para no meter ruido de build en el contexto de quien
    consuma esto. En FALLA con `--out`, el log entero va a disco y aqui solo viaja su ruta:
    el orquestador la reenvia sin leerla y el implementador recibe el error completo en vez
    de treinta lineas.
    """
    try:
        proc = subprocess.run(
            comando,
            shell=True,
            check=False,
            cwd=opciones.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=opciones.timeout,
        )
        exit_code, salida = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        exit_code, salida = -1, f"timeout tras {opciones.timeout}s"

    if exit_code == 0:
        return ResultadoControl(nombre=nombre, comando=comando, passed=True, exit_code=0)

    if opciones.out is None:
        return ResultadoControl(
            nombre=nombre,
            comando=comando,
            passed=False,
            exit_code=exit_code,
            salida=tail(salida, opciones.tail_lines),
        )

    destino = _log_path(opciones.out, nombre)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(salida, encoding="utf-8")
    return ResultadoControl(nombre=nombre, comando=comando, passed=False, exit_code=exit_code, log=str(destino))


def ejecuta_controles(specs: list[tuple[str, str]], opciones: OpcionesControl) -> ResultadoControles:
    """Ejecuta TODOS los controles, sin fail-fast.

    Una vuelta al implementador (spawn de agente + contexto) cuesta mas que volver a
    correr la suite, asi que se recolectan todos los fallos en una pasada.
    """
    return ResultadoControles(controles=[ejecuta_control(n, c, opciones) for n, c in specs])


@dataclass(frozen=True, kw_only=True, slots=True)
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
            "veredicto": str(_veredicto_de(self.passed)),
            "slice_diff": self.slice_diff,
            "files": self.files,
            "n_files": self.n_files,
            "hallazgos": self.hallazgos,
        }


def escribe_diff_bundle(repo: str, base: str, out: str) -> ResultadoBundle:
    """Escribe `slice.diff` y `files.txt` en `out` para que el verificador los lea.

    El verificador no tiene `Bash`: recibe el diff en disco en vez de calcularlo. De
    paso el rango lo fija el script y no el juicio de un modelo.

    Se diffea el **indice** (`--cached`) contra el **branch-point** (`--merge-base`),
    no `HEAD`, por dos razones que el primer smoke real dejo claras:

    - El tramo final va `git add` -> `pr-hygiene` -> controles -> `diff-bundle` ->
      verificador -> commit (lo fija `skills/slice-runner/SKILL.md`; aqui se nombra por
      sus fases y no por su numero de paso, que se desfasa en cuanto el tramo se
      reordena). Con el commit DESPUES de la verificacion, contra `HEAD` no habria nada
      que ver. Verificar antes de commitear es lo que permite que un veto del
      verificador no deje rastro y que la slice siga siendo un solo commit sin
      `--amend`.
    - El indice es exactamente lo que sera el commit, asi que el verificador juzga lo
      que ira en la PR y no una aproximacion.

    `--merge-base` conserva la razon de ser del rango de tres puntos que habia antes
    -si la base ha avanzado, sus commits no deben aparecer como borrados y hacer que
    el verificador cace violaciones fantasma- y ademas es la unica forma de
    expresarlo: `git diff --cached base...HEAD` no es sintaxis valida.

    Ojo con lo que esto NO ve: un fichero **untracked** es invisible a `git diff
    --cached`. Por eso `pr-hygiene` corre antes en ese orden -antes tambien de los
    controles, que van entre los dos, no pegado a este subcomando-: es lo que afirma
    que el conjunto staged es igual a la lista que declaro el implementador, y con eso
    le da integridad a este bundle.

    Un indice vacio es FALLA, fail-closed igual que `pr-hygiene` con nada staged: sin nada
    que verificar, un bundle vacio haria que el verificador diera PASA sobre la nada. Es
    tambien el sintoma de haberse olvidado el `git add`.
    """
    rango = ["--merge-base", base]
    try:
        diff = subprocess.run(
            ["git", "-C", repo, "diff", "--cached", *rango],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        names = subprocess.run(
            ["git", "-C", repo, "diff", "--cached", "--name-only", *rango],
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
        return ResultadoBundle(
            passed=False,
            hallazgos=[f"nada staged respecto a {base}: nada que verificar (falta el git add?)"],
        )

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    slice_diff = out_dir / "slice.diff"
    files_txt = out_dir / "files.txt"
    slice_diff.write_text(diff, encoding="utf-8")
    files_txt.write_text("\n".join(ficheros) + "\n", encoding="utf-8")

    return ResultadoBundle(
        passed=True,
        slice_diff=str(slice_diff),
        files=str(files_txt),
        n_files=len(ficheros),
    )


class EstadoCI(StrEnum):
    """Estados de la CI. `VERDE` hay que demostrarlo; el resto son grados de "no consta"."""

    VERDE = "verde"
    ROJO = "rojo"
    PENDIENTE = "pendiente"
    SIN_CHECKS = "sin-checks"
    DESCONOCIDO = "desconocido"


CI_EXIT = {
    EstadoCI.VERDE: 0,
    EstadoCI.ROJO: 1,
    EstadoCI.PENDIENTE: 3,
    EstadoCI.SIN_CHECKS: 4,
    EstadoCI.DESCONOCIDO: 4,
}
"""Exit code por estado, uno por rama del paso 9 para que un tick decida sin parsear JSON.

El 2 esta reservado para error de uso, como en el resto del script. Publico, y no `_CI_EXIT`,
porque estos numeros los documenta el paso 9 de `SKILL.md`: son contrato con quien invoca, no
un detalle interno del clasificador.
"""

_CI_BUCKETS_ROJO = frozenset({"fail", "cancel"})
_CI_BUCKETS_OK = frozenset({"pass", "skipping"})
_CI_BUCKETS = _CI_BUCKETS_ROJO | _CI_BUCKETS_OK | {"pending"}
"""Los `bucket` que documenta `gh pr checks --help`.

Uno fuera de esta lista es una version de `gh` que sabe algo que este script no, y eso es
`desconocido`, no verde.
"""


@dataclass(frozen=True, kw_only=True, slots=True)
class Check:
    """Un check de la PR, tal como lo devuelve `gh pr checks --json`."""

    name: str
    bucket: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "bucket": self.bucket}


@dataclass(frozen=True, kw_only=True, slots=True)
class ResultadoCI:
    """Estado de la CI de una PR, con los checks que lo sostienen."""

    estado: EstadoCI
    checks: list[Check] = field(default_factory=list)
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": "ci-status",
            "estado": str(self.estado),
            "checks": [c.to_dict() for c in self.checks],
            "hallazgos": self.hallazgos,
        }


class _RespuestaIlegibleError(ValueError):
    """La respuesta de `gh` no se lee como una lista de checks: eso siempre es `desconocido`."""


def _lee_checks(stdout: str) -> list[Check]:
    """La respuesta de `gh pr checks --json`, como lista de `Check`.

    Lista vacia es un caso legitimo (`sin-checks`), no un error: lo clasifica quien llama.
    Cualquier otra forma es `_RespuestaIlegibleError`.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        detalle = " ".join(stdout.split())[:200] or "(respuesta vacia)"
        raise _RespuestaIlegibleError(f"respuesta de gh no parseable: {detalle}") from exc

    if not isinstance(data, list):
        raise _RespuestaIlegibleError(f"gh devolvio {type(data).__name__}, se esperaba una lista")
    if any(not isinstance(c, dict) for c in data):
        raise _RespuestaIlegibleError("algun check no es un objeto")
    return [Check(name=str(c.get("name", "")), bucket=str(c.get("bucket", ""))) for c in data]


def _clasifica_checks(checks: list[Check]) -> ResultadoCI:
    """El estado que sostiene esta lista de checks. Fail-closed en cada rama.

    Que todos los checks esten `skipping` es `sin-checks` y no verde: nada ha corrido, asi
    que no hay verde que afirmar.
    """
    if not checks:
        return ResultadoCI(estado=EstadoCI.SIN_CHECKS, hallazgos=["la PR no tiene ningun check"])

    buckets = {c.bucket for c in checks}
    if desconocidos := buckets - _CI_BUCKETS:
        return ResultadoCI(
            estado=EstadoCI.DESCONOCIDO,
            checks=checks,
            hallazgos=[f"bucket que este script no conoce: {sorted(desconocidos)}"],
        )
    if buckets & _CI_BUCKETS_ROJO:
        rotos = sorted(c.name for c in checks if c.bucket in _CI_BUCKETS_ROJO)
        return ResultadoCI(
            estado=EstadoCI.ROJO,
            checks=checks,
            hallazgos=[f"checks en fallo o cancelados: {rotos}"],
        )
    if "pending" in buckets:
        return ResultadoCI(estado=EstadoCI.PENDIENTE, checks=checks)
    if "pass" not in buckets:
        return ResultadoCI(
            estado=EstadoCI.SIN_CHECKS,
            checks=checks,
            hallazgos=["todos los checks se saltaron: nada corrio"],
        )
    return ResultadoCI(estado=EstadoCI.VERDE, checks=checks)


def clasifica_ci(stdout: str) -> ResultadoCI:
    """Mapea la respuesta de `gh pr checks --json` a uno de los `EstadoCI`.

    Funcion pura a proposito: es lo que se testea, sin red y sin `gh` instalado.

    La regla es fail-closed y es la decision central de este subcomando: **solo es
    `verde` un todo-pass explicito con al menos un check que haya pasado de verdad**.
    Todo lo demas cae en `rojo`, `pendiente`, `sin-checks` o `desconocido`. Asi no hay
    que adivinar que hace `gh` ante una PR sin CI configurada, y lo que no se puede
    demostrar verde no lo es.

    En particular, una respuesta que no es JSON valido es `desconocido` y no "todavia
    no hay checks": ese es exactamente el fallo que colgo el primer smoke durante
    cuatro minutos con la CI ya verde.
    """
    try:
        checks = _lee_checks(stdout)
    except _RespuestaIlegibleError as exc:
        return ResultadoCI(estado=EstadoCI.DESCONOCIDO, hallazgos=[str(exc)])
    return _clasifica_checks(checks)


def consulta_ci(repo: str, pr: int) -> ResultadoCI:
    """Pregunta a `gh` por los checks de la PR y clasifica su respuesta.

    Un tiro y sale: **sin `--watch` y sin polling**. El ticking lo hace el harness
    (background mas notificacion), porque un script que poll-ea es justo la shell
    bloqueante que `slice-runner` prohibe.
    """
    proc = subprocess.run(
        ["gh", "pr", "checks", str(pr), "--json", "name,state,bucket"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    result = clasifica_ci(proc.stdout)
    if result.estado is EstadoCI.DESCONOCIDO and proc.stderr.strip():
        detalle = f"stderr de gh: {' '.join(proc.stderr.split())[:200]}"
        return replace(result, hallazgos=[*result.hallazgos, detalle])
    return result


class Severidad(StrEnum):
    """Severidad de un hallazgo del juez. La rubrica vive en `agents/slice-verifier.md`."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class VeredictoJuez(StrEnum):
    """Los dos veredictos que puede emitir el juez adversarial."""

    PASA = "PASA"
    FALLA = "FALLA"


_HALLAZGO_CLAVES = ("regla", "path", "severidad", "evidencia", "detalle")


@dataclass(frozen=True, kw_only=True, slots=True)
class ResultadoVeredicto:
    """Validacion de la forma del veredicto del juez, con los conteos ya hechos."""

    passed: bool
    veredicto: str = ""
    conteo: dict[Severidad, int] = field(default_factory=dict)
    hallazgos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "control": "verify-verdict",
            "veredicto": str(_veredicto_de(self.passed)),
            "veredicto_juez": self.veredicto,
            "conteo": {str(sev): n for sev, n in self.conteo.items()},
            "hallazgos": self.hallazgos,
        }


def _valida_hallazgos(hallazgos: object) -> tuple[list[str], dict[Severidad, int]]:
    """Revisa la lista de hallazgos: devuelve (fallos de forma, conteo por severidad)."""
    conteo = dict.fromkeys(Severidad, 0)
    if not isinstance(hallazgos, list):
        return ([f"hallazgos deberia ser una lista, es {type(hallazgos).__name__}"], conteo)

    fallos: list[str] = []
    for i, h in enumerate(hallazgos):
        if not isinstance(h, dict):
            fallos.append(f"hallazgos[{i}] no es un objeto")
            continue
        if faltan := [k for k in _HALLAZGO_CLAVES if k not in h]:
            fallos.append(f"hallazgos[{i}] sin {faltan}")
        sev = h.get("severidad")
        if sev in conteo:
            conteo[Severidad(sev)] += 1
        else:
            fallos.append(f"hallazgos[{i}] con severidad invalida: {sev!r}")
    return (fallos, conteo)


def valida_veredicto(texto: str) -> ResultadoVeredicto:
    """Comprueba que el mensaje final del juez es su contrato JSON, y cuenta severidades.

    Funcion pura: se testea sin agentes.

    La regla de reinvocar cuando vuelve envuelto en prosa ya existia, pero solo cubria el
    caso obvio. Este control cubre el que no: un JSON **estructuralmente plausible pero
    equivocado** -`"veredicto": "PASS"`, `"severidad": "critical"`, un hallazgo sin
    `evidencia`- que el orquestador leeria como bueno porque "parece" correcto. Leer un
    JSON y decidir si cumple un esquema es regla exacta, no juicio, y el smoke del
    2026-07-30 demostro que la disciplina de salida de ese agente es **estocastica**.

    De paso devuelve `conteo` por severidad, que es lo que alimenta las metricas del paso
    9: antes lo contaba el orquestador a ojo sobre el JSON.

    Un `PASA` con algun hallazgo `alta` es contradiccion interna, porque el contrato dice que
    una `alta` implica FALLA. Al reves NO lo es: el juez puede escalar a FALLA por acumulacion
    de `media`/`baja` explicando por que, y eso esta permitido.
    """
    try:
        data = json.loads(texto)
    except json.JSONDecodeError:
        detalle = " ".join(texto.split())[:200] or "(vacio)"
        return ResultadoVeredicto(passed=False, hallazgos=[f"no es JSON (prosa alrededor?): {detalle}"])

    if not isinstance(data, dict):
        return ResultadoVeredicto(passed=False, hallazgos=[f"se esperaba un objeto, no {type(data).__name__}"])

    fallos: list[str] = []
    veredicto = data.get("veredicto")
    if veredicto not in tuple(VeredictoJuez):
        validos = [str(v) for v in VeredictoJuez]
        fallos.append(f"veredicto invalido: {veredicto!r} (esperado uno de {validos})")

    fallos_forma, conteo = _valida_hallazgos(data.get("hallazgos"))
    fallos += fallos_forma

    if veredicto == VeredictoJuez.PASA and conteo[Severidad.ALTA]:
        fallos.append(f"PASA con {conteo[Severidad.ALTA]} hallazgo(s) de severidad alta")

    return ResultadoVeredicto(passed=not fallos, veredicto=str(veredicto), conteo=conteo, hallazgos=fallos)


def _emit(result: Resultado, as_json: bool) -> int:
    """Humano por defecto, JSON con `--json`: la convencion de los cinco subcomandos.

    La comparte `issue_body.py` y la comprueba `tests/test_skill_contracts.py`.
    """
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[{result.control}] {_veredicto_de(result.passed)}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def _emit_controles(result: ResultadoControles, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[controles] {_veredicto_de(result.passed)}")
        for c in result.controles:
            print(f"  {c.veredicto} {c.nombre} ({c.comando})")
            if c.log:
                print(f"    log: {c.log}")
            for line in c.salida.splitlines():
                print(f"    {line}")
    return 0 if result.passed else 1


def _emit_bundle(result: ResultadoBundle, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[diff-bundle] {_veredicto_de(result.passed)}")
        if result.passed:
            print(f"  slice.diff  {result.slice_diff}")
            print(f"  files.txt   {result.files} ({result.n_files} ficheros)")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def _emit_ci(result: ResultadoCI, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[ci-status] {result.estado}")
        for c in result.checks:
            print(f"  {c.bucket:9} {c.name}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return CI_EXIT[result.estado]


def _emit_veredicto(result: ResultadoVeredicto, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(f"[verify-verdict] {_veredicto_de(result.passed)}")
        if result.passed:
            c = result.conteo
            print(f"  veredicto del juez: {result.veredicto}")
            print(f"  hallazgos: alta={c[Severidad.ALTA]} media={c[Severidad.MEDIA]} baja={c[Severidad.BAJA]}")
        for h in result.hallazgos:
            print(f"  - {h}")
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    """El parser, aparte de `main`, para que un test pueda introspeccionar la superficie CLI."""
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
    bun.add_argument(
        "--base",
        required=True,
        help="rama base (se diffea el INDICE contra el branch-point con esa base)",
    )
    bun.add_argument("--out", required=True, help="directorio destino, FUERA del repo")
    bun.add_argument("--json", action="store_true", help="salida estructurada JSON")

    ci = sub.add_parser("ci-status", help="estado de la CI de una PR (un tiro, sin polling)")
    ci.add_argument("--repo", default=".", help="ruta del repo (default: cwd)")
    ci.add_argument("--pr", required=True, type=int, help="numero de la PR")
    ci.add_argument("--json", action="store_true", help="salida estructurada JSON")

    ver = sub.add_parser("verify-verdict", help="valida la forma del veredicto del juez")
    ver.add_argument(
        "--file",
        required=True,
        help="fichero con el mensaje final del juez, tal cual (FUERA del repo)",
    )
    ver.add_argument("--json", action="store_true", help="salida estructurada JSON")

    return parser


def _cmd_pr_hygiene(args: argparse.Namespace) -> int:
    return _emit(comprueba_higiene_pr(args.repo, args.allow, args.spec), args.json)


def _cmd_diff_bundle(args: argparse.Namespace) -> int:
    return _emit_bundle(escribe_diff_bundle(args.repo, args.base, args.out), args.json)


def _cmd_ci_status(args: argparse.Namespace) -> int:
    return _emit_ci(consulta_ci(args.repo, args.pr), args.json)


def _cmd_verify_verdict(args: argparse.Namespace) -> int:
    """No poder leer el fichero es error de uso (exit 2), no FALLA.

    El fichero lo escribe el orquestador, y confundir su propio despiste con un veredicto
    invalido le haria reinvocar al juez por nada.
    """
    try:
        texto = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: no se pudo leer {args.file}: {exc}", file=sys.stderr)
        return 2
    return _emit_veredicto(valida_veredicto(texto), args.json)


def _cmd_controles(args: argparse.Namespace) -> int:
    """Un `--control` ausente o mal formado es error de uso (exit 2), no FALLA de control.

    Confundirlos haria que el orquestador reintentara el paso 5 por un fallo que esta en su
    propia invocacion.
    """
    if not args.control:
        print("error: controles necesita al menos un --control nombre=comando", file=sys.stderr)
        return 2
    try:
        specs = [parse_control_spec(s) for s in args.control]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    opciones = OpcionesControl(repo=args.repo, tail_lines=args.tail, timeout=args.timeout, out=args.out)
    return _emit_controles(ejecuta_controles(specs, opciones), args.json)


_COMANDOS: dict[str, Callable[[argparse.Namespace], int]] = {
    "pr-hygiene": _cmd_pr_hygiene,
    "controles": _cmd_controles,
    "diff-bundle": _cmd_diff_bundle,
    "ci-status": _cmd_ci_status,
    "verify-verdict": _cmd_verify_verdict,
}


def main(argv: list[str] | None = None) -> int:
    """Enruta al subcomando.

    El dispatch es una tabla y no cinco `if` seguidos: cada subcomando tiene su funcion, asi
    que la validacion de `--control` y la lectura del fichero del juez viven donde se usan en
    vez de mezcladas con el enrutado.
    """
    args = build_parser().parse_args(argv)
    return _COMANDOS[args.subcomando](args)


if __name__ == "__main__":
    sys.exit(main())
