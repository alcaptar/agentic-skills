#!/usr/bin/env python3
"""Metricas durables de slice-runner (patron offload-deterministic).

El estado del run vive en el issue de GitHub, no en el repo. Para decidir con datos
"cuando subir de nivel" hace falta ademas un rastro de telemetria que NUNCA entre en el
repo/PR y sobreviva a los runs. Este log vive fuera del repo:

    ~/.claude/slice-runner/log/metrics.jsonl   append-only, una linea por slice cerrada

Lo anexa el programa el mismo, en Python puro y sin lanzar este script como subproceso
(`LocalMetricsLog`, `docs/conventions/infrastructure.md`); este modulo solo lo agrega. Las cifras
del reporte son deterministas: tasa de FALLA del verificador, tasa de bloqueo por
controles, % de slices al primer intento, media de reintentos, tasa de CI roja. Coste en
tokens NO se mide aqui (sale de la telemetria/OTel de Claude Code): se admite como campo
opcional best-effort y, si no viene, no se inventa.

Lo que si mide el harness -coste en dolares, turnos, duracion y tokens leidos de cache- entra en
el grupo `harness`, sumado por slice a lo largo de todas sus llamadas. Los cuatro salen de la misma
suma, asi que viajan juntos o no viajan: si no vienen, la clave `harness` no se escribe, ni con
ceros ni con `null`. Ningun numero de este log se estima.

Con que modelo se hizo la slice tampoco lo estima quien escribe: `modelos` es lo que el propio
harness declaro haber usado (una lista, por si una slice uso mas de uno -implementador y juez, o un
reintento que cambio de modelo-), nunca el alias que se le pidio. Y `variante` nombra que forma de
trabajar del pipeline se estaba probando, para poder comparar dos sin rehacer el analisis a mano. Los
dos son vocabulario abierto -crecen con cada modelo y cada experimento nuevo- y ninguno se escribe si
no se declara: una fila sin `modelos` o sin `variante` se lee como "desconocido" en el reporte, no
como un valor mas del vocabulario.

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
    metrics.py report [--repo <repo>] [--json] [--path RUTA]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_Causa = TypeVar("_Causa", bound=StrEnum)

DEFAULT_PATH = Path.home() / ".claude" / "slice-runner" / "log" / "metrics.jsonl"
DESCONOCIDO = "desconocido"
"""Etiqueta de agrupacion para una fila que no declara modelo o variante.

No es un tercer valor del vocabulario abierto: es la ausencia del dato -historico anterior a esta
slice, o una invocacion que no lo paso-, y por eso vive fuera de `Fila.from_row` en vez de dentro:
la ausencia se lee al agrupar, no al normalizar la fila."""


class Veredicto(StrEnum):
    """Como acabo una slice, en el vocabulario del log durable.

    `FALLA` es el veto del juez adversarial. `BLOQUEADA_CONTROLES` es agotar los reintentos de
    lint/tipos/tests: un fallo mecanico, que se registra aparte porque confundirlo con un veto
    del juez dejaria inservible el unico instrumento para calibrarlo. `BLOQUEADA_HIGIENE` es agotar
    el presupuesto propio de `pr-hygiene` (indice staged con algo no declarado, o un artefacto
    prohibido): tampoco es un veto del juez ni un control en rojo -no se llego a ejecutar ninguno-,
    asi que compartir cualquiera de los otros dos dejaria ese mismo instrumento leyendo un fallo que
    no fue suyo. Solo la variante `programa` la escribe hoy: su agente (`SKILL.md`, paso 6.2)
    reintenta `pr-hygiene` sin limite propio.
    """

    PASA = "PASA"
    FALLA = "FALLA"
    BLOQUEADA_CONTROLES = "bloqueada-controles"
    BLOQUEADA_HIGIENE = "bloqueada-higiene"
    ABORTADA_PRESUPUESTO = "abortada-presupuesto"


class Ci(StrEnum):
    """Como acabo la CI de la PR de la slice."""

    VERDE = "green"
    ROJA = "red"
    NINGUNA = "none"
    CONFLICTO = "conflict"


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


class CausaCiIndeterminada(StrEnum):
    """Por que no se pudo determinar el estado de la integracion continua.

    `COMANDO_FALLIDO` es `gh pr checks` fallando de verdad -credenciales, red, una pull request
    que no resuelve-; `RESPUESTA_NO_LEGIBLE` es una respuesta que si llego pero no se pudo
    interpretar. Se separan por el mismo motivo que `CausaDescarte`: cada una se arregla mirando
    un sitio distinto, y sumadas no dicen cual.

    El campo es opcional: el historico anterior a esta slice no lo trae.
    """

    COMANDO_FALLIDO = "comando-fallido"
    RESPUESTA_NO_LEGIBLE = "respuesta-no-legible"


_VEREDICTO_VIEJO = "bloqueada-puertas"
_REINTENTOS_CONTROLES_VIEJO = "reintentos_puertas"
"""Formas viejas escritas en el log durable, de cuando los controles se llamaban "puertas".

Solo se leen (las consume `Fila.from_row`): lo que se emite es siempre la forma canonica.
"""


def _path(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else DEFAULT_PATH


def _texto(row: dict[str, object], clave: str) -> str:
    valor = row.get(clave)
    return valor if isinstance(valor, str) else ""


def _texto_opcional(row: dict[str, object], clave: str) -> str | None:
    """Igual que `_texto`, pero distingue "no declarado" de una cadena vacia.

    `variante` no tiene default razonable: una cadena vacia se leeria como un valor mas del
    vocabulario abierto en vez de como ausencia del dato.
    """
    valor = row.get(clave)
    return valor if isinstance(valor, str) else None


def _lista_str(row: dict[str, object], clave: str) -> tuple[str, ...]:
    """Los elementos de texto de una lista, o vacio si la fila es anterior al campo o trae otra cosa."""
    valor = row.get(clave)
    if isinstance(valor, list) and all(isinstance(elemento, str) for elemento in valor):
        return tuple(valor)
    return ()


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


def _causa(row: dict[str, object], clave: str, vocabulario: type[_Causa]) -> _Causa | None:
    """La causa si la fila trae una del `vocabulario`, y si no, ninguna.

    Una causa que no reconocemos se lee como ausente por lo mismo que `_load` se salta una linea
    corrupta: el log es durable y una fila rara no puede tumbar el agregado de todo el historico
    que si es legible.
    """
    valor = row.get(clave)
    return vocabulario(valor) if isinstance(valor, str) and valor in set(vocabulario) else None


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
    tokens_cache: float | None
    descartes_verify_causa: CausaDescarte | None
    ci_indeterminada_causa: CausaCiIndeterminada | None
    modelos: tuple[str, ...]
    variante: str | None

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
            tokens_cache=_opcional(harness, "tokens_cache"),
            descartes_verify_causa=_causa(row, "descartes_verify_causa", CausaDescarte),
            ci_indeterminada_causa=_causa(row, "ci_indeterminada_causa", CausaCiIndeterminada),
            modelos=_lista_str(row, "modelos"),
            variante=_texto_opcional(row, "variante"),
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
class Grupo:
    """Las cifras de nivel de un solo valor de un campo abierto (un modelo, o una variante).

    Coste en dolares y tokens de cache son las dos cifras que motivaron este reporte -comparar dos
    formas de trabajar sin rehacer la cuenta a mano-, y `primer_intento_pct` es lo que impide leer un
    ahorro como una mejora si en realidad se pago con calidad: una variante mas barata que tambien
    reintenta mas no esta ganando nada.
    """

    slices: int
    primer_intento_pct: float
    coste_usd_media: float | None
    coste_usd_muestras: int
    tokens_cache_media: float | None
    tokens_cache_muestras: int

    @staticmethod
    def from_filas(filas: list[Fila]) -> Grupo:
        total = len(filas)
        dolares = [f.coste_usd for f in filas if f.coste_usd is not None]
        cache = [f.tokens_cache for f in filas if f.tokens_cache is not None]
        return Grupo(
            slices=total,
            primer_intento_pct=_pct(sum(1 for f in filas if f.primer_intento), total),
            coste_usd_media=_mean(dolares) if dolares else None,
            coste_usd_muestras=len(dolares),
            tokens_cache_media=_mean(cache) if cache else None,
            tokens_cache_muestras=len(cache),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "slices": self.slices,
            "primer_intento_pct": self.primer_intento_pct,
            "coste_usd_media": self.coste_usd_media,
            "coste_usd_muestras": self.coste_usd_muestras,
            "tokens_cache_media": self.tokens_cache_media,
            "tokens_cache_muestras": self.tokens_cache_muestras,
        }


def _agrupar(filas: list[Fila], etiquetas: Callable[[Fila], tuple[str, ...]]) -> dict[str, Grupo]:
    """Agrupa las filas por cada etiqueta que declaran; las que no declaran ninguna van a `DESCONOCIDO`.

    Una fila puede caer en mas de un grupo -una slice puede haber usado mas de un modelo, el del
    implementador y el del juez, o un reintento que cambio de modelo-, y eso es la fila reflejando lo
    que de verdad paso en vez de quedarse con uno solo en silencio.
    """
    grupos: dict[str, list[Fila]] = {}
    for fila in filas:
        for etiqueta in etiquetas(fila) or (DESCONOCIDO,):
            grupos.setdefault(etiqueta, []).append(fila)
    return {etiqueta: Grupo.from_filas(subfilas) for etiqueta, subfilas in grupos.items()}


@dataclass(frozen=True, kw_only=True, slots=True)
class Metricas:
    """Las cifras del reporte. Las claves de `to_dict` son las que consume `SKILL.md`."""

    slices: int
    verificador_falla_pct: float
    bloqueada_controles_pct: float
    bloqueada_higiene_pct: float
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
    tokens_cache_media: float | None
    tokens_cache_muestras: int
    por_modelo: dict[str, Grupo]
    por_variante: dict[str, Grupo]

    def to_dict(self) -> dict[str, object]:
        return {
            "slices": self.slices,
            "verificador_falla_pct": self.verificador_falla_pct,
            "bloqueada_controles_pct": self.bloqueada_controles_pct,
            "bloqueada_higiene_pct": self.bloqueada_higiene_pct,
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
            "tokens_cache_media": self.tokens_cache_media,
            "tokens_cache_muestras": self.tokens_cache_muestras,
            "por_modelo": {modelo: grupo.to_dict() for modelo, grupo in self.por_modelo.items()},
            "por_variante": {variante: grupo.to_dict() for variante, grupo in self.por_variante.items()},
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
    tokens_cache = [f.tokens_cache for f in filas if f.tokens_cache is not None]
    return Metricas(
        slices=total,
        verificador_falla_pct=_pct(sum(1 for f in filas if f.veredicto == Veredicto.FALLA), total),
        bloqueada_controles_pct=_pct(sum(1 for f in filas if f.veredicto == Veredicto.BLOQUEADA_CONTROLES), total),
        bloqueada_higiene_pct=_pct(sum(1 for f in filas if f.veredicto == Veredicto.BLOQUEADA_HIGIENE), total),
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
        tokens_cache_media=_mean(tokens_cache) if tokens_cache else None,
        tokens_cache_muestras=len(tokens_cache),
        por_modelo=_agrupar(filas, lambda f: f.modelos),
        por_variante=_agrupar(filas, lambda f: (f.variante,) if f.variante else ()),
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
    print(f"  bloqueada por higiene    {agg.bloqueada_higiene_pct}%")
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
    print(f"  tokens de cache          {_medicion(agg.tokens_cache_media, agg.tokens_cache_muestras)}")
    _imprime_grupos("por modelo", agg.por_modelo)
    _imprime_grupos("por variante", agg.por_variante)
    return 0


def _imprime_grupos(titulo: str, grupos: dict[str, Grupo]) -> None:
    """Una linea por valor del campo abierto, para comparar dos formas de trabajar leyendo el reporte."""
    print(f"  {titulo}:")
    for etiqueta, grupo in sorted(grupos.items()):
        coste = _medicion(grupo.coste_usd_media, grupo.coste_usd_muestras)
        cache = _medicion(grupo.tokens_cache_media, grupo.tokens_cache_muestras)
        print(
            f"    {etiqueta:30s} {grupo.slices} slices, 1er intento {grupo.primer_intento_pct}%, "
            f"coste $ {coste}, tokens de cache {cache}"
        )


def main(argv: list[str] | None = None) -> int:
    """CLI de `report`."""
    parser = argparse.ArgumentParser(description="Metricas durables de slice-runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

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
