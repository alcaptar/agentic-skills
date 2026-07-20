#!/usr/bin/env python3
"""TUI de estado en vivo del pipeline slice-runner / deploy-watch.

Lee la spec (para listar TODAS las slices, no solo las cerradas), el ledger y el
stream de `<repo>/.slice-runner/` y pinta una tabla que se refresca sola. Muestra
ESTADO, no consumo de tokens en tiempo real (eso sale de la telemetria/OTel de
Claude Code, no de una skill).

Fuentes:
    <repo>/.slice-runner/state.json   estado vivo (spec_path, slice_actual, fase)
    <repo>/.slice-runner/runs.jsonl   ledger (una linea por slice/deploy al cerrar)
    <repo>/.slice-runner/stream.log   stream en vivo
    <spec_path>                       checklist Formato A: slices pendientes

Uso:
    python3 slice-panel.py [repo]            # live, refresco cada 2s (Ctrl+C sale)
    python3 slice-panel.py [repo] --once     # un solo render (test/captura)
    python3 slice-panel.py [repo] --interval 5
    python3 slice-panel.py [repo] --spec spec.md   # fuerza la spec (si no hay state.json)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
CLEAR = "\033[2J\033[H"

ESTADO_COLOR = {
    "hecha": GREEN,
    "bloqueada": RED,
    "abortada-presupuesto": YELLOW,
    "esperando-merge": MAGENTA,
    "en curso": CYAN,
    "pendiente": DIM,
}

DEPLOY_COLOR = {
    "sano": GREEN,
    "degradado": RED,
    "inconcluso": YELLOW,
}

# checkbox de la spec (Formato A) -> estado
BOX_ESTADO = {" ": "pendiente", "x": "hecha", "X": "hecha", "!": "bloqueada"}

_SLICE_LINE = re.compile(r"^\s*-\s*\[([ xX!])\]\s*(.*)$")
_SLICE_ID = re.compile(r"^(slice[-\w]+)\s*[:\-—]?\s*(.*)$", re.IGNORECASE)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()[-n:]


def _parse_spec(spec_path: Path) -> list[dict]:
    """Lee un checklist Formato A y devuelve las slices en orden de aparicion."""
    if not spec_path.exists():
        return []
    slices: list[dict] = []
    for raw in spec_path.read_text(encoding="utf-8").splitlines():
        m = _SLICE_LINE.match(raw)
        if not m:
            continue
        box, rest = m.group(1), m.group(2).strip()
        idm = _SLICE_ID.match(rest)
        if idm:
            sid, title = idm.group(1), idm.group(2).strip()
        else:
            sid, title = rest.split(":", 1)[0][:12], rest
        slices.append({"slice_id": sid, "title": title, "box_estado": BOX_ESTADO.get(box, "pendiente")})
    return slices


def _coste(entry: dict) -> str:
    usd = entry.get("coste_usd")
    if isinstance(usd, (int, float)) and usd > 0:
        return f"${usd:.2f}"
    tok = entry.get("verifier_tokens") or entry.get("tokens_out") or entry.get("tokens_in")
    if isinstance(tok, (int, float)) and tok > 0:
        return f"{tok / 1000:.1f}k tok"
    return "-"


def _trunc(text: str, width: int) -> str:
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def _estado_de(
    sid: str,
    slice_led: dict[str, dict],
    spec_by_id: dict[str, dict],
    slice_actual: str | None,
    fase_actual: str,
    esperando: bool,
) -> str:
    """Estado de una slice. La fase VIVA (state.json) manda sobre el ledger:
    una slice con CI verde figura `hecha` en el ledger, pero si sigue siendo la
    slice en curso y esta esperando el merge, la fila lo refleja como
    `esperando-merge` (no como cerrada)."""
    if slice_actual == sid and fase_actual:
        return "esperando-merge" if esperando else "en curso"
    led_e = slice_led.get(sid)
    if led_e:
        return str(led_e.get("estado", "?"))
    return spec_by_id.get(sid, {}).get("box_estado", "pendiente")


def _resolve_spec_path(repo: Path, state: dict, cli_spec: str | None) -> Path | None:
    if cli_spec:
        p = Path(cli_spec)
        return p if p.is_absolute() else (repo / p)
    sp = state.get("spec_path")
    if sp:
        p = Path(sp)
        return p if p.is_absolute() else (repo / p)
    return None


def _render(repo: Path, cli_spec: str | None) -> str:
    sr = repo / ".slice-runner"
    state = _read_json(sr / "state.json")
    led = _read_jsonl(sr / "runs.jsonl")
    stream = _tail(sr / "stream.log", 8)

    slice_led = {e.get("slice_id"): e for e in led if e.get("fase") != "deploy" and e.get("slice_id")}
    deploy_led: dict[str, dict] = {}
    deploys_sin_slice: list[dict] = []
    for e in led:
        if e.get("fase") != "deploy":
            continue
        sid = e.get("slice_id")
        if sid:
            deploy_led[sid] = e
        else:
            deploys_sin_slice.append(e)

    spec_path = _resolve_spec_path(repo, state, cli_spec)
    spec_slices = _parse_spec(spec_path) if spec_path else []

    # Ordena por la spec; anexa cualquier slice del ledger que no este en la spec.
    ordered_ids: list[str] = [s["slice_id"] for s in spec_slices]
    spec_by_id = {s["slice_id"]: s for s in spec_slices}
    for sid in slice_led:
        if sid not in spec_by_id:
            ordered_ids.append(sid)

    slice_actual = state.get("slice_actual")
    fase_actual = str(state.get("fase", ""))
    esperando = fase_actual.startswith("waiting")

    out: list[str] = []
    out.append(f"{BOLD}{CYAN}  slice-runner panel{RESET}  {DIM}{repo}{RESET}")
    if spec_path:
        marca = f"{DIM}{spec_path.name}{RESET}" if spec_slices else f"{YELLOW}{spec_path.name} (no leida){RESET}"
        out.append(f"  {DIM}spec:{RESET} {marca}")
    out.append("")

    # Banner de espera: distingue "esperandote a ti" de "parado".
    if esperando:
        det = fase_actual.split(":", 1)[1].strip() if ":" in fase_actual else fase_actual
        out.append(
            f"  {MAGENTA}{BOLD}>> ESPERANDO DECISION TUYA: {det}{RESET}"
            f"  {DIM}(slice {slice_actual}){RESET}"
        )
        out.append("")

    header = f"  {'SLICE':<12} {'ESTADO':<16} {'INT':<4} {'VERIFY':<7} {'COSTE':<10} {'CI':<14} {'DEPLOY':<11} PR"
    out.append(f"{BOLD}{header}{RESET}")
    out.append(f"  {DIM}{'-' * 92}{RESET}")

    if not ordered_ids:
        out.append(f"  {DIM}(sin slices: no hay spec legible ni entradas en el ledger){RESET}")

    for sid in ordered_ids:
        led_e = slice_led.get(sid)
        estado = _estado_de(sid, slice_led, spec_by_id, slice_actual, fase_actual, esperando)
        color = ESTADO_COLOR.get(estado, "")
        dep = deploy_led.get(sid, {})
        ver = str(dep.get("veredicto", "-"))
        dep_color = DEPLOY_COLOR.get(ver, DIM)
        e = led_e or {}
        row = (
            f"  {str(sid):<12} "
            f"{color}{estado:<16}{RESET} "
            f"{str(e.get('intentos', '-')):<4} "
            f"{str(e.get('verify', '-')):<7} "
            f"{_coste(e):<10} "
            f"{_trunc(e.get('ci_result', '-'), 14):<14} "
            f"{dep_color}{ver:<11}{RESET} "
            f"{DIM}{str(e.get('pr_url', '-'))}{RESET}"
        )
        out.append(row)

    # deploys sin slice asociada (compat con entradas viejas)
    if deploys_sin_slice:
        out.append("")
        out.append(f"{BOLD}  deploy-watch (sin slice){RESET}")
        for d in deploys_sin_slice:
            ver = str(d.get("veredicto", "?"))
            color = DEPLOY_COLOR.get(ver, YELLOW)
            out.append(f"  {str(d.get('pr_url', '-')):<24} {color}{ver}{RESET}")

    # resumen
    all_states = {
        sid: _estado_de(sid, slice_led, spec_by_id, slice_actual, fase_actual, esperando)
        for sid in ordered_ids
    }
    hechas = [s for s, st in all_states.items() if st == "hecha"]
    bloqueadas = [s for s, st in all_states.items() if st == "bloqueada"]
    pendientes = [s for s, st in all_states.items() if st == "pendiente"]
    esperando_merge = [s for s, st in all_states.items() if st == "esperando-merge"]
    validadas = [s for s in ordered_ids if deploy_led.get(s, {}).get("veredicto") == "sano"]
    total_usd = sum(float((slice_led.get(s) or {}).get("coste_usd") or 0) for s in ordered_ids)
    usd_hechas = sum(float((slice_led.get(s) or {}).get("coste_usd") or 0) for s in hechas)

    out.append("")
    resumen = (
        f"  {BOLD}resumen{RESET}  "
        f"{GREEN}{len(hechas)} hechas{RESET}  "
        f"{GREEN}{len(validadas)} validadas en deploy{RESET}  "
        f"{MAGENTA}{len(esperando_merge)} esperando merge{RESET}  "
        f"{RED}{len(bloqueadas)} bloqueadas{RESET}  "
        f"{DIM}{len(pendientes)} pendientes{RESET}  "
        f"{len(ordered_ids)} total"
    )
    if total_usd > 0:
        por_slice = usd_hechas / len(hechas) if hechas else 0.0
        resumen += f"  ·  ${total_usd:.2f} total  ·  ${por_slice:.2f}/slice mergeada"
    out.append(resumen)

    # stream en vivo
    out.append("")
    out.append(f"{BOLD}  stream{RESET}  {DIM}(.slice-runner/stream.log){RESET}")
    if not stream:
        out.append(f"  {DIM}(stream vacio){RESET}")
    for ln in stream:
        color = MAGENTA if "waiting" in ln else DIM
        out.append(f"  {color}{ln}{RESET}")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="TUI de estado del pipeline slice-runner")
    ap.add_argument("repo", nargs="?", default=".", help="raiz del repo objetivo")
    ap.add_argument("--once", action="store_true", help="un solo render y salir")
    ap.add_argument("--interval", type=float, default=2.0, help="segundos entre refrescos")
    ap.add_argument("--spec", default=None, help="ruta a la spec (si no hay state.json)")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()

    if args.once:
        print(_render(repo, args.spec))
        return 0

    try:
        while True:
            sys.stdout.write(CLEAR)
            sys.stdout.write(_render(repo, args.spec))
            sys.stdout.write(f"\n\n  {DIM}refresco cada {args.interval}s · Ctrl+C para salir{RESET}\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
