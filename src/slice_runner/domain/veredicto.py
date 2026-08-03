"""El veredicto del juez adversarial, en el vocabulario del dominio.

El contrato que describen estos tipos lo fija la rubrica de `agents/slice-verifier.md`, que es
lo que produce el objeto. `controles.py` tiene hoy un gemelo de estas dos enumeraciones porque su
`verify-verdict` valida el mismo documento desde el otro lado; `tests/test_skill_contracts.py`
ancla las dos copias a la rubrica para que no puedan derivar por separado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Dictamen(StrEnum):
    """Los dos veredictos que puede emitir el juez.

    Se llama `Dictamen` y no `Veredicto` porque el veredicto entero es el dictamen **mas** los
    hallazgos que lo sostienen, y confundirlos es lo que hace que un `PASA` con un hallazgo de
    severidad alta parezca representable.
    """

    PASA = "PASA"
    FALLA = "FALLA"


class Severidad(StrEnum):
    """Severidad de un hallazgo. Una `alta` implica FALLA; el resto es juicio del juez."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


@dataclass(frozen=True, kw_only=True, slots=True)
class Hallazgo:
    """Un incumplimiento concreto, con la evidencia citable que lo hace bloqueante.

    `linea` es el unico campo opcional, y no por comodidad: hay reglas de la rubrica (una pieza
    que **falta**) cuya evidencia no vive en ninguna linea del diff.
    """

    regla: str
    path: str
    severidad: Severidad
    evidencia: str
    detalle: str
    linea: int | None = None

    def to_dict(self) -> dict[str, object]:
        datos: dict[str, object] = {
            "regla": self.regla,
            "path": self.path,
            "severidad": str(self.severidad),
            "evidencia": self.evidencia,
            "detalle": self.detalle,
        }
        if self.linea is not None:
            datos["linea"] = self.linea
        return datos


@dataclass(frozen=True, kw_only=True, slots=True)
class Veredicto:
    """Lo que el juez decide sobre una slice: el dictamen y los hallazgos que lo sostienen."""

    dictamen: Dictamen
    hallazgos: tuple[Hallazgo, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"veredicto": str(self.dictamen), "hallazgos": [h.to_dict() for h in self.hallazgos]}


class VeredictoInvalidoError(ValueError):
    """La invocacion del juez no dejo un veredicto utilizable.

    Cubre las dos formas de quedarse sin veredicto -la llamada al harness que falla y el veredicto
    que incumple el contrato-, porque para quien decide el merge las dos significan lo mismo: no
    hay juicio. Cual de las dos fue va en el mensaje, que es lo que alimenta la `causa` del log
    durable de metricas.
    """
