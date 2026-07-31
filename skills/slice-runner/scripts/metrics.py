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
el agregado lee las dos formas y las suma como una sola categoria. Renombrar no puede borrar
historico, y toda esa tolerancia vive en un solo sitio (`Fila.from_row`) para que el resto
del modulo pueda hacer aritmetica sobre campos tipados sin volver a preguntarse que forma
tenia el log el mes pasado.

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
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

DEFAULT_PATH = Path.home() / ".claude" / "slice-runner" / "metrics.jsonl"


class Veredicto(StrEnum):
    """Como acabo una slice, en el vocabulario del log durable.

    `FALLA` es el veto del juez adversarial. `BLOQUEADA_CONTROLES` es agotar los reintentos de
    lint/tipos/tests: un fallo mecanico, que se registra aparte porque confundirlo con un veto
    del juez dejaria inservible el unico instrumento para calibrarlo.
    """

    PASA = "PASA"
    FALLA = "FALLA"
    BLOQUEADA_CONTROLES = "bloqueada-controles"
    ABORTADA_PRESUPUESTO = "abortada-presupuesto"


class Ci(StrEnum):
    """Como acabo la CI de la PR de la slice."""

    VERDE = "green"
    ROJA = "red"
    NINGUNA = "none"


_VEREDICTO_VIEJO = "bloqueada-puertas"
_REINTENTOS_CONTROLES_VIEJO = "reintentos_puertas"
"""Formas viejas escritas en el log durable, de cuando los controles se llamaban "puertas".

Solo se leen (las consume `Fila.from_row`): lo que se emite es siempre la forma canonica.
"""


def _path(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else DEFAULT_PATH


@dataclass(frozen=True, kw_only=True, slots=True)
class Hallazgos:
    """Los hallazgos del verificador de una slice, por severidad."""

    alta: int = 0
    media: int = 0
    baja: int = 0

    def to_dict(self) -> dict[str, object]:
        return {"alta": self.alta, "media": self.media, "baja": self.baja}


@dataclass(frozen=True, kw_only=True, slots=True)
class Registro:
    """Una linea del log: lo que se sabe de una slice ya cerrada.

    Era un `dict` literal armado dentro de `record` a partir de un `argparse.Namespace`, o sea
    dos bolsas sin tipar seguidas. Las claves que escribe `to_dict` son el formato del log
    durable y no cambian: hay historico escrito con ellas.

    `reintentos_verify` y `descartes_verify` son las dos formas de volver a invocar al
    verificador, separadas a proposito por el mismo motivo por el que `FALLA` y
    `bloqueada-controles` son veredictos distintos: una es un rechazo semantico del juez y la
    otra un fallo mecanico del agente. `coste_tokens` se queda en `None` si no se pasa: no se
    inventa.

    `reintentos_verify` se amplio el 2026-07-31: eran las rondas por `FALLA` y ahora son **todas**
    las vueltas al paso 5 que decide el juez, incluida la correccion de un hallazgo no bloqueante
    que la regla del paso 7 manda arreglar. Las filas anteriores a esa fecha **no se marcan y el
    historico se sigue agregando entero**, decidido asi y no por descuido: lo que este campo mide es
    la frontera que lo separa de `descartes_verify` -el juez rechazo el codigo, frente a un agente que
    no aguanto su contrato de salida- y esa frontera no se movio, con lo que las dos epocas cuentan la
    misma cosa. Marcar la fecha partiria la serie en dos para conservar una distincion que ningun
    agregado del reporte usa.
    """

    ts: str
    repo: str
    slice_id: str
    name: str
    veredicto: Veredicto
    ci: Ci
    hallazgos: Hallazgos
    reintentos_implement: int = 0
    reintentos_controles: int = 0
    reintentos_ci: int = 0
    reintentos_verify: int = 0
    descartes_verify: int = 0
    duracion_s: int | None = None
    coste_tokens: int | None = None

    @staticmethod
    def from_args(args: argparse.Namespace) -> Registro:
        return Registro(
            ts=args.ts or datetime.now(UTC).isoformat(),
            repo=args.repo,
            slice_id=args.slice,
            name=args.name,
            veredicto=Veredicto(args.veredicto),
            ci=Ci(args.ci),
            hallazgos=Hallazgos(
                alta=args.hallazgos_alta,
                media=args.hallazgos_media,
                baja=args.hallazgos_baja,
            ),
            reintentos_implement=args.reintentos_implement,
            reintentos_controles=args.reintentos_controles,
            reintentos_ci=args.reintentos_ci,
            reintentos_verify=args.reintentos_verify,
            descartes_verify=args.descartes_verify,
            duracion_s=args.duracion_s,
            coste_tokens=args.coste_tokens,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts,
            "repo": self.repo,
            "slice_id": self.slice_id,
            "name": self.name,
            "veredicto": str(self.veredicto),
            "ci": str(self.ci),
            "hallazgos": self.hallazgos.to_dict(),
            "reintentos_implement": self.reintentos_implement,
            "reintentos_controles": self.reintentos_controles,
            "reintentos_ci": self.reintentos_ci,
            "reintentos_verify": self.reintentos_verify,
            "descartes_verify": self.descartes_verify,
            "duracion_s": self.duracion_s,
            "coste_tokens": self.coste_tokens,
        }


def _texto(row: dict[str, object], clave: str) -> str:
    valor = row.get(clave)
    return valor if isinstance(valor, str) else ""


def _numero(row: dict[str, object], *claves: str) -> float:
    """El primer valor numerico presente entre `claves`, o 0.0.

    Varias claves porque el log durable tiene el campo viejo y el nuevo escritos en filas
    distintas, y una fila anterior al campo no tiene ninguno: cero, nunca dato ausente que
    invalide la fila.
    """
    for clave in claves:
        valor = row.get(clave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
    return 0.0


def _opcional(row: dict[str, object], clave: str) -> float | None:
    valor = row.get(clave)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    return None


@dataclass(frozen=True, kw_only=True, slots=True)
class Fila:
    """Una fila del log ya normalizada: es donde vive TODA la compatibilidad historica.

    Antes cada cifra del agregado se leia del `dict` crudo con su propio `.get()`, y las dos
    lecturas tolerantes (`bloqueada-puertas`, `reintentos_puertas`) eran funciones que devolvian
    `object`. Con esto, `_aggregate` es aritmetica sobre campos tipados y quien anada un campo
    nuevo tiene un solo sitio donde decidir como se leen las filas que no lo traen.
    """

    repo: str
    slice_id: str
    veredicto: str
    ci: str
    reintentos_implement: float
    reintentos_controles: float
    reintentos_ci: float
    reintentos_verify: float
    descartes_verify: float
    duracion_s: float | None
    coste_tokens: float | None

    @staticmethod
    def from_row(row: dict[str, object]) -> Fila:
        veredicto = _texto(row, "veredicto")
        return Fila(
            repo=_texto(row, "repo"),
            slice_id=_texto(row, "slice_id"),
            veredicto=Veredicto.BLOQUEADA_CONTROLES if veredicto == _VEREDICTO_VIEJO else veredicto,
            ci=_texto(row, "ci"),
            reintentos_implement=_numero(row, "reintentos_implement"),
            reintentos_controles=_numero(row, "reintentos_controles", _REINTENTOS_CONTROLES_VIEJO),
            reintentos_ci=_numero(row, "reintentos_ci"),
            reintentos_verify=_numero(row, "reintentos_verify"),
            descartes_verify=_numero(row, "descartes_verify"),
            duracion_s=_opcional(row, "duracion_s"),
            coste_tokens=_opcional(row, "coste_tokens"),
        )

    @property
    def primer_intento(self) -> bool:
        """Resuelta limpia a la primera: PASA del juez, CI verde y cero reintentos de cualquier clase.

        Tambien los de controles: una vuelta por lint sucio no es limpia. Un abort-por-presupuesto
        con 0 reintentos NO es exito, y por eso el veredicto tiene que ser `PASA` explicito.
        """
        return (
            self.veredicto == Veredicto.PASA
            and self.ci == Ci.VERDE
            and not self.reintentos_implement
            and not self.reintentos_controles
            and not self.reintentos_ci
        )


def escribe(registro: Registro, path: Path) -> None:
    """Anexa el registro al log durable, creando el directorio si hace falta."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro.to_dict(), ensure_ascii=False) + "\n")


def record(args: argparse.Namespace) -> int:
    registro = Registro.from_args(args)
    path = _path(args.path)
    escribe(registro, path)
    print(f"registrado: {registro.slice_id} ({registro.name}) -> {path}")
    return 0


def _load(path: Path, repo: str | None) -> list[Fila]:
    """Las filas del log, opcionalmente filtradas por repo.

    Una linea corrupta se salta en vez de reventar: el log es append-only y durable, asi que
    una escritura a medias no puede dejar sin report todo el historico que si es legible.
    """
    if not path.exists():
        return []
    filas: list[Fila] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            linea = raw.strip()
            if not linea:
                continue
            try:
                row = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            fila = Fila.from_row({str(k): v for k, v in row.items()})
            if repo is None or fila.repo == repo:
                filas.append(fila)
    return filas


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


@dataclass(frozen=True, kw_only=True, slots=True)
class Metricas:
    """Las cifras del reporte. Las claves de `to_dict` son las que consume `SKILL.md`."""

    slices: int
    verificador_falla_pct: float
    bloqueada_controles_pct: float
    ci_roja_pct: float
    primer_intento_pct: float
    reintentos_implement_media: float
    reintentos_controles_media: float
    reintentos_ci_media: float
    reintentos_verify_media: float
    descartes_verify_pct: float
    duracion_s_media: float
    coste_tokens_media: float | None
    coste_muestras: int

    def to_dict(self) -> dict[str, object]:
        return {
            "slices": self.slices,
            "verificador_falla_pct": self.verificador_falla_pct,
            "bloqueada_controles_pct": self.bloqueada_controles_pct,
            "ci_roja_pct": self.ci_roja_pct,
            "primer_intento_pct": self.primer_intento_pct,
            "reintentos_implement_media": self.reintentos_implement_media,
            "reintentos_controles_media": self.reintentos_controles_media,
            "reintentos_ci_media": self.reintentos_ci_media,
            "reintentos_verify_media": self.reintentos_verify_media,
            "descartes_verify_pct": self.descartes_verify_pct,
            "duracion_s_media": self.duracion_s_media,
            "coste_tokens_media": self.coste_tokens_media,
            "coste_muestras": self.coste_muestras,
        }


def _aggregate(filas: list[Fila]) -> Metricas:
    """Las cifras de nivel a partir de las filas del log.

    `descartes_verify` se reporta como tasa y no como media: la pregunta que responde no es
    "cuantos de media" sino "en que fraccion de slices el contrato de salida del juez no
    aguanto". Es una propiedad del agente, no de la slice.
    """
    total = len(filas)
    costes = [f.coste_tokens for f in filas if f.coste_tokens is not None]
    return Metricas(
        slices=total,
        verificador_falla_pct=_pct(sum(1 for f in filas if f.veredicto == Veredicto.FALLA), total),
        bloqueada_controles_pct=_pct(sum(1 for f in filas if f.veredicto == Veredicto.BLOQUEADA_CONTROLES), total),
        ci_roja_pct=_pct(sum(1 for f in filas if f.ci == Ci.ROJA), total),
        primer_intento_pct=_pct(sum(1 for f in filas if f.primer_intento), total),
        reintentos_implement_media=_mean([f.reintentos_implement for f in filas]),
        reintentos_controles_media=_mean([f.reintentos_controles for f in filas]),
        reintentos_ci_media=_mean([f.reintentos_ci for f in filas]),
        reintentos_verify_media=_mean([f.reintentos_verify for f in filas]),
        descartes_verify_pct=_pct(sum(1 for f in filas if f.descartes_verify > 0), total),
        duracion_s_media=_mean([f.duracion_s for f in filas if f.duracion_s is not None]),
        coste_tokens_media=_mean(costes) if costes else None,
        coste_muestras=len(costes),
    )


def report(args: argparse.Namespace) -> int:
    path = _path(args.path)
    filas = _load(path, args.repo)
    agg = _aggregate(filas)

    if args.json:
        print(json.dumps(agg.to_dict(), ensure_ascii=False))
        return 0

    scope = args.repo or "todos los repos"
    if not filas:
        print(f"sin metricas para {scope} en {path}")
        return 0
    print(f"metricas slice-runner ({scope}) - {agg.slices} slices - {path}")
    print(f"  verificador FALLA        {agg.verificador_falla_pct}%")
    print(f"  bloqueada por controles  {agg.bloqueada_controles_pct}%")
    print(f"  CI roja                  {agg.ci_roja_pct}%")
    print(f"  slices al 1er intento    {agg.primer_intento_pct}%")
    print(f"  reintentos implement     {agg.reintentos_implement_media} media")
    print(f"  reintentos controles     {agg.reintentos_controles_media} media")
    print(f"  reintentos CI            {agg.reintentos_ci_media} media")
    print(f"  reintentos verify        {agg.reintentos_verify_media} media")
    print(f"  contrato del juez roto   {agg.descartes_verify_pct}% de slices")
    print(f"  duracion                 {agg.duracion_s_media}s media")
    if agg.coste_tokens_media is None:
        print("  coste tokens             sin datos (ver OTel de Claude Code)")
    else:
        print(f"  coste tokens             {agg.coste_tokens_media} media ({agg.coste_muestras} muestras)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI de `record` y `report`.

    Los `choices` se escriben como `[str(v) for v in ...]` y no como `list(...)` porque
    argparse formatea los suyos con `repr` en el mensaje de error, y un
    `<Veredicto.PASA: 'PASA'>` en un error de uso se lee peor que la cadena.
    """
    parser = argparse.ArgumentParser(description="Metricas durables de slice-runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="anexa un registro por slice cerrada")
    rec.add_argument("--repo", required=True)
    rec.add_argument("--slice", required=True, help="slice_id, p. ej. slice-01")
    rec.add_argument("--name", required=True)
    rec.add_argument("--veredicto", required=True, choices=[str(v) for v in Veredicto])
    rec.add_argument("--ci", default=str(Ci.NINGUNA), choices=[str(c) for c in Ci])
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
        help="rondas de vuelta al paso 5 que decide el juez (rechazo semantico)",
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
    resultado: int = args.func(args)
    return resultado


if __name__ == "__main__":
    sys.exit(main())
