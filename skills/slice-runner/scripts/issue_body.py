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
          AC: emite evento StockAjustado
          SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
    - [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11
    - [ ] slice-04 (backfill): Backfill [bloqueada: ci-roja] PR #13
    - [ ] slice-05 (alerta-ajuste): Alerta de ajustes fallidos [pendiente]
          REPO: mercadona/mercadona.online.gke

El marcador `[estado]` va al final (antes del opcional `PR #N`). El checkbox `[x]` es la
verdad de "mergeada": una slice marcada esta mergeada aunque el texto diga otra cosa.

Bajo cada slice, cuatro tipos de linea indentada:

    INTENCION: que esta mal hoy y deja de estarlo con esta slice; alimenta el cuerpo de la PR.
    AC:        criterio de aceptacion, verificable pre-merge (test + verificador).
    SENAL:     como se comprueba viva en produccion; la consume `deploy-watch`.
    REPO:      repo destino de la slice. Ausente = el repo del issue (el de la app).

A nivel de feature, la seccion `## Intencion` cuenta el problema entero (ver `parse_intencion`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
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
_FUENTES_SUBHEADING_RE = re.compile(r"^\s*###\s+(.+?)\s*$")
_FUENTE_LINE_RE = re.compile(r"^\s*-\s*(doc|skill)\s*:\s*(.+?)\s*$", re.IGNORECASE)


@dataclass
class Slice:
    """Una slice tal como vive en el cuerpo del issue.

    `intencion` es que esta mal hoy y deja de estarlo con esta slice (alimenta el cuerpo de
    la PR); `ac` son los criterios verificables pre-merge; `senal` es como se comprueba viva
    en produccion (la consume `deploy-watch`). `repo` es el repo destino: `None` = el repo
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
    ac: list[str] = field(default_factory=list)
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
            estado, motivo = (p.strip() for p in marcador.split(":", 1))
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
    """Extrae las slices (estado, INTENCION, AC, SENAL y REPO) del cuerpo, en orden de aparicion."""
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
        if stripped.startswith("AC:"):
            current.ac.append(stripped[len("AC:") :].strip())
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

    Read-modify-write puro: mantiene name/type/titulo y las lineas hijas (INTENCION, AC,
    SENAL, REPO) intactos. Si `pr` es None, conserva
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


def tiene_seccion_fuentes(body: str) -> bool:
    """True si el cuerpo tiene la seccion `## Fuentes de convencion` (aunque este vacia).

    Distingue "seccion ausente" (el issue nunca la declaro -> `slice-runner` para y pide
    generarla con `slice-spec`) de "seccion presente pero vacia".
    """
    return any(_FUENTES_HEADING_RE.match(line) for line in body.splitlines())


def parse_fuentes(body: str) -> list[Fuente]:
    """Extrae los punteros de la seccion `## Fuentes de convencion`, en orden.

    Devuelve `[]` si la seccion no existe o esta vacia. Solo lee las lineas `- doc: ...`
    y `- skill: ...` que van bajo el heading, hasta el siguiente `## `. Una subseccion
    `### <org>/<repo>` atribuye las lineas que le siguen a ese repo destino; las de antes
    quedan con `repo=None` (el repo del issue). Para filtrar, `fuentes_para`.
    """
    fuentes: list[Fuente] = []
    in_section = False
    repo: str | None = None
    for line in body.splitlines():
        if _FUENTES_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section:
            if _H2_RE.match(line):  # empieza otra seccion: la de fuentes acabo
                break
            if sub := _FUENTES_SUBHEADING_RE.match(line):
                repo = sub.group(1)
                continue
            m = _FUENTE_LINE_RE.match(line)
            if m:
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

    repos: list[str] = []
    for f in fuentes:
        if f.repo is not None and f.repo not in repos:
            repos.append(f.repo)
    for repo in repos:
        lines += ["", f"### {repo}"]
        lines += [f"- {f.tipo}: {f.ruta}" for f in fuentes if f.repo == repo]

    return "\n".join(lines)


def set_fuentes(body: str, fuentes: Iterable[Fuente]) -> str:
    """Upsert de la seccion de fuentes: reemplaza si existe, la anade al final si no.

    Read-modify-write puro que preserva el resto del cuerpo (intro, slices, AC). Valida
    los tipos via `render_fuentes_section`.
    """
    section_lines = render_fuentes_section(fuentes).splitlines()
    lines = body.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    replaced = False
    while i < n:
        if _FUENTES_HEADING_RE.match(lines[i]):
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
