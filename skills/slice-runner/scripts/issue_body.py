#!/usr/bin/env python3
"""Logica pura del cuerpo del issue de GitHub (fuente de verdad del estado).

El estado del run vive en el cuerpo de un issue de GitHub: no hay estado local. Este
modulo NO habla con `gh` en su nucleo (eso es I/O, lo valida el smoke real); solo
transforma texto:

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

El vocabulario cerrado (`Estado`, `MotivoBloqueada`, `TipoFuente`) son `StrEnum`: sus miembros se
serializan como su cadena, asi que el formato del issue no cambia, pero las comparaciones y los
`choices` de la CLI salen de un solo sitio. `Slice.estado` sigue siendo `str` a proposito: el
cuerpo lo escribe una persona y el parser tiene que poder leer un marcador que no sea canonico
sin reventar, para que quien decida sobre el lo vea. Validar es el trabajo de la frontera de
escritura, no del parser.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class Estado(StrEnum):
    """Estados canonicos de una slice."""

    PENDIENTE = "pendiente"
    EN_CURSO = "en-curso"
    ESPERANDO_MERGE = "esperando-merge"
    MERGEADA = "mergeada"
    BLOQUEADA = "bloqueada"
    ABORTADA = "abortada"


class MotivoBloqueada(StrEnum):
    """Motivos canonicos de `bloqueada`.

    `CI_INDETERMINADA` es que la CI no se pudo medir: no hay checks, o la respuesta de `gh` no
    era legible. No es `ci-roja` -mentiria en el registro duradero- ni `esperando-merge`
    -afirmaria un verde que no hubo-. Lo emite el paso 9 desde `controles.py ci-status`.
    """

    SIN_SUBAGENTES = "sin-subagentes"
    CONTROLES = "controles"
    VERIFY = "verify"
    CI_ROJA = "ci-roja"
    CI_INDETERMINADA = "ci-indeterminada"


_MOTIVOS_VIEJOS = {"puertas": MotivoBloqueada.CONTROLES}
"""`puertas` es como se llamaba `controles` antes del renombrado.

Hay issues abiertos con ese marcador escrito en el cuerpo, asi que se normaliza al parsear y
nadie aguas abajo tiene que conocer las dos formas. Mismo trato que `AC:` -> `ACEPTACION:`.
"""

_LINE_RE = re.compile(
    r"^\s*-\s*\[([ xX])\]\s*"
    r"(slice[-\w]+)\s*"
    r"(?:\(([^)]*)\))?\s*"
    r":\s*"
    r"(.*?)"
    r"\s*(?:\[([^\]]+)\])?"
    r"\s*(?:PR\s*#(\d+))?\s*$"
)
"""Una linea de slice: checkbox, id `slice-NN`, `(name)` o `(type: name)` opcional, titulo,
marcador `[estado]` opcional y `PR #N` opcional.

Cualquier `- [ ]` que no sea `slice-NN` se ignora, porque no es una slice: endurecido igual que
el parser del antiguo panel.
"""

_SENAL_LINE_RE = re.compile(r"^SE(?:N|Ñ)AL\s*:\s*(.*)$", re.IGNORECASE)
_REPO_LINE_RE = re.compile(r"^REPO\s*:\s*(.+?)\s*$", re.IGNORECASE)
_INTENCION_LINE_RE = re.compile(r"^INTENCI(?:O|Ó)N\s*:\s*(.*)$", re.IGNORECASE)
_ACEPTACION_LINE_RE = re.compile(r"^(?:ACEPTACI(?:O|Ó)N|AC)\s*:\s*(.*)$", re.IGNORECASE)
"""Lineas indentadas bajo una slice.

`SENAL` e `INTENCION` se aceptan con y sin tilde: las escribe una persona en un issue de GitHub
y un "SEÑAL:" no debe perderse en silencio. `AC` es la forma vieja de `ACEPTACION`, que se sigue
aceptando porque hay issues abiertos escritos con ella. El formato canonico que se documenta y se
emite es siempre el completo y sin tilde.
"""

_INTENCION_HEADING_RE = re.compile(r"^\s*##\s+intenci[oó]n\s*$", re.IGNORECASE)
"""La intencion de la feature entera (no la de una slice) vive en su propia seccion.

Va antes de las fuentes y las slices, y cuenta que esta mal hoy y como se nota, no como se va a
arreglar. `slice-spec` la escribe; `slice-runner` la lee para el cuerpo de la PR.
"""


class TipoFuente(StrEnum):
    """`doc` es convencion declarativa (CLAUDE.md, docs de reglas); `skill`, skill de proyecto."""

    DOC = "doc"
    SKILL = "skill"


_FUENTES_HEADING = "## Fuentes de convencion"
_FUENTES_HEADING_RE = re.compile(r"^\s*##\s+fuentes\s+de\s+convenci[oó]n\s*$", re.IGNORECASE)
_H2_RE = re.compile(r"^\s*##\s+")
_SUBHEADING_RE = re.compile(r"^\s*###\s+(.+?)\s*$")
_FUENTE_LINE_RE = re.compile(r"^\s*-\s*(doc|skill)\s*:\s*(.+?)\s*$", re.IGNORECASE)
"""Las fuentes de convencion: punteros a la vara de medir del repo, no su contenido.

Guardar el "donde" evita duplicar la fuente de verdad, que sigue viviendo en el repo.
`slice-spec` las escribe tras descubrirlas y confirmarlas; `slice-runner` solo las lee.

Son **por repo**: una slice con `REPO:` se mide con la vara de SU repo destino, no con la del
repo de la app. Las lineas antes de cualquier `### <org>/<repo>` son las del repo del issue;
cada subseccion `###` declara las de un repo destino.
"""

CONTROL_EXENTO = "ninguno"
"""Nombre reservado que declara que el repo no tiene controles reales.

El caso es el de los paneles de Grafana: su CI solo publica en master, no valida en PR. Vacio y
eximido no son lo mismo, igual que en `SENAL: exenta`.
"""

_CONTROLES_HEADING = "## Controles"
_CONTROLES_HEADING_RE = re.compile(r"^\s*##\s+controles\s*$", re.IGNORECASE)
_CONTROL_LINE_RE = re.compile(r"^\s*-\s*([\w-]+)\s*:\s*(.+?)\s*$")
"""Los controles deterministas del repo, con la misma forma por repo que las fuentes.

Antes los deducia `slice-runner` leyendo el `Makefile` al principio de cada slice: eso metia el
Makefile en el contexto del agente de vida mas larga del loop, lo repetia en cada slice y no lo
confirmaba nadie. Ahora `slice-spec` los descubre una vez, la persona los confirma y quedan
escritos aqui; `slice-runner` solo los lee.

Declararlos en el issue tiene un segundo efecto: la vara es texto publico. Si los eligiera el
implementador, el juzgado estaria definiendo la vara con la que se le juzga y bastaria
`compliance-bias` para que acabara midiendose con `make test-unit`.
"""


@dataclass(frozen=True, kw_only=True, slots=True)
class Slice:
    """Una slice tal como vive en el cuerpo del issue.

    `intencion` es que esta mal hoy y deja de estarlo con esta slice (alimenta el cuerpo de
    la PR); `aceptacion` son los criterios verificables pre-merge; `senal` es como se comprueba
    viva en produccion (la consume `deploy-watch`). `repo` es el repo destino: `None` = el repo
    del issue, y cualquier otro valor = slice cross-repo (p. ej. una alerta que vive en
    el repo de manifiestos, o un panel de Grafana).

    `estado` es `str` y no `Estado` porque el cuerpo lo escribe una persona: un marcador no
    canonico se lee tal cual en vez de reventar el parseo del issue entero.
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


@dataclass(frozen=True, kw_only=True, slots=True)
class Fuente:
    """Un puntero a una fuente de convencion de un repo.

    `ruta` es la ruta relativa al repo. `repo` es el repo al que aplica: `None` = el repo del
    issue (el de la app).
    """

    tipo: str
    ruta: str
    repo: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"tipo": self.tipo, "ruta": self.ruta}


@dataclass(frozen=True, kw_only=True, slots=True)
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

    def to_dict(self) -> dict[str, object]:
        return {
            "nombre": self.nombre,
            "comando": self.comando,
            "exento": self.exento,
            "motivo": self.motivo,
        }


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


@dataclass(frozen=True, kw_only=True, slots=True)
class _LineasHijas:
    """Las lineas indentadas bajo una slice, ya clasificadas."""

    intencion: list[str] = field(default_factory=list)
    aceptacion: list[str] = field(default_factory=list)
    senal: list[str] = field(default_factory=list)
    repo: str | None = None


def _lineas_hijas(lineas: Iterable[str]) -> _LineasHijas:
    """Clasifica las lineas indentadas de una slice por su prefijo."""
    intencion: list[str] = []
    aceptacion: list[str] = []
    senal: list[str] = []
    repo: str | None = None
    for linea in lineas:
        if m := _INTENCION_LINE_RE.match(linea):
            intencion.append(m.group(1).strip())
        elif m := _ACEPTACION_LINE_RE.match(linea):
            aceptacion.append(m.group(1).strip())
        elif m := _SENAL_LINE_RE.match(linea):
            senal.append(m.group(1).strip())
        elif m := _REPO_LINE_RE.match(linea):
            repo = m.group(1)
    return _LineasHijas(intencion=intencion, aceptacion=aceptacion, senal=senal, repo=repo)


def _estado_de_marcador(box: str, marcador: str) -> tuple[str, str]:
    """El (estado, motivo) de una slice a partir del checkbox y el marcador `[...]`.

    El checkbox manda: marcada es `mergeada` diga lo que diga el texto.
    """
    if box == "x":
        return (Estado.MERGEADA, "")
    if not marcador:
        return (Estado.PENDIENTE, "")
    if ":" in marcador:
        estado, raw_motivo = (p.strip() for p in marcador.split(":", 1))
        return (estado, normaliza_motivo(raw_motivo))
    return (marcador, "")


def _slice_from_match(m: re.Match[str], hijas: Iterable[str] = ()) -> Slice:
    type_, name = _split_type_name(m.group(3))
    estado, motivo = _estado_de_marcador(m.group(1).lower(), (m.group(5) or "").strip())
    clasificadas = _lineas_hijas(hijas)
    return Slice(
        slice_id=m.group(2),
        name=name,
        type=type_,
        title=(m.group(4) or "").strip(),
        estado=estado,
        motivo=motivo,
        pr=int(m.group(6)) if m.group(6) else None,
        intencion=clasificadas.intencion,
        aceptacion=clasificadas.aceptacion,
        senal=clasificadas.senal,
        repo=clasificadas.repo,
    )


def render_slice_line(sl: Slice) -> str:
    """Renderiza la linea de una slice en el formato canonico del cuerpo."""
    box = "x" if sl.estado == Estado.MERGEADA else " "
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
    """Extrae las slices (estado, INTENCION, ACEPTACION, SENAL y REPO), en orden de aparicion.

    Se recogen las lineas hijas de cada slice y la `Slice` se construye entera al final, en vez
    de crearla y luego irle anadiendo campos: es lo que permite que sea inmutable.
    """
    bloques: list[tuple[re.Match[str], list[str]]] = []
    for line in body.splitlines():
        if m := _LINE_RE.match(line):
            bloques.append((m, []))
        elif bloques:
            bloques[-1][1].append(line.strip())
    return [_slice_from_match(m, hijas) for m, hijas in bloques]


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
    if estado not in tuple(Estado):
        validos = ", ".join(Estado)
        raise ValueError(f"estado no valido: {estado!r} (validos: {validos})")

    out: list[str] = []
    changed = False
    for line in body.splitlines():
        m = _LINE_RE.match(line)
        if m and m.group(2) == slice_id:
            sl = _slice_from_match(m)
            actualizada = replace(sl, estado=estado, motivo=motivo, pr=pr if pr is not None else sl.pr)
            out.append(render_slice_line(actualizada))
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
    if not _tiene_seccion(body, _INTENCION_HEADING_RE):
        return None

    collected: list[str] = []
    in_section = False
    for line in body.splitlines():
        if _INTENCION_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section:
            if _H2_RE.match(line):
                break
            collected.append(line)
    return "\n".join(collected).strip()


def _tiene_seccion(body: str, heading_re: re.Pattern[str]) -> bool:
    """True si el cuerpo tiene esa seccion, aunque este vacia."""
    return any(heading_re.match(line) for line in body.splitlines())


def _iter_seccion(body: str, heading_re: re.Pattern[str]) -> list[tuple[str | None, str]]:
    """Las lineas de una seccion por repo, como `(repo, linea)`.

    Se detiene en el siguiente `## `. Una subseccion `### <org>/<repo>` atribuye las lineas
    que le siguen a ese repo destino; las de antes van con `repo=None` (el repo del issue).
    Lo comparten las secciones `## Fuentes de convencion` y `## Controles`, que tienen la
    misma forma por repo y existen por la misma razon.
    """
    out: list[tuple[str | None, str]] = []
    in_section = False
    repo: str | None = None
    for line in body.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if _H2_RE.match(line):
            break
        if sub := _SUBHEADING_RE.match(line):
            repo = sub.group(1)
            continue
        out.append((repo, line))
    return out


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
            while i < n and not _H2_RE.match(lines[i]):
                i += 1
            if i < n:
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
            fuentes.append(Fuente(tipo=m.group(1).lower(), ruta=m.group(2).strip(), repo=repo))
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
        if f.tipo not in tuple(TipoFuente):
            validos = ", ".join(TipoFuente)
            raise ValueError(f"tipo de fuente no valido: {f.tipo!r} (validos: {validos})")

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
            controles.append(Control(nombre=m.group(1).strip(), comando=m.group(2).strip(), repo=repo))
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


_GH_TIMEOUT = 60


def _gh_body(repo: str, issue: int) -> str:
    """Cuerpo actual del issue. Falla ruidosamente: un cuerpo vacio nunca es aceptable.

    Todo lo de arriba es puro y se testea sin `gh`. Esta capa de I/O existe porque sin ella el
    agente escribia el read-modify-write a mano en cada transicion: un `python3 -c` con
    `sys.path.insert`, `gh issue view --json body`, la llamada, y `gh issue edit --body-file`.
    En una sola sesion se escribio seis veces, y cada copia es una ocasion de equivocarse en
    silencio -el `--json body -q .body` mal puesto devuelve cadena vacia y el edit deja el issue
    en blanco-. Leer un issue, reescribir una linea y guardarlo es regla exacta, no juicio:
    `offload-deterministic`.
    """
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


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceInfo:
    """Una slice con la rama y el scope ya derivados, lista para el paso 1.

    Las claves que emite `to_dict` son el contrato que documenta `SKILL.md`.
    """

    slice_: Slice

    @property
    def rama(self) -> str:
        return rama_de(self.slice_)

    @property
    def scope(self) -> str:
        return scope_de(self.slice_)

    def to_dict(self) -> dict[str, object]:
        sl = self.slice_
        return {
            "slice_id": sl.slice_id,
            "name": sl.name,
            "type": sl.type,
            "titulo": sl.title,
            "estado": sl.estado,
            "motivo": sl.motivo,
            "pr": sl.pr,
            "repo": sl.repo,
            "intencion": sl.intencion,
            "aceptacion": sl.aceptacion,
            "senal": sl.senal,
            "rama": self.rama,
            "scope": self.scope,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class Show:
    """Todo lo que el paso 1 necesita del issue, ya filtrado por el repo de la slice.

    Era un `dict[str, object]` armado en `_cmd_show` y leido en `_emit_show` a base de indexar
    claves, lo que obligaba a tres `assert isinstance(...)` en produccion para convencer a mypy
    de lo que un campo declara por construccion. `slice` a `None` significa que no queda ninguna
    slice sin cerrar; el resto de claves se emiten igual, para que quien consuma el JSON no tenga
    que ramificar sobre que claves existen.

    `checklist` son **todas** las slices del issue, no solo la elegida: es el alcance declarado de la
    feature, que el paso 7 le pasa al verificador para que distinga "esto falta" de "esto lo cubre otra
    slice declarada" en vez de degradar la severidad por no poder constatarlo. Sale de aqui y no de un
    `gh issue view` improvisado por la misma razon que el resto del subcomando: leer el issue es regla
    exacta, no juicio. `slices` es su cuenta, derivada y no un campo, para que no puedan discrepar.
    """

    checklist: list[Slice]
    slice: SliceInfo | None = None
    intencion_feature: str | None = None
    tiene_seccion_fuentes: bool = False
    tiene_seccion_controles: bool = False
    fuentes: list[Fuente] = field(default_factory=list)
    controles: list[Control] = field(default_factory=list)

    @property
    def slices(self) -> int:
        return len(self.checklist)

    def to_dict(self) -> dict[str, object]:
        return {
            "slices": self.slices,
            "checklist": [
                {"slice_id": sl.slice_id, "titulo": sl.title, "estado": sl.estado, "motivo": sl.motivo}
                for sl in self.checklist
            ],
            "intencion_feature": self.intencion_feature,
            "tiene_seccion_fuentes": self.tiene_seccion_fuentes,
            "tiene_seccion_controles": self.tiene_seccion_controles,
            "fuentes": [f.to_dict() for f in self.fuentes],
            "controles": [c.to_dict() for c in self.controles],
            "slice": self.slice.to_dict() if self.slice else None,
        }


def _emit_show(show: Show, as_json: bool) -> int:
    """Humano por defecto, JSON con `--json`: el mismo contrato que `controles.py`.

    La incoherencia anterior -este subcomando emitia JSON siempre y tenia `--pretty`,
    mientras los cinco de `controles.py` son humanos salvo `--json`- hizo tropezar en la
    sonda del 2026-07-30 a quien habia escrito los dos scripts el dia antes. Dos scripts del
    mismo repo con convenciones opuestas para lo mismo son una trampa, no una preferencia.
    """
    if as_json:
        print(json.dumps(show.to_dict(), ensure_ascii=False))
        return 0

    if show.slice is None:
        print(f"[show] {show.slices} slice(s), ninguna sin cerrar")
        return 0

    sl = show.slice.slice_
    motivo = f": {sl.motivo}" if sl.motivo else ""
    print(f"[show] {show.slices} slice(s) en el issue")
    print(f"  slice   {sl.slice_id} ({sl.name}) [{sl.estado}{motivo}]")
    print(f"  rama    {show.slice.rama}")
    print(f"  scope   {show.slice.scope}")
    if sl.repo:
        print(f"  repo    {sl.repo}")
    if sl.pr:
        print(f"  pr      #{sl.pr}")
    for f in show.fuentes:
        print(f"  fuente  {f.tipo}: {f.ruta}")
    for c in show.controles:
        print(f"  control {c.nombre}: {'eximido' if c.exento else c.comando}")
    print(f"  aceptacion: {len(sl.aceptacion)} criterio(s)")
    print(f"  senal:      {'si' if sl.senal else 'NO DECLARADA'}")
    print(
        f"  intencion:  slice {'si' if sl.intencion else 'NO DECLARADA'}"
        f", feature {'si' if show.intencion_feature else 'NO DECLARADA'}"
    )
    return 0


def _elige_slice(slices: list[Slice], pedida: str | None) -> Slice | None:
    """La slice pedida, o la siguiente sin cerrar.

    Una en `esperando-merge` se retoma ahi, asi que tambien cuenta como "no terminada" y sale
    antes que una pendiente posterior.
    """
    if pedida:
        return next((s for s in slices if s.slice_id == pedida), None)
    return next((s for s in slices if s.estado != Estado.MERGEADA), None)


def _cmd_show(args: argparse.Namespace) -> int:
    body = _gh_body(args.repo, args.issue)
    slices = parse_body(body)
    if not slices:
        print("error: el cuerpo no tiene ninguna linea de slice valida", file=sys.stderr)
        return 2

    elegida = _elige_slice(slices, args.slice)
    if elegida is None:
        if args.slice:
            print(f"error: {args.slice} no esta en el issue", file=sys.stderr)
            return 2
        return _emit_show(Show(checklist=slices), args.json)

    return _emit_show(
        Show(
            checklist=slices,
            slice=SliceInfo(slice_=elegida),
            intencion_feature=parse_intencion(body),
            tiene_seccion_fuentes=tiene_seccion_fuentes(body),
            tiene_seccion_controles=tiene_seccion_controles(body),
            fuentes=fuentes_para(parse_fuentes(body), elegida.repo),
            controles=controles_para(parse_controles(body), elegida.repo),
        ),
        args.json,
    )


def _valida_motivo(estado: str, motivo: str | None) -> str | None:
    """El error de uso que corresponda, o `None` si el par (estado, motivo) es valido.

    `set_slice_estado` es puro y no valida el motivo: acepta cualquier cadena. Eso deja que un
    motivo inventado acabe escrito en el registro duradero, donde ya no se puede renombrar
    (paso lo mismo con `puertas`). La validacion vive aqui, en la frontera de escritura, que es
    el unico sitio donde hay un exit code que la haga cumplir.

    `abortada` se deja libre a proposito: su vocabulario aun no esta canonicalizado -la skill
    solo documenta `presupuesto`- y fijarlo aqui seria decidirlo de tapadillo. Para el resto de
    estados un motivo es ruido que nadie lee.
    """
    if estado == Estado.BLOQUEADA:
        if motivo not in tuple(MotivoBloqueada):
            validos = [str(m) for m in MotivoBloqueada]
            return f"bloqueada exige un motivo canonico, uno de {validos} (recibido: {motivo!r})"
        return None
    if motivo and estado != Estado.ABORTADA:
        return f"el estado {estado} no lleva motivo"
    return None


def _cmd_set_estado(args: argparse.Namespace) -> int:
    if error := _valida_motivo(args.estado, args.motivo):
        print(f"error: {error}", file=sys.stderr)
        return 2

    body = _gh_body(args.repo, args.issue)
    try:
        nuevo = set_slice_estado(body, args.slice, args.estado, pr=args.pr, motivo=args.motivo or "")
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if nuevo == body:
        if args.json:
            print(json.dumps({"control": "set-estado", "sin_cambios": True}, ensure_ascii=False))
        else:
            print(f"sin cambios: {args.slice} ya estaba asi")
        return 0
    _gh_set_body(args.repo, args.issue, nuevo)
    linea = next(
        (ln for ln in nuevo.splitlines() if args.slice in ln and ln.lstrip().startswith("- [")),
        "",
    )
    if args.json:
        print(
            json.dumps(
                {
                    "control": "set-estado",
                    "issue": f"{args.repo}#{args.issue}",
                    "slice": args.slice,
                    "estado": args.estado,
                    "motivo": args.motivo or "",
                    "linea": linea.strip(),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"{args.repo}#{args.issue} {args.slice} -> {args.estado}\n{linea.strip()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """El parser, aparte de `main`, para que un test pueda introspeccionar la superficie CLI."""
    parser = argparse.ArgumentParser(description="Lee y actualiza el estado del run en el issue")
    sub = parser.add_subparsers(dest="subcomando", required=True)

    sh = sub.add_parser("show", help="parsea el issue y emite lo que necesita el paso 1")
    sh.add_argument("--repo", required=True, help="org/repo del issue")
    sh.add_argument("--issue", required=True, type=int)
    sh.add_argument("--slice", default=None, help="slice concreta (default: la siguiente sin cerrar)")
    sh.add_argument("--json", action="store_true", help="salida estructurada JSON")

    st = sub.add_parser("set-estado", help="reescribe la linea de una slice en el issue")
    st.add_argument("--repo", required=True, help="org/repo del issue")
    st.add_argument("--issue", required=True, type=int)
    st.add_argument("--slice", required=True, help="p. ej. slice-01")
    st.add_argument("--estado", required=True, choices=[str(e) for e in Estado])
    st.add_argument(
        "--motivo",
        default=None,
        help=f"para bloqueada: uno de {[str(m) for m in MotivoBloqueada]}",
    )
    st.add_argument("--pr", type=int, default=None, help="numero de PR (se conserva si no se pasa)")
    st.add_argument("--json", action="store_true", help="salida estructurada JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.subcomando == "show":
            return _cmd_show(args)
        return _cmd_set_estado(args)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
