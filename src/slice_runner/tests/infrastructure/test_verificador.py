"""Tests del adaptador del juez contra payloads REALES de `claude -p --output-format json`.

Los dos ficheros de `payloads/` se grabaron llamando a la interfaz de verdad (una con la receta
completa de flags, otra sin acotar herramientas), y son la unica fuente de la forma del sobre del
harness: escribir a mano lo que se cree que devuelve es como se cuelan campos que no existen. Las
variantes que hacen falta para cubrir las ramas (un PASA, un veredicto incoherente, una clave que
no conocemos) se derivan del payload real **en el propio test**, con la mutacion a la vista, en vez
de guardarse como ficheros que aparentan estar grabados.

Ningun test de aqui sale a la red ni lanza `claude`: el proceso entra por el constructor.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.diff import DiffDeSlice
from slice_runner.domain.veredicto import Dictamen, Hallazgo, Severidad, VeredictoInvalidoError
from slice_runner.domain.verificacion import PeticionDeVerificacion
from slice_runner.infrastructure.proceso import Proceso, SalidaDeProceso
from slice_runner.infrastructure.verificador import (
    VerificadorClaude,
    argv_del_verificador,
    esquema_del_veredicto,
)
from slice_runner.tests.infrastructure.soporte import GRABADOS, ProcesoGrabado, con_veredicto, payload

if TYPE_CHECKING:
    from pathlib import Path


def peticion(tmp_path: Path) -> PeticionDeVerificacion:
    """Una peticion con el bundle ya materializado, como lo deja `diff-bundle`."""
    return PeticionDeVerificacion(
        repo="/repos/proyecto",
        instrucciones="Eres el verificador adversarial.",
        diff=DiffDeSlice(slice_diff=tmp_path / "slice.diff", files=tmp_path / "files.txt", n_ficheros=2),
    )


def test_las_herramientas_viajan_en_un_solo_argumento_con_comas() -> None:
    """`--tools` es variadico: con `--tools Read Grep Glob` se traga lo que venga detras.

    Medido contra la interfaz real: la invocacion muere con "Input must be provided either
    through stdin or as a prompt argument" porque el prompt posicional se lo come el flag. La
    forma con comas es la que deja el argumento cerrado en uno.
    """
    argv = argv_del_verificador()

    assert argv[argv.index("--tools") + 1] == "Read,Grep,Glob,Skill"


def test_el_juez_recibe_skill_porque_dos_items_de_su_rubrica_cargan_una() -> None:
    """La rubrica que si viaja le manda cargar `backend-best-practices` (item 1) y correr
    `test-desiderata` (item 8). Sin `Skill` son dos items de nueve que no puede ejecutar, y ni el
    argv ni el prompt se lo dicen: es la vara vacia que la propia rubrica declara causa raiz de
    desviaciones silenciosas.

    Concederla no toca la garantia estructural del juez -que no pueda correr controles-, porque
    `Skill` no trae `Bash` con ella; eso lo fija el test de abajo.
    """
    argv = argv_del_verificador()

    assert "Skill" in argv[argv.index("--tools") + 1].split(",")


def test_el_juez_no_recibe_herramientas_de_escritura_ni_de_ejecucion() -> None:
    """El que implementa no verifica, y aqui eso esta en el argv: sin `Bash`, `Write` ni `Edit`.

    Se comprueba sobre la lista de herramientas concedidas y no sobre el argv entero, para que
    anadir una herramienta de escritura a la receta no pueda pasar por ser un flag mas.
    """
    argv = argv_del_verificador()

    concedidas = argv[argv.index("--tools") + 1].split(",")
    assert set(concedidas).isdisjoint({"Bash", "Write", "Edit"})


def test_el_argv_acota_los_servidores_mcp_y_declara_el_esquema_del_veredicto() -> None:
    """Sin `--strict-mcp-config` el juez hereda los servidores MCP de la maquina -herramientas de
    red incluidas- y sin `--json-schema` el veredicto vuelve como prosa que hay que adivinar.
    """
    argv = argv_del_verificador()

    assert "--strict-mcp-config" in argv
    esquema = json.loads(argv[argv.index("--json-schema") + 1])
    assert esquema["properties"]["veredicto"]["enum"] == ["PASA", "FALLA"]


def test_el_argv_pide_el_sobre_json_del_harness() -> None:
    """Sin `--output-format json` no hay `structured_output` que leer, solo texto."""
    argv = argv_del_verificador()

    assert argv[argv.index("--output-format") + 1] == "json"


_FLAGS_CON_VALOR = ("--tools", "--json-schema", "--output-format")
"""Los flags de la receta que consumen el argumento siguiente. Escritos a mano: es la lista
contra la que se decide que es posicional, y derivarla del argv la volveria tautologica."""


def _posicionales(argv: list[str]) -> list[str]:
    """Los argumentos que no son un flag ni el valor de un flag, ejecutable aparte."""
    resto = argv[1:]
    posicionales: list[str] = []
    salta = False
    for arg in resto:
        if salta:
            salta = False
        elif arg.startswith("-"):
            salta = arg in _FLAGS_CON_VALOR
        else:
            posicionales.append(arg)
    return posicionales


def test_el_argv_no_lleva_ningun_argumento_posicional() -> None:
    """El prompt viaja por entrada estandar, siempre.

    Lo unico posicional legitimo es el ejecutable, porque los flags variadicos se tragan lo que
    venga detras. Si alguien mueve el prompt al argv, aparece aqui como posicional.
    """
    argv = argv_del_verificador()

    assert argv[0] == "claude"
    assert _posicionales(argv) == []


@pytest.mark.parametrize("grabado", GRABADOS)
def test_el_sobre_de_las_dos_llamadas_reales_se_lee_entero(grabado: str, tmp_path: Path) -> None:
    """Las dos invocaciones grabadas devolvieron cuatro hallazgos y un FALLA cada una.

    Es el test que se cae si el adaptador deja de leer `structured_output` -donde `--json-schema`
    deja el objeto ya parseado- y se pone a parsear `result`, que trae lo mismo como cadena: con
    `result` habria que reimplementar el harness, y con cualquiera de los dos campos mal elegidos
    el veredicto se queda vacio.
    """
    proceso = ProcesoGrabado(payload(grabado))

    veredicto = VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))

    assert veredicto.dictamen is Dictamen.FALLA
    assert len(veredicto.hallazgos) == 4


def test_el_hallazgo_llega_tipado_hasta_la_severidad(tmp_path: Path) -> None:
    """La severidad entra como cadena y sale como miembro de la enumeracion del dominio.

    Sin la conversion, un `"severidad": "critical"` seguiria viajando como cadena hasta quien
    cuenta las altas para decidir el merge.
    """
    proceso = ProcesoGrabado(payload("receta-completa"))

    primero = VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path)).hallazgos[0]

    assert primero.severidad is Severidad.ALTA
    assert primero.regla == "convenciones"
    assert primero.path == "mod.py"
    assert primero.linea == 11


def test_un_veredicto_sin_hallazgos_pasa(tmp_path: Path) -> None:
    """El camino verde: PASA con la lista de hallazgos vacia, que es lo que el contrato exige."""
    proceso = ProcesoGrabado(con_veredicto({"veredicto": "PASA", "hallazgos": []}))

    veredicto = VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))

    assert veredicto.dictamen is Dictamen.PASA
    assert veredicto.hallazgos == ()


def test_el_prompt_viaja_por_entrada_estandar_con_las_rutas_del_bundle(tmp_path: Path) -> None:
    """El juez no tiene `Bash`: el diff le llega en disco, por ruta, dentro del prompt.

    Y el prompt entra por entrada estandar: si alguien lo mueve al argv, los flags variadicos se lo
    tragan y la llamada muere pidiendo un prompt que si estaba.
    """
    proceso = ProcesoGrabado(payload("receta-completa"))
    pedido = peticion(tmp_path)

    VerificadorClaude(proceso=proceso).verifica(pedido)

    assert pedido.instrucciones in proceso.entrada
    assert str(pedido.diff.slice_diff) in proceso.entrada
    assert str(pedido.diff.files) in proceso.entrada
    assert pedido.repo in proceso.entrada
    assert proceso.entrada not in proceso.argv


def test_un_pasa_con_un_hallazgo_alta_se_rechaza(tmp_path: Path) -> None:
    """El esquema garantiza la forma, no la coherencia: este veredicto lo cumple entero.

    Es el modo de fallo que `--json-schema` no puede cazar y por el que `verify-verdict` sigue
    haciendo falta -una `alta` implica FALLA-, asi que el adaptador lo pasa por el.
    """
    contradictorio: dict[str, object] = {
        "veredicto": "PASA",
        "hallazgos": [
            {
                "regla": "boundaries",
                "path": "src/x.py",
                "severidad": "alta",
                "evidencia": "requests en el dominio",
                "detalle": "la I/O va detras de un puerto",
            }
        ],
    }
    proceso = ProcesoGrabado(con_veredicto(contradictorio))

    with pytest.raises(VeredictoInvalidoError, match="alta"):
        VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))


def test_una_clave_que_no_conocemos_en_el_sobre_se_rechaza(tmp_path: Path) -> None:
    """Fail-closed sobre lo que llega de fuera: el sobre se lee entero o no se lee.

    Un campo nuevo del harness que se ignore en silencio es una decision de merge tomada sobre un
    payload que ya no es el que se midio.
    """
    proceso = ProcesoGrabado(dict(payload("receta-completa")) | {"campo_nuevo_del_harness": 1})

    with pytest.raises(VeredictoInvalidoError, match="campo_nuevo_del_harness"):
        VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))


def test_un_tipo_equivocado_en_el_sobre_se_rechaza(tmp_path: Path) -> None:
    """`is_error` como cadena es verdadero para toda condicion, asi que un error del harness
    pasaria por llamada correcta."""
    proceso = ProcesoGrabado(dict(payload("receta-completa")) | {"is_error": "no"})

    with pytest.raises(VeredictoInvalidoError, match="is_error"):
        VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))


def test_un_sobre_sin_veredicto_estructurado_se_rechaza(tmp_path: Path) -> None:
    """Sin `structured_output` no hay veredicto, y el texto de `result` no es su sustituto."""
    sin_estructura = {k: v for k, v in payload("receta-completa").items() if k != "structured_output"}
    proceso = ProcesoGrabado(sin_estructura)

    with pytest.raises(VeredictoInvalidoError, match="structured_output"):
        VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))


def test_una_llamada_que_el_harness_declara_fallida_se_rechaza(tmp_path: Path) -> None:
    """`is_error` en el sobre es el harness diciendo que lo que devuelve no es un resultado."""
    proceso = ProcesoGrabado(dict(payload("receta-completa")) | {"is_error": True})

    with pytest.raises(VeredictoInvalidoError, match="is_error"):
        VerificadorClaude(proceso=proceso).verifica(peticion(tmp_path))


def test_un_proceso_que_no_devuelve_json_se_rechaza(tmp_path: Path) -> None:
    """`claude` que muere por un flag mal formado escribe en stderr y deja stdout vacio."""

    class ProcesoRoto(Proceso):
        def corre(self, argv: list[str], *, entrada: str) -> SalidaDeProceso:
            return SalidaDeProceso(codigo=1, stdout="", stderr="error: unknown option '--tools'")

    with pytest.raises(VeredictoInvalidoError, match="unknown option"):
        VerificadorClaude(proceso=ProcesoRoto()).verifica(peticion(tmp_path))


def _items_del_hallazgo() -> dict[str, object]:
    """El subesquema de un hallazgo, navegado con asserts: el esquema es JSON suelto."""
    nodo: object = esquema_del_veredicto()
    for clave in ("properties", "hallazgos", "items"):
        assert isinstance(nodo, dict)
        nodo = nodo[clave]
    assert isinstance(nodo, dict)
    return nodo


def test_el_esquema_declara_todos_los_campos_del_hallazgo_del_dominio() -> None:
    """El esquema cierra el objeto (`additionalProperties: false`), asi que un campo del dominio
    que no aparezca aqui es un campo que el juez no puede emitir aunque el dominio lo exija.

    Las claves del esquema se escriben junto a su tipo JSON y no se derivan del dataclass, que es
    por lo que las dos listas pueden desalinearse y este test hace falta.
    """
    propiedades = _items_del_hallazgo()["properties"]

    assert isinstance(propiedades, dict)
    assert set(propiedades) == {f.name for f in fields(Hallazgo)}


def test_el_esquema_exige_todo_menos_la_linea() -> None:
    """`linea` es el unico opcional: hay hallazgos cuya evidencia es una pieza que falta y no vive
    en ninguna linea del diff, y exigirla obligaria al juez a inventarse una.

    Al reves es lo que importa: darle un valor por defecto a `evidencia` la sacaria de
    `required`, y el juez podria bloquear sin citar nada -que es justo lo que la rubrica prohibe-.
    """
    obligatorios = _items_del_hallazgo()["required"]

    assert isinstance(obligatorios, list)
    assert set(obligatorios) == {f.name for f in fields(Hallazgo)} - {"linea"}
