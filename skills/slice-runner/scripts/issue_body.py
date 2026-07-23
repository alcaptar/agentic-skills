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
    - [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11
    - [ ] slice-04 (backfill): Backfill [bloqueada: ci-roja] PR #13

El marcador `[estado]` va al final (antes del opcional `PR #N`). El checkbox `[x]` es la
verdad de "mergeada": una slice marcada esta mergeada aunque el texto diga otra cosa.
"""

from __future__ import annotations

import re
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


@dataclass
class Slice:
    """Una slice tal como vive en el cuerpo del issue."""

    slice_id: str
    name: str
    type: str
    title: str
    estado: str
    motivo: str = ""
    pr: int | None = None
    ac: list[str] = field(default_factory=list)


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
    """Extrae las slices (con estado y AC) del cuerpo del issue, en orden de aparicion."""
    slices: list[Slice] = []
    current: Slice | None = None
    for line in body.splitlines():
        m = _LINE_RE.match(line)
        if m:
            current = _slice_from_match(m)
            slices.append(current)
            continue
        if current is not None:
            stripped = line.strip()
            if stripped.startswith("AC:"):
                current.ac.append(stripped[len("AC:"):].strip())
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

    Read-modify-write puro: mantiene name/type/titulo/AC intactos. Si `pr` es None, conserva
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
