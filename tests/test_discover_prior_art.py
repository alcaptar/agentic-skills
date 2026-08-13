"""Que devuelve el descubrimiento de trabajo previo, y sobre todo que no decide nada.

El helper existe porque `slice-spec` troceaba sin mirar que habia ya. Lo que se mide aqui es la
mitad determinista -que encuentra lo que nombra el concepto, que acota lo que devuelve, y que sin
`gh` sigue contestando en vez de fallar-; el juicio de si un candidato cuenta es del agente y la
confirmacion es de la persona, asi que ninguna de las dos cosas se testea aqui porque no viven aqui.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discover_prior_art import MAXIMO_POR_CLASE, Hallazgo, Piezas, Precedentes, TipoHallazgo, _format

if TYPE_CHECKING:
    from pathlib import Path


def test_un_fichero_que_nombra_el_concepto_sale_como_pieza(tmp_path: Path) -> None:
    """La pregunta que contesta es "¿que hay ya?", asi que lo que se busca es donde vive el nombre."""
    (tmp_path / "stock_repository.py").write_text("class StockRepository:\n    pass\n", encoding="utf-8")
    (tmp_path / "otro.py").write_text("class Member:\n    pass\n", encoding="utf-8")

    hallazgos = Piezas.buscar(str(tmp_path), ["StockRepository"])

    assert [h.referencia for h in hallazgos] == ["stock_repository.py"]
    assert hallazgos[0].tipo is TipoHallazgo.PIEZA


def test_los_directorios_de_ruido_no_cuentan_como_piezas(tmp_path: Path) -> None:
    """Un acierto dentro de `node_modules` o de un `.venv` no es codigo del repo, es una dependencia."""
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("stock", encoding="utf-8")
    (tmp_path / "propio.py").write_text("stock", encoding="utf-8")

    assert [h.referencia for h in Piezas.buscar(str(tmp_path), ["stock"])] == ["propio.py"]


def test_las_piezas_salen_por_numero_de_menciones_y_acotadas(tmp_path: Path) -> None:
    """Acotar es el punto: veinte lineas que una persona confirma, no un informe que nadie lee."""
    for numero in range(MAXIMO_POR_CLASE + 4):
        (tmp_path / f"f{numero:02d}.py").write_text("stock " * (numero + 1), encoding="utf-8")

    hallazgos = Piezas.buscar(str(tmp_path), ["stock"])

    assert len(hallazgos) == MAXIMO_POR_CLASE
    assert hallazgos[0].referencia == f"f{MAXIMO_POR_CLASE + 3:02d}.py"


def test_un_gh_que_no_contesta_deja_los_precedentes_vacios_en_vez_de_romper() -> None:
    """Sin `gh` utilizable se sigue pudiendo trocear con las piezas: media respuesta acotada vale."""
    assert Precedentes._gh(["gh-que-no-existe", "pr", "list"]) == []


def test_sin_candidatos_se_dice_y_no_se_devuelve_una_lista_vacia_muda() -> None:
    """Una salida vacia se lee como "no busque"; esta se lee como "busque y no hay"."""
    assert "sin candidatos" in _format([])


def test_cada_candidato_sale_con_su_referencia_comprobable() -> None:
    """La vara del paso: un hallazgo es una ruta o un numero, para poder ir a mirarlo."""
    rendered = _format(
        [
            Hallazgo(tipo=TipoHallazgo.PRECEDENTE, referencia="#88", detalle="pull request mergeada: x"),
            Hallazgo(tipo=TipoHallazgo.PIEZA, referencia="src/stock.py", detalle="3 mencion(es)"),
        ]
    )

    assert "precedente: #88 - pull request mergeada: x" in rendered
    assert "pieza: src/stock.py - 3 mencion(es)" in rendered
