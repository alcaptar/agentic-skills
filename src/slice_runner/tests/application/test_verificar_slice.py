"""Tests del caso de uso: empaquetar el diff y llevarselo al juez, en ese orden.

Los dos colaboradores entran como dobles de sus puertos (`create_autospec(spec_set=True)`), asi que
lo que se prueba es la orquestacion y no git ni `claude`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import create_autospec

import pytest

from slice_runner.application.verificar_slice import VerificarSlice, VerificarSliceParams
from slice_runner.domain.diff import DiffDeSlice, DiffNoEmpaquetableError, EmpaquetadorDeDiff
from slice_runner.domain.veredicto import Dictamen, Veredicto
from slice_runner.domain.verificacion import Verificador

_DIFF = DiffDeSlice(slice_diff=Path("/tmp/b/slice.diff"), files=Path("/tmp/b/files.txt"), n_ficheros=3)

_PARAMS = VerificarSliceParams(
    repo="/repos/proyecto",
    base="master",
    instrucciones="Eres el verificador adversarial.",
)


def test_el_juez_recibe_el_bundle_que_acaba_de_empaquetarse() -> None:
    """El diff que juzga el juez es el que sale del empaquetador, no uno que el se calcule.

    Si la peticion se armara con otra cosa -por ejemplo el repo y la base, dejando que el juez
    resuelva el diff-, el juez se quedaria sin `Bash` para hacerlo y juzgaria a ciegas.
    """
    empaquetador = create_autospec(EmpaquetadorDeDiff, spec_set=True, instance=True)
    empaquetador.empaqueta.return_value = _DIFF
    verificador = create_autospec(Verificador, spec_set=True, instance=True)
    verificador.verifica.return_value = Veredicto(dictamen=Dictamen.PASA)

    VerificarSlice(empaquetador=empaquetador, verificador=verificador).execute(_PARAMS)

    empaquetador.empaqueta.assert_called_once_with(repo="/repos/proyecto", base="master")
    peticion = verificador.verifica.call_args.args[0]
    assert peticion.diff is _DIFF
    assert peticion.repo == "/repos/proyecto"
    assert peticion.instrucciones == "Eres el verificador adversarial."


def test_el_veredicto_del_juez_es_el_que_sale_del_caso_de_uso() -> None:
    """El caso de uso no reinterpreta el veredicto: quien decide es el juez."""
    empaquetador = create_autospec(EmpaquetadorDeDiff, spec_set=True, instance=True)
    empaquetador.empaqueta.return_value = _DIFF
    verificador = create_autospec(Verificador, spec_set=True, instance=True)
    esperado = Veredicto(dictamen=Dictamen.FALLA)
    verificador.verifica.return_value = esperado

    veredicto = VerificarSlice(empaquetador=empaquetador, verificador=verificador).execute(_PARAMS)

    assert veredicto is esperado


def test_sin_diff_que_empaquetar_no_se_invoca_al_juez() -> None:
    """Invocar al juez sobre un bundle que no existe le hace dar un PASA sobre la nada.

    Y ademas cuesta una invocacion entera del harness, que es el gasto que este orden evita.
    """
    empaquetador = create_autospec(EmpaquetadorDeDiff, spec_set=True, instance=True)
    empaquetador.empaqueta.side_effect = DiffNoEmpaquetableError("nada staged respecto a master")
    verificador = create_autospec(Verificador, spec_set=True, instance=True)

    with pytest.raises(DiffNoEmpaquetableError):
        VerificarSlice(empaquetador=empaquetador, verificador=verificador).execute(_PARAMS)

    verificador.verifica.assert_not_called()
