"""Tests del veredicto: lo unico que decide es como se serializa para quien lo consume."""

from __future__ import annotations

from slice_runner.domain.veredicto import Dictamen, Hallazgo, Severidad, Veredicto

_SIN_LINEA = Hallazgo(
    regla="cobertura-capa",
    path="src/x.py",
    severidad=Severidad.ALTA,
    evidencia="el criterio de aceptacion no tiene test",
    detalle="falta el test que lo acredita",
)


def test_un_hallazgo_sin_linea_no_emite_la_clave() -> None:
    """Ausente, no `null`.

    El contrato declara `linea` opcional y de tipo entero, asi que un `null` es una clave presente
    con un valor que el propio esquema del veredicto rechaza. Y hay hallazgos legitimos sin linea
    -una pieza que falta no esta en ninguna-, o sea que este no es el caso raro.
    """
    assert "linea" not in _SIN_LINEA.to_dict()


def test_un_hallazgo_con_linea_la_emite_como_entero() -> None:
    """Como entero y no como texto: quien lee el veredicto la usa para senalar el sitio del diff."""
    con_linea = Hallazgo(
        regla="convenciones",
        path="src/x.py",
        severidad=Severidad.MEDIA,
        evidencia="comentario en un `.py`",
        detalle="el por que va en el docstring",
        linea=42,
    )

    assert con_linea.to_dict()["linea"] == 42


def test_el_veredicto_se_serializa_con_el_vocabulario_del_contrato() -> None:
    """Las claves y los valores son los de la rubrica -`veredicto`, `hallazgos`, `alta`-, no los
    nombres internos del dominio: al otro lado hay un programa que espera el contrato."""
    veredicto = Veredicto(dictamen=Dictamen.FALLA, hallazgos=(_SIN_LINEA,))

    assert veredicto.to_dict() == {
        "veredicto": "FALLA",
        "hallazgos": [
            {
                "regla": "cobertura-capa",
                "path": "src/x.py",
                "severidad": "alta",
                "evidencia": "el criterio de aceptacion no tiene test",
                "detalle": "falta el test que lo acredita",
            }
        ],
    }
