#!/usr/bin/env python3
"""TUI de estado en vivo del pipeline slice-runner / deploy-watch.

Lee el ledger y el stream de `<repo>/.slice-runner/` y pinta una tabla que se
refresca sola. Muestra ESTADO, no consumo de tokens en tiempo real (eso sale de
la telemetria/OTel de Claude Code, no de una skill).

Uso:
    python3 slice-panel.py [repo]            # live, refresco cada 2s (Ctrl+C sale)
    python3 slice-panel.py [repo] --once     # un solo render (test/captura)
    python3 slice-panel.py [repo] --interval 5

`repo` por defecto es el directorio actual; se leen `<repo>/.slice-runner/runs.jsonl`
y `<repo>/.slice-runner/stream.log`.
"""

from __future__ import annotations

import argparse
import json
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
CLEAR = "\033[2J\033[H"

ESTADO_COLOR = {
    "hecha": GREEN,
    "bloqueada": RED,
    "abortada-presupuesto": YELLOW,
    "pendiente": DIM,
}


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


def _tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()[-n:]


def _coste(entry: dict) -> str:
    usd = entry.get("coste_usd")
    if isinstance(usd, (int, float)) and usd > 0:
        return f"${usd:.2f}"
    tok = entry.get("verifier_tokens") or entry.get("tokens_out") or entry.get("tokens_in")
    if isinstance(tok, (int, float)) and tok > 0:
        return f"{tok / 1000:.1f}k tok"
    return "-"


def _render(repo: Path) -> str:
    led = _read_jsonl(repo / ".slice-runner" / "runs.jsonl")
    stream = _tail(repo / ".slice-runner" / "stream.log", 8)

    slices = [e for e in led if e.get("fase") != "deploy"]
    deploys = [e for e in led if e.get("fase") == "deploy"]

    out: list[str] = []
    out.append(f"{BOLD}{CYAN}  slice-runner panel{RESET}  {DIM}{repo}{RESET}")
    out.append("")
    header = f"  {'SLICE':<12} {'ESTADO':<20} {'INT':<4} {'VERIFY':<7} {'COSTE':<10} {'CI':<14} PR"
    out.append(f"{BOLD}{header}{RESET}")
    out.append(f"  {DIM}{'-' * 78}{RESET}")

    if not slices:
        out.append(f"  {DIM}(sin entradas en el ledger todavia){RESET}")
    for e in slices:
        estado = str(e.get("estado", "?"))
        color = ESTADO_COLOR.get(estado, "")
        row = (
            f"  {str(e.get('slice_id', '?')):<12} "
            f"{color}{estado:<20}{RESET} "
            f"{str(e.get('intentos', '-')):<4} "
            f"{str(e.get('verify', '-')):<7} "
            f"{_coste(e):<10} "
            f"{str(e.get('ci_result', '-')):<14} "
            f"{DIM}{str(e.get('pr_url', '-'))}{RESET}"
        )
        out.append(row)

    if deploys:
        out.append("")
        out.append(f"{BOLD}  deploy-watch{RESET}")
        for d in deploys:
            ver = str(d.get("veredicto", "?"))
            color = GREEN if ver == "sano" else (RED if ver == "degradado" else YELLOW)
            out.append(f"  {str(d.get('pr_url', '-')):<24} {color}{ver}{RESET}")

    # resumen
    hechas = [e for e in slices if e.get("estado") == "hecha"]
    bloqueadas = [e for e in slices if e.get("estado") == "bloqueada"]
    total_usd = sum(float(e.get("coste_usd") or 0) for e in slices)
    out.append("")
    resumen = (
        f"  {BOLD}resumen{RESET}  "
        f"{GREEN}{len(hechas)} hechas{RESET}  "
        f"{RED}{len(bloqueadas)} bloqueadas{RESET}  "
        f"{len(slices)} total"
    )
    if total_usd > 0:
        por_slice = total_usd / len(hechas) if hechas else 0.0
        resumen += f"  ·  ${total_usd:.2f} total  ·  ${por_slice:.2f}/slice mergeada"
    out.append(resumen)

    # stream en vivo
    out.append("")
    out.append(f"{BOLD}  stream{RESET}  {DIM}(.slice-runner/stream.log){RESET}")
    if not stream:
        out.append(f"  {DIM}(stream vacio){RESET}")
    for ln in stream:
        out.append(f"  {DIM}{ln}{RESET}")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="TUI de estado del pipeline slice-runner")
    ap.add_argument("repo", nargs="?", default=".", help="raiz del repo objetivo")
    ap.add_argument("--once", action="store_true", help="un solo render y salir")
    ap.add_argument("--interval", type=float, default=2.0, help="segundos entre refrescos")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()

    if args.once:
        print(_render(repo))
        return 0

    try:
        while True:
            sys.stdout.write(CLEAR)
            sys.stdout.write(_render(repo))
            sys.stdout.write(f"\n\n  {DIM}refresco cada {args.interval}s · Ctrl+C para salir{RESET}\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
