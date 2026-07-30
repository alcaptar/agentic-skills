#!/usr/bin/env python3
"""Metricas durables de slice-runner (patron offload-deterministic).

El estado del run vive en el issue de GitHub, no en el repo. Para decidir con datos
"cuando subir de nivel" hace falta ademas un rastro de telemetria que NUNCA entre en el
repo/PR y sobreviva a los runs. Este log vive fuera del repo:

    ~/.claude/slice-runner/metrics.jsonl   append-only, una linea por slice cerrada

Un script anexa el registro (no la IA redactando prosa) y otro lo agrega. Las cifras
del reporte son deterministas: tasa de FALLA del verificador, tasa de bloqueo por
controles, % de slices al primer intento, media de reintentos, tasa de CI roja. Coste en
tokens NO se mide aqui (sale de la telemetria/OTel de Claude Code): se admite como campo
opcional best-effort y, si no viene, no se inventa.

El log es durable y append-only, asi que los registros viejos no tienen los campos
nuevos: el agregado los trata como cero, nunca como dato ausente que invalide la fila. Por
lo mismo, los que se escribieron cuando los controles se llamaban "puertas" siguen contando:
el agregado lee las dos formas y las suma como una sola categoria (ver `_veredicto` y
`_reintentos_controles`). Renombrar no puede borrar historico.

Uso:
    metrics.py record --repo <repo> --slice slice-01 --name cantidad-vo \\
        --veredicto PASA --ci green \\
        --hallazgos-alta 0 --hallazgos-media 1 --hallazgos-baja 2 \\
        --reintentos-implement 0 --reintentos-controles 0 --reintentos-ci 0 \\
        --reintentos-verify 0 --descartes-verify 0 \\
        --duracion-s 540 \\
        [--coste-tokens 12345] [--ts 2026-07-22T10:00:00Z] [--path RUTA]

    metrics.py report [--repo <repo>] [--json] [--path RUTA]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PATH = Path.home() / ".claude" / "slice-runner" / "metrics.jsonl"

# `FALLA` es el veto del juez adversarial. `bloqueada-controles` es agotar los reintentos
# de lint/tipos/tests: un fallo mecanico, que se registra aparte porque confundirlo con un
# veto del juez dejaria inservible el unico instrumento para calibrarlo.
VEREDICTOS = ("PASA", "FALLA", "bloqueada-controles", "abortada-presupuesto")
CI_RESULTS = ("green", "red", "none")

# Formas viejas que hay escritas en el log durable, de cuando los controles se llamaban
# "puertas". Solo se leen: lo que se emite es siempre la forma canonica.
_VEREDICTO_VIEJO = "bloqueada-puertas"
_REINTENTOS_CONTROLES_VIEJO = "reintentos_puertas"


def _path(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else DEFAULT_PATH


def _veredicto(row: dict[str, object]) -> object:
    """El veredicto de una fila, con la forma vieja normalizada a la canonica."""
    v = row.get("veredicto")
    return "bloqueada-controles" if v == _VEREDICTO_VIEJO else v


def _reintentos_controles(row: dict[str, object]) -> object:
    """Los reintentos de controles de una fila, mirando tambien el campo con el nombre viejo."""
    valor = row.get("reintentos_controles")
    return row.get(_REINTENTOS_CONTROLES_VIEJO) if valor is None else valor


def record(args: argparse.Namespace) -> int:
    ts = args.ts or datetime.now(UTC).isoformat()
    entry: dict[str, object] = {
        "ts": ts,
        "repo": args.repo,
        "slice_id": args.slice,
        "name": args.name,
        "veredicto": args.veredicto,
        "ci": args.ci,
        "hallazgos": {
            "alta": args.hallazgos_alta,
            "media": args.hallazgos_media,
            "baja": args.hallazgos_baja,
        },
        "reintentos_implement": args.reintentos_implement,
        "reintentos_controles": args.reintentos_controles,
        "reintentos_ci": args.reintentos_ci,
        # Las dos formas de volver a invocar al verificador, separadas a proposito, por el
        # mismo motivo por el que `FALLA` y `bloqueada-controles` son veredictos distintos:
        # una es un rechazo semantico del juez y la otra un fallo mecanico del agente.
        "reintentos_verify": args.reintentos_verify,
        "descartes_verify": args.descartes_verify,
        "duracion_s": args.duracion_s,
        "coste_tokens": args.coste_tokens,  # None si no se pasa: no se inventa
    }
    path = _path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"registrado: {entry['slice_id']} ({entry['name']}) -> {path}")
    return 0


def _load(path: Path, repo: str | None) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Log durable append-only: una linea corrupta (p. ej. escritura a
                # medias) no debe reventar el report. Se salta, como hace el panel.
                continue
            if repo is None or row.get("repo") == repo:
                rows.append(row)
    return rows


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _as_float(v: object) -> float:
    """Coacciona a float un valor leido de JSON (tipado como object)."""
    return float(v) if isinstance(v, (int, float)) else 0.0


def _aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    total = len(rows)
    verificador_falla = sum(1 for r in rows if _veredicto(r) == "FALLA")
    bloqueada_controles = sum(1 for r in rows if _veredicto(r) == "bloqueada-controles")
    ci_red = sum(1 for r in rows if r.get("ci") == "red")
    # "Primer intento" = resuelta limpia a la primera: PASA del verificador, CI verde
    # y cero reintentos de cualquier clase (tambien de controles: una vuelta por lint
    # sucio no es limpia). Un abort-por-presupuesto con 0 reintentos NO es exito.
    primer_intento = sum(
        1
        for r in rows
        if _veredicto(r) == "PASA"
        and r.get("ci") == "green"
        and r.get("reintentos_implement") == 0
        and not _reintentos_controles(r)
        and r.get("reintentos_ci") == 0
    )
    reint_impl = [_as_float(r.get("reintentos_implement")) for r in rows]
    reint_controles = [_as_float(_reintentos_controles(r)) for r in rows]
    reint_ci = [_as_float(r.get("reintentos_ci")) for r in rows]
    reint_verify = [_as_float(r.get("reintentos_verify")) for r in rows]
    # `descartes_verify` se reporta como tasa, no como media: la pregunta que responde no es
    # "cuantos de media" sino "en que fraccion de slices el contrato de salida del juez no
    # aguanto". Es una propiedad del agente, no de la slice.
    descartes = sum(1 for r in rows if _as_float(r.get("descartes_verify")) > 0)
    duraciones = [_as_float(r["duracion_s"]) for r in rows if r.get("duracion_s") is not None]
    costes = [_as_float(r["coste_tokens"]) for r in rows if r.get("coste_tokens") is not None]
    return {
        "slices": total,
        "verificador_falla_pct": _pct(verificador_falla, total),
        "bloqueada_controles_pct": _pct(bloqueada_controles, total),
        "ci_roja_pct": _pct(ci_red, total),
        "primer_intento_pct": _pct(primer_intento, total),
        "reintentos_implement_media": _mean(reint_impl),
        "reintentos_controles_media": _mean(reint_controles),
        "reintentos_ci_media": _mean(reint_ci),
        "reintentos_verify_media": _mean(reint_verify),
        "descartes_verify_pct": _pct(descartes, total),
        "duracion_s_media": _mean(duraciones),
        "coste_tokens_media": _mean(costes) if costes else None,
        "coste_muestras": len(costes),
    }


def report(args: argparse.Namespace) -> int:
    path = _path(args.path)
    rows = _load(path, args.repo)
    agg = _aggregate(rows)

    if args.json:
        print(json.dumps(agg, ensure_ascii=False))
        return 0

    scope = args.repo or "todos los repos"
    if not rows:
        print(f"sin metricas para {scope} en {path}")
        return 0
    print(f"metricas slice-runner ({scope}) - {agg['slices']} slices - {path}")
    print(f"  verificador FALLA        {agg['verificador_falla_pct']}%")
    print(f"  bloqueada por controles  {agg['bloqueada_controles_pct']}%")
    print(f"  CI roja                  {agg['ci_roja_pct']}%")
    print(f"  slices al 1er intento    {agg['primer_intento_pct']}%")
    print(f"  reintentos implement     {agg['reintentos_implement_media']} media")
    print(f"  reintentos controles     {agg['reintentos_controles_media']} media")
    print(f"  reintentos CI            {agg['reintentos_ci_media']} media")
    print(f"  reintentos verify        {agg['reintentos_verify_media']} media")
    print(f"  contrato del juez roto   {agg['descartes_verify_pct']}% de slices")
    print(f"  duracion                 {agg['duracion_s_media']}s media")
    if agg["coste_tokens_media"] is not None:
        print(
            f"  coste tokens             {agg['coste_tokens_media']} media"
            f" ({agg['coste_muestras']} muestras)"
        )
    else:
        print("  coste tokens             sin datos (ver OTel de Claude Code)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Metricas durables de slice-runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="anexa un registro por slice cerrada")
    rec.add_argument("--repo", required=True)
    rec.add_argument("--slice", required=True, help="slice_id, p. ej. slice-01")
    rec.add_argument("--name", required=True)
    rec.add_argument("--veredicto", required=True, choices=VEREDICTOS)
    rec.add_argument("--ci", default="none", choices=CI_RESULTS)
    rec.add_argument("--hallazgos-alta", type=int, default=0)
    rec.add_argument("--hallazgos-media", type=int, default=0)
    rec.add_argument("--hallazgos-baja", type=int, default=0)
    rec.add_argument("--reintentos-implement", type=int, default=0)
    rec.add_argument("--reintentos-controles", type=int, default=0)
    rec.add_argument("--reintentos-ci", type=int, default=0)
    rec.add_argument(
        "--reintentos-verify",
        type=int,
        default=0,
        help="rondas de verificacion por FALLA del juez (rechazo semantico)",
    )
    rec.add_argument(
        "--descartes-verify",
        type=int,
        default=0,
        help="invocaciones del juez descartadas por devolver algo que no era su JSON",
    )
    rec.add_argument("--duracion-s", type=int, default=None)
    rec.add_argument("--coste-tokens", type=int, default=None)
    rec.add_argument("--ts", default=None, help="ISO ts; default now(UTC)")
    rec.add_argument(
        "--path",
        default=None,
        help="override del log (default ~/.claude/slice-runner/metrics.jsonl)",
    )
    rec.set_defaults(func=record)

    rep = sub.add_parser("report", help="agrega el log y calcula las cifras de nivel")
    rep.add_argument("--repo", default=None, help="filtra por repo (default: todos)")
    rep.add_argument("--json", action="store_true")
    rep.add_argument("--path", default=None)
    rep.set_defaults(func=report)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
