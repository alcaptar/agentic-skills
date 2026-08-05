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

Lo que si mide el harness -coste en dolares, turnos y duracion- entra en el grupo `harness`,
sumado por slice a lo largo de todas sus llamadas. Los tres salen de la misma suma, asi que se
registran juntos o no se registran: pasar unos y no otros es error de uso, y si no vienen la clave
`harness` NO se escribe, ni con ceros ni con `null`. Ningun numero de este log se estima.

El log es durable y append-only, asi que los registros viejos no tienen los campos
nuevos: el agregado los trata como cero, nunca como dato ausente que invalide la fila -salvo en los
campos de medicion (`coste_tokens`, `duracion_s` y el grupo `harness`), donde ausente y cero no son
lo mismo y ausente se lee como tal, para que las filas sin dato no hundan la media-. Por
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
        [--descartes-verify-causa veredicto-incoherente|llamada-fallida] \\
        [--coste-usd 1.23 --turnos 42 --duracion-ms 65652] \\
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


class CausaDescarte(StrEnum):
    """Por que se descarto una invocacion del verificador.

    Las dos no son la misma cosa y se separan por el mismo motivo por el que `FALLA` y
    `bloqueada-controles` son veredictos distintos: `veredicto-incoherente` es un juez que
    contesto su JSON pero con un veredicto que se contradice -un `PASA` con un hallazgo `alta`-,
    y `llamada-fallida` es una invocacion que ni llego a devolver el sobre. La primera se arregla
    apretando la rubrica; la segunda, mirando el harness. Sumadas no dicen a quien mirar.

    El campo es opcional: el flujo viejo no distingue las dos y el historico no las trae.
    """

    VEREDICTO_INCOHERENTE = "veredicto-incoherente"
    LLAMADA_FALLIDA = "llamada-fallida"


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
class Harness:
    """Lo que midio el harness en una slice, sumado a lo largo de todas sus llamadas.

    Agrupados y no sueltos porque los tres salen de la misma suma: separados, una fila no diria
    de cuantas llamadas es cada numero, y `harness` significa exactamente "esto lo midio el
    harness", frente a los campos que rellena quien invoca.
    """

    coste_usd: float
    turnos: int
    duracion_ms: int

    @staticmethod
    def from_args(args: argparse.Namespace) -> Harness | None:
        """El grupo, o `None` si esta slice no trae medicion del harness.

        Que vengan los tres o ninguno lo garantiza `_error_de_uso` antes de llegar aqui.
        """
        if args.coste_usd is None:
            return None

        return Harness(coste_usd=args.coste_usd, turnos=args.turnos, duracion_ms=args.duracion_ms)

    def to_dict(self) -> dict[str, object]:
        return {"coste_usd": self.coste_usd, "turnos": self.turnos, "duracion_ms": self.duracion_ms}


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
    harness: Harness | None = None
    descartes_verify_causa: CausaDescarte | None = None

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
            harness=Harness.from_args(args),
            descartes_verify_causa=(
                CausaDescarte(args.descartes_verify_causa) if args.descartes_verify_causa else None
            ),
        )

    def to_dict(self) -> dict[str, object]:
        """Las claves del log durable. Las opcionales que no hay se omiten, no se escriben `null`.

        `duracion_s` y `coste_tokens` si se escriben como `null` porque hay historico con la clave
        presente y vacia: quitarlas ahora solo anadiria una forma mas que `Fila.from_row` tendria
        que tolerar. Las nuevas nacen omitiendose, que es lo que distingue "no medido" de "cero".
        """
        escrito: dict[str, object] = {
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
        if self.harness is not None:
            escrito["harness"] = self.harness.to_dict()
        if self.descartes_verify_causa is not None:
            escrito["descartes_verify_causa"] = str(self.descartes_verify_causa)

        return escrito


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


def _grupo(row: dict[str, object], clave: str) -> dict[str, object]:
    """El grupo anidado `clave`, o vacio si la fila es anterior al grupo o trae otra cosa.

    Vacio y no ausente para que quien lea dentro use los mismos `_numero`/`_opcional` que el
    resto del modulo, sin una segunda forma de preguntar por un campo que no esta.
    """
    valor = row.get(clave)
    return {str(k): v for k, v in valor.items()} if isinstance(valor, dict) else {}


def _causa(row: dict[str, object], clave: str) -> CausaDescarte | None:
    """La causa del descarte si la fila trae una del vocabulario, y si no, ninguna.

    Una causa que no reconocemos se lee como ausente por lo mismo que `_load` se salta una linea
    corrupta: el log es durable y una fila rara no puede tumbar el agregado de todo el historico
    que si es legible.
    """
    valor = row.get(clave)
    return CausaDescarte(valor) if isinstance(valor, str) and valor in set(CausaDescarte) else None


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
    coste_usd: float | None
    turnos: float | None
    duracion_ms: float | None
    descartes_verify_causa: CausaDescarte | None

    @staticmethod
    def from_row(row: dict[str, object]) -> Fila:
        veredicto = _texto(row, "veredicto")
        harness = _grupo(row, "harness")
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
            coste_usd=_opcional(harness, "coste_usd"),
            turnos=_opcional(harness, "turnos"),
            duracion_ms=_opcional(harness, "duracion_ms"),
            descartes_verify_causa=_causa(row, "descartes_verify_causa"),
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


def _error_de_uso(args: argparse.Namespace) -> str | None:
    """El mensaje del error de uso de `record`, o `None` si los flags son coherentes.

    Se comprueba antes de escribir porque el log es append-only: una fila con media medicion o con
    una causa que no atribuye nada se queda ahi para siempre, y el agregado no puede distinguirla
    de una buena. Los emite `parser.error`, o sea exit 2 y nada escrito, en vez de una excepcion.
    """
    gasto = (args.coste_usd, args.turnos, args.duracion_ms)
    if any(dato is not None for dato in gasto) and any(dato is None for dato in gasto):
        return "--coste-usd, --turnos y --duracion-ms salen de la misma suma: van los tres o ninguno"
    if args.descartes_verify_causa and not args.descartes_verify:
        return "--descartes-verify-causa sin --descartes-verify: no hay ningun descarte al que atribuirla"

    return None


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


def _medicion(media: float | None, muestras: int, unidad: str = "") -> str:
    """Como se lee una media del harness, incluido el caso de que ninguna fila la traiga.

    El caso vacio se dice con palabras y no con un `0.0`, que se leeria como una medicion real:
    decidir "cuando subir de nivel" con un cero inventado es peor que decidir sin el dato.
    """
    if media is None:
        return "sin datos (ninguna fila trae medicion del harness)"

    return f"{media}{unidad} media ({muestras} muestras)"


@dataclass(frozen=True, kw_only=True, slots=True)
class DescartesPorCausa:
    """En cuantas slices se descarto al verificador por cada causa.

    Solo cuentan las filas que declaran la causa: el flujo viejo y el historico no la escriben, y
    repartirlas entre las dos causas seria inventarse justo el dato que el campo existe para
    saber. Un campo que se escribe y nadie agrega no sirve para decidir, asi que el reparto entra
    en el reporte junto con el campo y no despues.
    """

    veredicto_incoherente: int = 0
    llamada_fallida: int = 0

    @staticmethod
    def from_filas(filas: list[Fila]) -> DescartesPorCausa:
        declaradas = [f.descartes_verify_causa for f in filas if f.descartes_verify_causa is not None]

        return DescartesPorCausa(
            veredicto_incoherente=declaradas.count(CausaDescarte.VEREDICTO_INCOHERENTE),
            llamada_fallida=declaradas.count(CausaDescarte.LLAMADA_FALLIDA),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            str(CausaDescarte.VEREDICTO_INCOHERENTE): self.veredicto_incoherente,
            str(CausaDescarte.LLAMADA_FALLIDA): self.llamada_fallida,
        }

    def __str__(self) -> str:
        return ", ".join(f"{clave} {valor}" for clave, valor in self.to_dict().items())


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
    descartes_por_causa: DescartesPorCausa
    duracion_s_media: float
    coste_tokens_media: float | None
    coste_muestras: int
    coste_usd_media: float | None
    coste_usd_muestras: int
    turnos_media: float | None
    turnos_muestras: int
    duracion_ms_media: float | None
    duracion_ms_muestras: int

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
            "descartes_por_causa": self.descartes_por_causa.to_dict(),
            "duracion_s_media": self.duracion_s_media,
            "coste_tokens_media": self.coste_tokens_media,
            "coste_muestras": self.coste_muestras,
            "coste_usd_media": self.coste_usd_media,
            "coste_usd_muestras": self.coste_usd_muestras,
            "turnos_media": self.turnos_media,
            "turnos_muestras": self.turnos_muestras,
            "duracion_ms_media": self.duracion_ms_media,
            "duracion_ms_muestras": self.duracion_ms_muestras,
        }


def _aggregate(filas: list[Fila]) -> Metricas:
    """Las cifras de nivel a partir de las filas del log.

    `descartes_verify` se reporta como tasa y no como media: la pregunta que responde no es
    "cuantos de media" sino "en que fraccion de slices el contrato de salida del juez no
    aguanto". Es una propiedad del agente, no de la slice.
    """
    total = len(filas)
    costes = [f.coste_tokens for f in filas if f.coste_tokens is not None]
    dolares = [f.coste_usd for f in filas if f.coste_usd is not None]
    turnos = [f.turnos for f in filas if f.turnos is not None]
    duraciones = [f.duracion_ms for f in filas if f.duracion_ms is not None]
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
        descartes_por_causa=DescartesPorCausa.from_filas(filas),
        duracion_s_media=_mean([f.duracion_s for f in filas if f.duracion_s is not None]),
        coste_tokens_media=_mean(costes) if costes else None,
        coste_muestras=len(costes),
        coste_usd_media=_mean(dolares) if dolares else None,
        coste_usd_muestras=len(dolares),
        turnos_media=_mean(turnos) if turnos else None,
        turnos_muestras=len(turnos),
        duracion_ms_media=_mean(duraciones) if duraciones else None,
        duracion_ms_muestras=len(duraciones),
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
    print(f"  descartes por causa      {agg.descartes_por_causa}")
    print(f"  duracion                 {agg.duracion_s_media}s media")
    if agg.coste_tokens_media is None:
        print("  coste tokens             sin datos (ver OTel de Claude Code)")
    else:
        print(f"  coste tokens             {agg.coste_tokens_media} media ({agg.coste_muestras} muestras)")
    print(f"  coste $                  {_medicion(agg.coste_usd_media, agg.coste_usd_muestras)}")
    print(f"  turnos del harness       {_medicion(agg.turnos_media, agg.turnos_muestras)}")
    print(f"  duracion del harness     {_medicion(agg.duracion_ms_media, agg.duracion_ms_muestras, 'ms')}")
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
    rec.add_argument(
        "--descartes-verify-causa",
        default=None,
        choices=[str(c) for c in CausaDescarte],
        help="de que clase fueron los descartes; opcional, el flujo viejo no la distingue",
    )
    rec.add_argument("--duracion-s", type=int, default=None)
    rec.add_argument("--coste-tokens", type=int, default=None)
    rec.add_argument("--coste-usd", type=float, default=None, help="coste en dolares que sumo el harness")
    rec.add_argument("--turnos", type=int, default=None, help="turnos que sumo el harness")
    rec.add_argument("--duracion-ms", type=int, default=None, help="duracion en ms que sumo el harness")
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
    if args.func is record:
        problema = _error_de_uso(args)
        if problema:
            rec.error(problema)
    resultado: int = args.func(args)
    return resultado


if __name__ == "__main__":
    sys.exit(main())
