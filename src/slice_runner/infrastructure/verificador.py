"""Adaptador del puerto del juez sobre `claude -p`.

Aqui vive todo lo que es detalle de la herramienta: la receta de flags, el sobre JSON que devuelve
y la traduccion de ese sobre a los tipos del dominio.

La coherencia del veredicto no se comprueba aqui: la sigue comprobando `valida_veredicto` de
`controles.py`, que es el `verify-verdict` que ya existia. `--json-schema` garantiza la **forma**
del objeto, no que un `PASA` no venga acompanado de un hallazgo de severidad alta.
"""

from __future__ import annotations

import json
from dataclasses import MISSING, dataclass, fields
from typing import TYPE_CHECKING

from controles import valida_veredicto
from slice_runner.domain.veredicto import Dictamen, Hallazgo, Severidad, Veredicto, VeredictoInvalidoError
from slice_runner.domain.verificacion import Verificador

if TYPE_CHECKING:
    from slice_runner.domain.verificacion import PeticionDeVerificacion
    from slice_runner.infrastructure.proceso import Proceso, SalidaDeProceso

_EJECUTABLE = "claude"

_HERRAMIENTAS = ("Read", "Grep", "Glob", "Skill")
"""Lo que el juez necesita para leer el diff y el codigo de alrededor, y para cargar las skills que
su propia rubrica le manda: `backend-best-practices` como vara secundaria y `test-desiderata` sobre
los tests nuevos. Sin `Skill` esos dos items llegan como orden que no puede ejecutar, y eso es la
vara vacia que la rubrica declara causa raiz de las desviaciones silenciosas.

Sin `Bash` a proposito: no puede correr lint, tipos ni tests aunque quisiera -ya pasaron antes de
invocarlo-, y sin `Write`/`Edit` porque el que verifica no implementa. `Skill` no afloja eso: no
trae `Bash` con ella.

Que este juego sea el mismo que declara la cabecera de `agents/slice-verifier.md` lo comprueba un
test de contrato: la cabecera se descarta antes de mandar el prompt, asi que una herramienta que
figure alli y falte aqui no la concede nadie.
"""

_TIPOS_DE_HALLAZGO: dict[str, dict[str, object]] = {
    "regla": {"type": "string"},
    "path": {"type": "string"},
    "linea": {"type": "integer"},
    "severidad": {"type": "string", "enum": [str(s) for s in Severidad]},
    "evidencia": {"type": "string"},
    "detalle": {"type": "string"},
}
"""Tipo JSON de cada campo de `Hallazgo`. Los vocabularios cerrados salen de las enumeraciones del
dominio; que el juego de claves siga siendo el del dataclass lo comprueba un test."""


def esquema_del_veredicto() -> dict[str, object]:
    """El esquema que se le pasa a `--json-schema` para acotar la salida del juez.

    Se deriva de los tipos del dominio en vez de escribirse aparte: es la tercera copia de un
    contrato que ya esta en la rubrica del agente y en `verify-verdict`, y una copia que nadie
    ancla es una que deriva.

    Lo que el esquema **no** garantiza es la coherencia: un `PASA` que convive con un hallazgo de
    severidad alta lo cumple entero. Por eso `verify-verdict` sigue haciendo falta.
    """
    obligatorios = [f.name for f in fields(Hallazgo) if f.default is MISSING]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["veredicto", "hallazgos"],
        "properties": {
            "veredicto": {"type": "string", "enum": [str(d) for d in Dictamen]},
            "hallazgos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": obligatorios,
                    "properties": dict(_TIPOS_DE_HALLAZGO),
                },
            },
        },
    }


def argv_del_verificador() -> list[str]:
    """La receta de flags medida contra la interfaz real, sin el prompt.

    El prompt **no** viaja aqui: `--tools` es variadico y se traga el argumento posicional que
    venga detras, con lo que la invocacion muere pidiendo un prompt que si estaba. Por eso las
    herramientas van en un solo argumento separado por comas y el prompt entra por entrada
    estandar.

    El modelo tampoco se pasa, asi que el juez corre con el que `claude -p` tenga por defecto: no lo
    decide esta receta ni el `model: inherit` de la cabecera del agente, que solo significaba algo
    en el registro de agentes. Pinearlo es una decision de coste y calidad que **ninguna slice ha
    tomado todavia** y queda abierta; cuando se tome, entra aqui como flag explicito.
    """
    return [
        _EJECUTABLE,
        "-p",
        "--output-format",
        "json",
        "--tools",
        ",".join(_HERRAMIENTAS),
        "--strict-mcp-config",
        "--json-schema",
        json.dumps(esquema_del_veredicto(), ensure_ascii=False),
    ]


_CLAVES_DEL_SOBRE = frozenset(
    {
        "api_error_status",
        "duration_api_ms",
        "duration_ms",
        "fast_mode_disabled_reason",
        "fast_mode_state",
        "is_error",
        "modelUsage",
        "num_turns",
        "permission_denials",
        "result",
        "session_id",
        "stop_reason",
        "structured_output",
        "subtype",
        "terminal_reason",
        "time_to_request_ms",
        "total_cost_usd",
        "ttft_ms",
        "ttft_stream_ms",
        "type",
        "usage",
        "uuid",
    }
)
"""Las claves que emite `claude -p --output-format json`, medidas contra la interfaz real.

Es a proposito mas ancha que lo que el programa consume: sirve para decidir si el sobre es el que
se midio, no para describir el modelo. Una clave nueva del harness corta la ejecucion en vez de
colarse ignorada, porque el veredicto que decide un merge no se lee de un payload que ya no es el
que se conoce; anadirla aqui es una linea.
"""

_CLAVES_DEL_HALLAZGO = frozenset(f.name for f in fields(Hallazgo))
"""Derivadas del dataclass: una lista escrita en paralelo es la forma de que un campo nuevo quede
rechazado como desconocido por haberse olvidado de anadirlo en dos sitios."""


def _texto(datos: dict[str, object], clave: str) -> str:
    valor = datos.get(clave)
    if not isinstance(valor, str):
        raise VeredictoInvalidoError(f"`{clave}` tiene que ser texto, no {type(valor).__name__}")
    return valor


def _bandera(datos: dict[str, object], clave: str) -> bool:
    valor = datos.get(clave)
    if not isinstance(valor, bool):
        raise VeredictoInvalidoError(f"`{clave}` tiene que ser true o false, no {type(valor).__name__}")
    return valor


def _objeto(datos: dict[str, object], clave: str) -> dict[str, object]:
    valor = datos.get(clave)
    if not isinstance(valor, dict):
        raise VeredictoInvalidoError(f"`{clave}` tiene que ser un objeto, no {type(valor).__name__}")
    return valor


def _lista(datos: dict[str, object], clave: str) -> list[object]:
    valor = datos.get(clave)
    if not isinstance(valor, list):
        raise VeredictoInvalidoError(f"`{clave}` tiene que ser una lista, no {type(valor).__name__}")
    return valor


def _linea(datos: dict[str, object]) -> int | None:
    valor = datos.get("linea")
    if valor is None:
        return None
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise VeredictoInvalidoError(f"`linea` tiene que ser un entero, no {type(valor).__name__}")
    return valor


def _severidad(datos: dict[str, object]) -> Severidad:
    valor = _texto(datos, "severidad")
    if valor not in tuple(Severidad):
        raise VeredictoInvalidoError(f"severidad invalida: {valor!r}")
    return Severidad(valor)


def _sin_claves_de_mas(datos: dict[str, object], conocidas: frozenset[str], que: str) -> None:
    desconocidas = sorted(set(datos) - conocidas)
    if desconocidas:
        raise VeredictoInvalidoError(f"claves desconocidas en {que}: {', '.join(desconocidas)}")


@dataclass(frozen=True, kw_only=True, slots=True)
class SalidaHarness:
    """El sobre de `claude -p --output-format json`, reducido a lo que el programa consume.

    `structured_output` es **el** campo del veredicto: con `--json-schema` viene ya como objeto
    parseado. `result` trae lo mismo como cadena, y leerlo de ahi seria reimplementar el harness.
    """

    is_error: bool
    structured_output: dict[str, object]

    @staticmethod
    def from_dict(datos: dict[str, object]) -> SalidaHarness:
        """Valida el sobre al entrar: clave desconocida y tipo equivocado son error, no matiz."""
        _sin_claves_de_mas(datos, _CLAVES_DEL_SOBRE, "el sobre del harness")
        return SalidaHarness(
            is_error=_bandera(datos, "is_error"),
            structured_output=_objeto(datos, "structured_output"),
        )


def _hallazgo_desde(crudo: object) -> Hallazgo:
    """Un hallazgo del veredicto, con la severidad ya convertida al vocabulario del dominio."""
    if not isinstance(crudo, dict):
        raise VeredictoInvalidoError(f"cada hallazgo tiene que ser un objeto, no {type(crudo).__name__}")
    _sin_claves_de_mas(crudo, _CLAVES_DEL_HALLAZGO, "un hallazgo")
    return Hallazgo(
        regla=_texto(crudo, "regla"),
        path=_texto(crudo, "path"),
        severidad=_severidad(crudo),
        evidencia=_texto(crudo, "evidencia"),
        detalle=_texto(crudo, "detalle"),
        linea=_linea(crudo),
    )


def _veredicto_desde(estructura: dict[str, object]) -> Veredicto:
    """Traduce el veredicto del juez, ya comprobada su coherencia, a los tipos del dominio.

    Se le vuelve a serializar para pasarlo por `valida_veredicto`, que recibe texto porque nacio
    leyendo el mensaje final del agente. Es un ida y vuelta, y es mas barato que duplicar aqui sus
    comprobaciones: pasada la validacion, el dictamen y las severidades ya son vocabulario cerrado.
    """
    revision = valida_veredicto(json.dumps(estructura, ensure_ascii=False))
    if not revision.passed:
        raise VeredictoInvalidoError("; ".join(revision.hallazgos))
    return Veredicto(
        dictamen=Dictamen(_texto(estructura, "veredicto")),
        hallazgos=tuple(_hallazgo_desde(h) for h in _lista(estructura, "hallazgos")),
    )


def _prompt(peticion: PeticionDeVerificacion) -> str:
    """Las instrucciones del juez mas los tres datos que esta orden tiene, por entrada estandar.

    Los tres son la ruta del repo y las dos rutas del bundle, y **no son todos** los que la rubrica
    que viaja aqui declara obligatorios. `agents/slice-verifier.md`, en "Lo que recibes", pide
    ademas el issue y el `slice_id`, la linea `ACEPTACION:`, el checklist de slices del issue, la
    `SENAL` y las fuentes de convencion -su vara de medir principal-, mas la lista de rutas
    etiquetadas produccion/test. Nada de eso se compone aqui, asi que hoy el juez recibe la vara
    vacia y su propia rubrica le manda decirlo en el veredicto en vez de suplirlo.

    Es hueco declarado, no olvido: la superficie de la orden la fija su criterio de aceptacion en
    `--repo` y `--base`, y los datos que faltan viven en el issue, que este programa todavia no sabe
    leer. Los trae la slice-04 (lee del issue padre la intencion, las fuentes y los controles, y de
    cada subissue su aceptacion, su senal y su estado) sobre el formato que crea la slice-12; la
    lista etiquetada produccion/test la produce el implementador de la slice-03, y quien tendra las
    dos cosas a la vez para meterlas en este prompt es el loop de la slice-09. Hasta entonces,
    cualquier invocacion de `verificar` juzga con menos vara de la que la rubrica pide.
    """
    return "\n".join(
        [
            peticion.instrucciones,
            "",
            "## Datos del run",
            "",
            f"- ruta del repo: {peticion.repo}",
            f"- `slice.diff`: {peticion.diff.slice_diff}",
            f"- `files.txt`: {peticion.diff.files} ({peticion.diff.n_ficheros} ficheros)",
        ]
    )


def _sobre_de(salida: SalidaDeProceso) -> SalidaHarness:
    """Lee el sobre, o explica con lo que dejo el proceso por que no hay sobre que leer."""
    try:
        datos = json.loads(salida.stdout)
    except json.JSONDecodeError as exc:
        motivo = " ".join((salida.stderr or salida.stdout).split())[:200] or "(sin salida)"
        raise VeredictoInvalidoError(f"el harness no devolvio JSON (codigo {salida.codigo}): {motivo}") from exc
    if not isinstance(datos, dict):
        raise VeredictoInvalidoError(f"el sobre del harness tiene que ser un objeto, no {type(datos).__name__}")
    sobre = SalidaHarness.from_dict(datos)
    if sobre.is_error:
        raise VeredictoInvalidoError("el harness marco la llamada como fallida (`is_error`)")
    return sobre


class VerificadorClaude(Verificador):
    """El juez adversarial, invocado como `claude -p` en el anfitrion."""

    def __init__(self, *, proceso: Proceso) -> None:
        self._proceso = proceso

    def verifica(self, peticion: PeticionDeVerificacion) -> Veredicto:
        salida = self._proceso.corre(argv_del_verificador(), entrada=_prompt(peticion))
        return _veredicto_desde(_sobre_de(salida).structured_output)
