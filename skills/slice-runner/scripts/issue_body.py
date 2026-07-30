#!/usr/bin/env python3
"""Logica pura del cuerpo del issue de GitHub (fuente de verdad del estado).

El estado del run vive en el cuerpo de un issue de GitHub: no hay estado local. Este
modulo NO habla con `gh` (eso es I/O, lo valida el smoke real); solo transforma texto:

    parse_body(body)                     cuerpo del issue -> lista de Slice con estado
    set_slice_estado(body, id, estado)   reescribe la linea de una slice, preserva el resto

`slice-runner` compone: lee el body (I/O gh) -> transforma aqui (puro) -> escribe el body
(I/O gh). Al ser puro, se testea offline sin mocks de gh.

Formato de una linea de slice en el cuerpo:

    - [ ] slice-02 (ajustar-stock): Caso de uso AjustarStock [esperando-merge] PR #12
          INTENCION: hoy el ajuste se hace a mano en la consola y nadie sabe quien lo hizo
          ACEPTACION: emite evento StockAjustado
          SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
    - [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11
    - [ ] slice-04 (backfill): Backfill [bloqueada: ci-roja] PR #13
    - [ ] slice-05 (alerta-ajuste): Alerta de ajustes fallidos [pendiente]
          REPO: mercadona/mercadona.online.gke

El marcador `[estado]` va al final (antes del opcional `PR #N`). El checkbox `[x]` es la
verdad de "mergeada": una slice marcada esta mergeada aunque el texto diga otra cosa.

Bajo cada slice, cuatro tipos de linea indentada:

    INTENCION:  que esta mal hoy y deja de estarlo con esta slice; alimenta el cuerpo de la PR.
    ACEPTACION: criterio de aceptacion, verificable pre-merge (test + verificador).
    SENAL:      como se comprueba viva en produccion; la consume `deploy-watch`.
    REPO:       repo destino de la slice. Ausente = el repo del issue (el de la app).

`ACEPTACION:` se llamaba `AC:`, y el parser sigue aceptando la forma vieja: hay issues abiertos
que la usan. Lo que se documenta y se emite es el nombre completo. Por el mismo motivo, el
motivo de bloqueo `puertas` se normaliza a `controles` al parsear (ver `normaliza_motivo`).

A nivel de feature, el cuerpo trae dos secciones que `slice-spec` escribe y `slice-runner` solo
lee: `## Intencion` (el problema entero, ver `parse_intencion`) y `## Controles` (los comandos
deterministas del repo, ver `parse_controles`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

# Estados canonicos de una slice.
ESTADOS = (
    "pendiente",
    "en-curso",
    "esperando-merge",
    "mergeada",
    "bloqueada",
    "abortada",
)

# Motivos canonicos de `bloqueada`. `puertas` es como se llamaba `controles` antes del
# renombrado, y hay issues abiertos con ese marcador escrito en el cuerpo: se normaliza al
# parsear para que nadie aguas abajo tenga que conocer las dos formas. Mismo trato que
# `AC:` -> `ACEPTACION:`.
MOTIVOS_BLOQUEADA = (
    "sin-subagentes",
    "controles",
    "verify",
    "ci-roja",
    # La CI no se pudo medir: no hay checks, o la respuesta de `gh` no era legible. No es
    # `ci-roja` -mentiria en el registro duradero- ni `esperando-merge` -afirmaria un verde
    # que no hubo-. Lo emite el paso 9 desde `controles.py ci-status`.
    "ci-indeterminada",
)
_MOTIVOS_VIEJOS = {"puertas": "controles"}

# Una linea de slice: checkbox, id `slice-NN`, `(name)` o `(type: name)` opcional, titulo,
# marcador `[estado]` opcional y `PR #N` opcional. Cualquier `- [ ]` que no sea `slice-NN`
# se ignora (no es una slice): endurecido igual que el parser del antiguo panel.
_LINE_RE = re.compile(
    r"^\s*-\s*\[([ xX])\]\s*"
    r"(slice[-\w]+)\s*"
    r"(?:\(([^)]*)\))?\s*"
    r":\s*"
    r"(.*?)"
    r"\s*(?:\[([^\]]+)\])?"
    r"\s*(?:PR\s*#(\d+))?\s*$"
)

# Lineas indentadas bajo una slice. `SENAL` se acepta con y sin tilde (lo escribe una
# persona en un issue de GitHub, y "SEÑAL:" no debe perderse en silencio); el formato
# canonico que se documenta y se emite es `SENAL:`.
_SENAL_LINE_RE = re.compile(r"^SE(?:N|Ñ)AL\s*:\s*(.*)$", re.IGNORECASE)
_REPO_LINE_RE = re.compile(r"^REPO\s*:\s*(.+?)\s*$", re.IGNORECASE)
# `INTENCION` se acepta con y sin tilde por el mismo motivo que `SENAL`: la escribe una
# persona en un issue de GitHub y no debe perderse en silencio.
_INTENCION_LINE_RE = re.compile(r"^INTENCI(?:O|Ó)N\s*:\s*(.*)$", re.IGNORECASE)
# `ACEPTACION` es el nombre canonico; `AC` es la forma vieja, que se sigue aceptando porque
# hay issues abiertos escritos con ella (misma tolerancia que con `SEÑAL`).
_ACEPTACION_LINE_RE = re.compile(r"^(?:ACEPTACI(?:O|Ó)N|AC)\s*:\s*(.*)$", re.IGNORECASE)

# --- Intencion de la feature (el problema entero, no el de una slice) ---
# Vive en una seccion `## Intencion` del cuerpo, antes de las fuentes y las slices. Cuenta
# que esta mal hoy y como se nota, no como se va a arreglar. `slice-spec` la escribe;
# `slice-runner` la lee para el cuerpo de la PR.
_INTENCION_HEADING_RE = re.compile(r"^\s*##\s+intenci[oó]n\s*$", re.IGNORECASE)

# --- Fuentes de convencion (punteros a la vara de medir del repo) ---
# Viven en una seccion `## Fuentes de convencion` del cuerpo del issue. Son punteros
# (no contenido): `doc:` para convenciones declarativas y `skill:` para skills de
# proyecto (patrones procedimentales). `slice-spec` las escribe tras descubrirlas y
# confirmarlas; `slice-runner` solo las lee como vara de medir. Guardar el "donde" (no
# el contenido) evita duplicar la fuente de verdad, que sigue viviendo en el repo.
#
# Son **por repo**: una slice con `REPO:` se mide con la vara de SU repo destino, no con
# la del repo de la app. Las lineas antes de cualquier `### <org>/<repo>` son las del
# repo del issue; cada subseccion `###` declara las de un repo destino.
FUENTE_TIPOS = ("doc", "skill")

_FUENTES_HEADING = "## Fuentes de convencion"
_FUENTES_HEADING_RE = re.compile(r"^\s*##\s+fuentes\s+de\s+convenci[oó]n\s*$", re.IGNORECASE)
_H2_RE = re.compile(r"^\s*##\s+")
_SUBHEADING_RE = re.compile(r"^\s*###\s+(.+?)\s*$")
_FUENTE_LINE_RE = re.compile(r"^\s*-\s*(doc|skill)\s*:\s*(.+?)\s*$", re.IGNORECASE)

# --- Controles deterministas (los comandos con los que se mide el repo) ---
# Viven en una seccion `## Controles` del cuerpo del issue, con la misma forma por repo
# que las fuentes. Antes los deducia `slice-runner` leyendo el `Makefile` al principio de
# cada slice: eso metia el Makefile en el contexto del agente de vida mas larga del loop,
# lo repetia en cada slice y no lo confirmaba nadie. Ahora `slice-spec` los descubre una
# vez, la persona los confirma y quedan escritos aqui; `slice-runner` solo los lee.
#
# Declararlos en el issue tiene un segundo efecto: la vara es texto publico. Si los
# eligiera el implementador, el juzgado estaria definiendo la vara con la que se le juzga
# y bastaria `compliance-bias` para que acabara midiendose con `make test-unit`.
#
# El nombre reservado `ninguno` declara que el repo no tiene controles reales (el de
# paneles de Grafana: la CI solo publica en master, no valida en PR). Vacio y eximido no
# son lo mismo, igual que en `SENAL: exenta`.
CONTROL_EXENTO = "ninguno"

_CONTROLES_HEADING = "## Controles"
_CONTROLES_HEADING_RE = re.compile(r"^\s*##\s+controles\s*$", re.IGNORECASE)
_CONTROL_LINE_RE = re.compile(r"^\s*-\s*([\w-]+)\s*:\s*(.+?)\s*$")


@dataclass
class Slice:
    """Una slice tal como vive en el cuerpo del issue.

    `intencion` es que esta mal hoy y deja de estarlo con esta slice (alimenta el cuerpo de
    la PR); `aceptacion` son los criterios verificables pre-merge; `senal` es como se comprueba
    viva en produccion (la consume `deploy-watch`). `repo` es el repo destino: `None` = el repo
    del issue, y cualquier otro valor = slice cross-repo (p. ej. una alerta que vive en
    el repo de manifiestos, o un panel de Grafana).
    """

    slice_id: str
    name: str
    type: str
    title: str
    estado: str
    motivo: str = ""
    pr: int | None = None
    intencion: list[str] = field(default_factory=list)
    aceptacion: list[str] = field(default_factory=list)
    senal: list[str] = field(default_factory=list)
    repo: str | None = None


@dataclass
class Fuente:
    """Un puntero a una fuente de convencion de un repo.

    `tipo` es `doc` (convencion declarativa: CLAUDE.md, docs de reglas...) o `skill`
    (skill de proyecto que codifica un patron). `ruta` es la ruta relativa al repo.
    `repo` es el repo al que aplica: `None` = el repo del issue (el de la app).
    """

    tipo: str
    ruta: str
    repo: str | None = None


@dataclass
class Control:
    """Un control determinista declarado para un repo: `nombre: comando`.

    Los nombres son libres (`lint`, `types`, `tests`, pero tambien `schema` en un repo de
    manifiestos): el script que los ejecuta no sabe nada de toolchains, solo corre lo que se
    le pasa. `repo` es el repo al que aplica: `None` = el repo del issue.

    El nombre reservado `ninguno` no es un control sino una **exencion declarada**: el repo no
    tiene controles reales y su `comando` es en realidad el motivo (ver `exento` y `motivo`).
    """

    nombre: str
    comando: str
    repo: str | None = None

    @property
    def exento(self) -> bool:
        """True si esta linea declara que el repo no tiene controles, en vez de declarar uno."""
        return self.nombre.lower() == CONTROL_EXENTO

    @property
    def motivo(self) -> str:
        """El motivo de la exencion; cadena vacia si esto es un control de verdad."""
        return self.comando if self.exento else ""


def normaliza_motivo(motivo: str) -> str:
    """Motivo de bloqueo en su forma canonica (`puertas` -> `controles`).

    La forma vieja esta escrita en cuerpos de issues abiertos, que no se pueden renombrar por
    edicion. Normalizar al parsear deja la compatibilidad en un solo sitio.
    """
    limpio = motivo.strip()
    return _MOTIVOS_VIEJOS.get(limpio.lower(), limpio)


def _split_type_name(paren: str | None) -> tuple[str, str]:
    """`(name)` -> (feat, name); `(type: name)` -> (type, name); vacio -> (feat, '')."""
    if not paren:
        return ("feat", "")
    paren = paren.strip()
    if ":" in paren:
        type_, name = paren.split(":", 1)
        return (type_.strip(), name.strip())
    return ("feat", paren)


def _slice_from_match(m: re.Match[str]) -> Slice:
    box = m.group(1).lower()
    type_, name = _split_type_name(m.group(3))
    title = (m.group(4) or "").strip()
    marcador = (m.group(5) or "").strip()
    pr = int(m.group(6)) if m.group(6) else None

    if box == "x":
        # El checkbox manda: marcada = mergeada.
        estado, motivo = "mergeada", ""
    elif marcador:
        if ":" in marcador:
            estado, raw_motivo = (p.strip() for p in marcador.split(":", 1))
            motivo = normaliza_motivo(raw_motivo)
        else:
            estado, motivo = marcador, ""
    else:
        estado, motivo = "pendiente", ""

    return Slice(m.group(2), name, type_, title, estado, motivo, pr)


def render_slice_line(sl: Slice) -> str:
    """Renderiza la linea de una slice en el formato canonico del cuerpo."""
    box = "x" if sl.estado == "mergeada" else " "
    if sl.name:
        paren = f" ({sl.name})" if sl.type == "feat" else f" ({sl.type}: {sl.name})"
    else:
        paren = ""
    marcador = f"{sl.estado}: {sl.motivo}" if sl.motivo else sl.estado
    line = f"- [{box}] {sl.slice_id}{paren}: {sl.title} [{marcador}]"
    if sl.pr is not None:
        line += f" PR #{sl.pr}"
    return line


def parse_body(body: str) -> list[Slice]:
    """Extrae las slices (estado, INTENCION, ACEPTACION, SENAL y REPO), en orden de aparicion."""
    slices: list[Slice] = []
    current: Slice | None = None
    for line in body.splitlines():
        m = _LINE_RE.match(line)
        if m:
            current = _slice_from_match(m)
            slices.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        if intencion := _INTENCION_LINE_RE.match(stripped):
            current.intencion.append(intencion.group(1).strip())
            continue
        if aceptacion := _ACEPTACION_LINE_RE.match(stripped):
            current.aceptacion.append(aceptacion.group(1).strip())
            continue
        if senal := _SENAL_LINE_RE.match(stripped):
            current.senal.append(senal.group(1).strip())
            continue
        if repo := _REPO_LINE_RE.match(stripped):
            current.repo = repo.group(1)
    return slices


def set_slice_estado(
    body: str,
    slice_id: str,
    estado: str,
    *,
    pr: int | None = None,
    motivo: str = "",
) -> str:
    """Reescribe la linea de `slice_id` con el nuevo estado; preserva el resto del cuerpo.

    Read-modify-write puro: mantiene name/type/titulo y las lineas hijas (INTENCION,
    ACEPTACION, SENAL, REPO) intactos. Si `pr` es None, conserva
    el PR que ya tuviera la linea. Lanza KeyError si la slice no esta en el cuerpo y ValueError
    si el estado no es canonico.
    """
    if estado not in ESTADOS:
        raise ValueError(f"estado no valido: {estado!r} (validos: {', '.join(ESTADOS)})")

    out: list[str] = []
    changed = False
    for line in body.splitlines():
        m = _LINE_RE.match(line)
        if m and m.group(2) == slice_id:
            sl = _slice_from_match(m)
            sl.estado = estado
            sl.motivo = motivo
            if pr is not None:
                sl.pr = pr
            out.append(render_slice_line(sl))
            changed = True
        else:
            out.append(line)

    if not changed:
        raise KeyError(f"slice {slice_id!r} no encontrada en el cuerpo del issue")

    result = "\n".join(out)
    return result + "\n" if body.endswith("\n") else result


def parse_intencion(body: str) -> str | None:
    """El texto de la seccion `## Intencion` del cuerpo, o `None` si la seccion no existe.

    Distingue tres casos que el cuerpo de la PR trata distinto: seccion ausente (`None`, la
    intencion habra que inferirla y decirlo), presente pero vacia (`""`, misma degradacion) y
    declarada (el texto). Que lo decida un script y no el criterio del agente es lo que evita
    que una PR afirme "intencion declarada" cuando nadie la escribio.
    """
    if not any(_INTENCION_HEADING_RE.match(line) for line in body.splitlines()):
        return None

    collected: list[str] = []
    in_section = False
    for line in body.splitlines():
        if _INTENCION_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section:
            if _H2_RE.match(line):  # empieza otra seccion: la de intencion acabo
                break
            collected.append(line)
    return "\n".join(collected).strip()


def _tiene_seccion(body: str, heading_re: re.Pattern[str]) -> bool:
    """True si el cuerpo tiene esa seccion, aunque este vacia."""
    return any(heading_re.match(line) for line in body.splitlines())


def _iter_seccion(body: str, heading_re: re.Pattern[str]) -> Iterator[tuple[str | None, str]]:
    """Recorre las lineas de una seccion por repo, como `(repo, linea)`.

    Se detiene en el siguiente `## `. Una subseccion `### <org>/<repo>` atribuye las lineas
    que le siguen a ese repo destino; las de antes van con `repo=None` (el repo del issue).
    Lo comparten las secciones `## Fuentes de convencion` y `## Controles`, que tienen la
    misma forma por repo y existen por la misma razon.
    """
    in_section = False
    repo: str | None = None
    for line in body.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if _H2_RE.match(line):  # empieza otra seccion: esta acabo
            return
        if sub := _SUBHEADING_RE.match(line):
            repo = sub.group(1)
            continue
        yield repo, line


def _repos_en_orden(items: Iterable[Fuente | Control]) -> list[str]:
    """Los repos destino citados, sin repetir y en orden de aparicion."""
    repos: list[str] = []
    for item in items:
        if item.repo is not None and item.repo not in repos:
            repos.append(item.repo)
    return repos


def _upsert_seccion(body: str, heading_re: re.Pattern[str], section: str) -> str:
    """Reemplaza la seccion si existe, la anade al final si no; preserva el resto del cuerpo."""
    section_lines = section.splitlines()
    lines = body.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    replaced = False
    while i < n:
        if heading_re.match(lines[i]):
            out.extend(section_lines)
            i += 1
            while i < n and not _H2_RE.match(lines[i]):  # descarta la seccion vieja
                i += 1
            if i < n:  # separa de la siguiente seccion con una linea en blanco
                out.append("")
            replaced = True
            continue
        out.append(lines[i])
        i += 1

    if not replaced:
        if out and out[-1].strip() != "":
            out.append("")
        out.extend(section_lines)

    result = "\n".join(out)
    return result + "\n" if body.endswith("\n") else result


def tiene_seccion_fuentes(body: str) -> bool:
    """True si el cuerpo tiene la seccion `## Fuentes de convencion` (aunque este vacia).

    Distingue "seccion ausente" (el issue nunca la declaro -> `slice-runner` para y pide
    generarla con `slice-spec`) de "seccion presente pero vacia".
    """
    return _tiene_seccion(body, _FUENTES_HEADING_RE)


def parse_fuentes(body: str) -> list[Fuente]:
    """Extrae los punteros de la seccion `## Fuentes de convencion`, en orden.

    Devuelve `[]` si la seccion no existe o esta vacia. Solo lee las lineas `- doc: ...`
    y `- skill: ...`. Para filtrar por repo destino, `fuentes_para`.
    """
    fuentes: list[Fuente] = []
    for repo, line in _iter_seccion(body, _FUENTES_HEADING_RE):
        if m := _FUENTE_LINE_RE.match(line):
            fuentes.append(Fuente(m.group(1).lower(), m.group(2).strip(), repo))
    return fuentes


def fuentes_para(fuentes: Iterable[Fuente], repo: str | None = None) -> list[Fuente]:
    """Las fuentes que aplican a `repo` (`None` = el repo del issue).

    La vara de medir de una slice es la de SU repo destino: medir una alerta del repo de
    manifiestos con las convenciones del repo de la app es el `silent-misalignment` que la
    seccion de fuentes existe para evitar.
    """
    return [f for f in fuentes if f.repo == repo]


def render_fuentes_section(fuentes: Iterable[Fuente]) -> str:
    """Renderiza la seccion completa (heading + lineas) en formato canonico, sin `\\n` final.

    Las del repo del issue van primero; cada repo destino va en su subseccion
    `### <repo>`, en orden de aparicion. Lanza ValueError si algun `tipo` no es canonico.
    """
    fuentes = list(fuentes)
    for f in fuentes:
        if f.tipo not in FUENTE_TIPOS:
            raise ValueError(
                f"tipo de fuente no valido: {f.tipo!r} (validos: {', '.join(FUENTE_TIPOS)})"
            )

    lines = [_FUENTES_HEADING]
    lines += [f"- {f.tipo}: {f.ruta}" for f in fuentes if f.repo is None]
    for repo in _repos_en_orden(fuentes):
        lines += ["", f"### {repo}"]
        lines += [f"- {f.tipo}: {f.ruta}" for f in fuentes if f.repo == repo]

    return "\n".join(lines)


def set_fuentes(body: str, fuentes: Iterable[Fuente]) -> str:
    """Upsert de la seccion de fuentes: reemplaza si existe, la anade al final si no.

    Read-modify-write puro que preserva el resto del cuerpo (intro, slices, criterios). Valida
    los tipos via `render_fuentes_section`.
    """
    return _upsert_seccion(body, _FUENTES_HEADING_RE, render_fuentes_section(fuentes))


def tiene_seccion_controles(body: str) -> bool:
    """True si el cuerpo tiene la seccion `## Controles` (aunque este vacia).

    Distingue "seccion ausente" (el issue nunca la declaro -> `slice-runner` para y pide
    generarla con `slice-spec validate`) de "seccion presente pero vacia". Sin controles
    declarados no se ejecuta: fail-closed, igual que con las fuentes de convencion.
    """
    return _tiene_seccion(body, _CONTROLES_HEADING_RE)


def parse_controles(body: str) -> list[Control]:
    """Extrae los pares `nombre: comando` de la seccion `## Controles`, en orden.

    Devuelve `[]` si la seccion no existe o esta vacia. Una linea `- ninguno: <motivo>` sale
    como un `Control` con `exento` a True. Para filtrar por repo destino, `controles_para`.
    """
    controles: list[Control] = []
    for repo, line in _iter_seccion(body, _CONTROLES_HEADING_RE):
        if m := _CONTROL_LINE_RE.match(line):
            controles.append(Control(m.group(1).strip(), m.group(2).strip(), repo))
    return controles


def controles_para(controles: Iterable[Control], repo: str | None = None) -> list[Control]:
    """Los controles que aplican a `repo` (`None` = el repo del issue).

    Una slice con `REPO:` se mide con los controles de SU repo destino: correr `make test` de
    la app contra el repo de manifiestos no valida nada, y heredar los controles del repo del
    issue es la misma desviacion silenciosa que heredar su vara de medir.
    """
    return [c for c in controles if c.repo == repo]


def render_controles_section(controles: Iterable[Control]) -> str:
    """Renderiza la seccion completa (heading + lineas) en formato canonico, sin `\\n` final.

    Los del repo del issue van primero; cada repo destino va en su subseccion `### <repo>`, en
    orden de aparicion. Lanza ValueError si un repo mezcla la exencion `ninguno` con controles
    de verdad: "no hay controles" y "hay estos" no pueden ser ciertas a la vez, y dejarlo pasar
    haria que la ejecucion dependiera de cual se leyera primero.
    """
    controles = list(controles)
    for repo in [None, *_repos_en_orden(controles)]:
        del_repo = [c for c in controles if c.repo == repo]
        if any(c.exento for c in del_repo) and len(del_repo) > 1:
            donde = repo or "el repo del issue"
            raise ValueError(f"{donde}: la exencion '{CONTROL_EXENTO}' no admite otros controles")

    lines = [_CONTROLES_HEADING]
    lines += [f"- {c.nombre}: {c.comando}" for c in controles if c.repo is None]
    for repo in _repos_en_orden(controles):
        lines += ["", f"### {repo}"]
        lines += [f"- {c.nombre}: {c.comando}" for c in controles if c.repo == repo]

    return "\n".join(lines)


def set_controles(body: str, controles: Iterable[Control]) -> str:
    """Upsert de la seccion de controles: reemplaza si existe, la anade al final si no.

    Read-modify-write puro que preserva el resto del cuerpo. Valida via
    `render_controles_section`.
    """
    return _upsert_seccion(body, _CONTROLES_HEADING_RE, render_controles_section(controles))


# --- CLI ---------------------------------------------------------------------
#
# Todo lo de arriba es puro y se testea sin `gh`. Esto de abajo es la capa de I/O, y existe
# porque sin ella el agente escribia el read-modify-write a mano en cada transicion: un
# `python3 -c` con `sys.path.insert`, `gh issue view --json body`, la llamada, y `gh issue
# edit --body-file`. En una sola sesion se escribio **seis veces**, y cada copia es una
# ocasion de equivocarse en silencio (el `--json body -q .body` mal puesto devuelve cadena
# vacia y el edit deja el issue en blanco). Leer un issue, reescribir una linea y
# guardarlo es regla exacta, no juicio: `offload-deterministic`.
#
# El nucleo sigue siendo puro: estas funciones solo orquestan `gh` alrededor de las de
# arriba. Los tests apuntan al nucleo, como en `controles.py` con `clasifica_ci`.

_GH_TIMEOUT = 60


def _gh_body(repo: str, issue: int) -> str:
    """Cuerpo actual del issue. Falla ruidosamente: un cuerpo vacio nunca es aceptable."""
    proc = subprocess.run(
        ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body", "-q", ".body"],
        capture_output=True,
        text=True,
        check=False,
        timeout=_GH_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh issue view fallo: {proc.stderr.strip() or proc.returncode}")
    if not proc.stdout.strip():
        raise RuntimeError(f"el cuerpo de {repo}#{issue} vino vacio: no se reescribe nada")
    return proc.stdout


def _gh_set_body(repo: str, issue: int, body: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        tmp = fh.name
    try:
        proc = subprocess.run(
            ["gh", "issue", "edit", str(issue), "--repo", repo, "--body-file", tmp],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh issue edit fallo: {proc.stderr.strip() or proc.returncode}")
    finally:
        os.unlink(tmp)


def rama_de(slice_: Slice) -> str:
    """`slice-01` + `cantidad-vo` -> `slice/01-cantidad-vo`. Determinista, no un slug a ojo."""
    numero = slice_.slice_id.removeprefix("slice-")
    return f"slice/{numero}-{slice_.name}" if slice_.name else f"slice/{numero}"


def scope_de(slice_: Slice) -> str:
    """El scope del conventional commit: `feat(cantidad-vo)`."""
    return f"{slice_.type}({slice_.name})" if slice_.name else slice_.type


def _slice_info(slice_: Slice) -> dict[str, object]:
    return {
        "slice_id": slice_.slice_id,
        "name": slice_.name,
        "type": slice_.type,
        "titulo": slice_.title,
        "estado": slice_.estado,
        "motivo": slice_.motivo,
        "pr": slice_.pr,
        "repo": slice_.repo,
        "intencion": slice_.intencion,
        "aceptacion": slice_.aceptacion,
        "senal": slice_.senal,
        "rama": rama_de(slice_),
        "scope": scope_de(slice_),
    }


def _cmd_show(args: argparse.Namespace) -> int:
    body = _gh_body(args.repo, args.issue)
    slices = parse_body(body)
    if not slices:
        print("error: el cuerpo no tiene ninguna linea de slice valida", file=sys.stderr)
        return 2

    if args.slice:
        elegida = next((s for s in slices if s.slice_id == args.slice), None)
        if elegida is None:
            print(f"error: {args.slice} no esta en el issue", file=sys.stderr)
            return 2
    else:
        # La siguiente pendiente. Una en `esperando-merge` se retoma ahi, asi que tambien
        # cuenta como "no terminada" y sale antes que una pendiente posterior.
        elegida = next((s for s in slices if s.estado not in ("mergeada",)), None)
        if elegida is None:
            print(json.dumps({"slices": len(slices), "slice": None}, ensure_ascii=False))
            return 0

    out = {
        "slices": len(slices),
        "intencion_feature": parse_intencion(body),
        "tiene_seccion_fuentes": tiene_seccion_fuentes(body),
        "tiene_seccion_controles": tiene_seccion_controles(body),
        "fuentes": [
            {"tipo": f.tipo, "ruta": f.ruta}
            for f in fuentes_para(parse_fuentes(body), elegida.repo)
        ],
        "controles": [
            {"nombre": c.nombre, "comando": c.comando, "exento": c.exento, "motivo": c.motivo}
            for c in controles_para(parse_controles(body), elegida.repo)
        ],
        "slice": _slice_info(elegida),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _cmd_set_estado(args: argparse.Namespace) -> int:
    # `set_slice_estado` es puro y no valida el motivo: acepta cualquier cadena. Eso deja
    # que un motivo inventado acabe escrito en el registro duradero, donde ya no se puede
    # renombrar (paso lo mismo con `puertas`). La validacion vive aqui, en la frontera de
    # escritura, que es el unico sitio donde hay un exit code que la haga cumplir.
    if args.estado == "bloqueada":
        if args.motivo not in MOTIVOS_BLOQUEADA:
            print(
                f"error: bloqueada exige un motivo canonico, uno de {list(MOTIVOS_BLOQUEADA)}"
                f" (recibido: {args.motivo!r})",
                file=sys.stderr,
            )
            return 2
    elif args.motivo and args.estado != "abortada":
        # `abortada` se deja libre a proposito: su vocabulario aun no esta canonicalizado
        # (la skill solo documenta `presupuesto`), y fijarlo aqui seria decidirlo de
        # tapadillo. Para el resto de estados un motivo es ruido que nadie lee.
        print(f"error: el estado {args.estado} no lleva motivo", file=sys.stderr)
        return 2

    body = _gh_body(args.repo, args.issue)
    try:
        nuevo = set_slice_estado(
            body, args.slice, args.estado, pr=args.pr, motivo=args.motivo or ""
        )
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if nuevo == body:
        print(f"sin cambios: {args.slice} ya estaba asi")
        return 0
    _gh_set_body(args.repo, args.issue, nuevo)
    linea = next(
        (ln for ln in nuevo.splitlines() if args.slice in ln and ln.lstrip().startswith("- [")),
        "",
    )
    print(f"{args.repo}#{args.issue} {args.slice} -> {args.estado}\n{linea.strip()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lee y actualiza el estado del run en el issue")
    sub = parser.add_subparsers(dest="subcomando", required=True)

    sh = sub.add_parser("show", help="parsea el issue y emite lo que necesita el paso 1")
    sh.add_argument("--repo", required=True, help="org/repo del issue")
    sh.add_argument("--issue", required=True, type=int)
    sh.add_argument(
        "--slice", default=None, help="slice concreta (default: la siguiente sin cerrar)"
    )
    sh.add_argument("--pretty", action="store_true", help="JSON indentado")

    st = sub.add_parser("set-estado", help="reescribe la linea de una slice en el issue")
    st.add_argument("--repo", required=True, help="org/repo del issue")
    st.add_argument("--issue", required=True, type=int)
    st.add_argument("--slice", required=True, help="p. ej. slice-01")
    st.add_argument("--estado", required=True, choices=ESTADOS)
    st.add_argument(
        "--motivo", default=None, help=f"para bloqueada: uno de {list(MOTIVOS_BLOQUEADA)}"
    )
    st.add_argument("--pr", type=int, default=None, help="numero de PR (se conserva si no se pasa)")

    args = parser.parse_args(argv)
    try:
        if args.subcomando == "show":
            return _cmd_show(args)
        return _cmd_set_estado(args)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
