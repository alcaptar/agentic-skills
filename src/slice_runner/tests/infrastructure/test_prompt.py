"""Tests de la lectura del prompt del juez desde su fichero versionado."""

from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.prompt import RUTA_DEL_PROMPT_DEL_JUEZ, lee_prompt_del_agente

if TYPE_CHECKING:
    from pathlib import Path


def test_la_cabecera_de_configuracion_no_viaja_como_instruccion(tmp_path: Path) -> None:
    """El bloque `---` de arriba es config del registro de agentes viejo, no instrucciones.

    Si viajara, el juez recibiria como primera orden la lista de herramientas que quien las concede
    de verdad es `--tools`, y un `model: inherit` que en una llamada de linea de comandos no
    selecciona modelo alguno.
    """
    fichero = tmp_path / "juez.md"
    fichero.write_text(
        "---\nname: slice-verifier\ntools: Read, Grep, Glob\n---\n\n# Verificador\n\nBusca motivos para bloquear.\n",
        encoding="utf-8",
    )

    prompt = lee_prompt_del_agente(fichero)

    assert prompt.startswith("# Verificador")
    assert "tools:" not in prompt


def test_un_prompt_sin_cabecera_se_lee_tal_cual(tmp_path: Path) -> None:
    """Lo que no empieza con `---` no tiene cabecera que quitar, y una regla que se coma la
    primera seccion por parecerse a una es peor que no tener regla."""
    fichero = tmp_path / "juez.md"
    fichero.write_text("# Verificador\n\n---\n\nSegunda seccion.\n", encoding="utf-8")

    assert lee_prompt_del_agente(fichero) == "# Verificador\n\n---\n\nSegunda seccion."


def test_el_prompt_del_juez_del_repo_llega_con_su_rubrica() -> None:
    """La ruta por defecto apunta al prompt de verdad, y lo que llega es la rubrica.

    Es el test que se cae si el fichero se mueve o se renombra: sin el, el programa invocaria al
    juez con las instrucciones vacias, que es exactamente la vara vacia que el prompt prohibe.
    """
    prompt = lee_prompt_del_agente(RUTA_DEL_PROMPT_DEL_JUEZ)

    assert "Rubrica cerrada" in prompt
    assert not prompt.startswith("---")
