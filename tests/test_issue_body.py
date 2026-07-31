"""Tests de la logica pura del cuerpo del issue (issue_body.py).

Cubren tres superficies. El parseo y la reescritura del cuerpo, que son puras. Las secciones por
repo (`## Fuentes de convencion` y `## Controles`), que antes deducia `slice-runner` leyendo el
Makefile en cada slice y ahora declara `slice-spec` una vez, confirma una persona y viven en el
issue. Y la capa de CLI, que existe porque sin ella el agente escribia el read-modify-write a mano
en cada transicion -en una sola sesion se escribio seis veces-, y cada copia es una ocasion de
equivocarse en silencio: si `gh issue view` devuelve vacio, un `gh issue edit` con ese cuerpo
**borra la spec entera del issue**. `gh` se inyecta, asi que estos tests no tocan la red.
"""

from __future__ import annotations

import json
import subprocess

import pytest

import issue_body
from issue_body import (
    Control,
    Fuente,
    Slice,
    controles_para,
    fuentes_para,
    normaliza_motivo,
    parse_body,
    parse_controles,
    parse_fuentes,
    parse_intencion,
    render_controles_section,
    render_fuentes_section,
    render_slice_line,
    set_controles,
    set_fuentes,
    set_slice_estado,
    tiene_seccion_controles,
    tiene_seccion_fuentes,
)

_BODY = """\
# Feature X

Intro de la feature.

## Slices
- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [ ] slice-02 (ajustar-stock): Caso de uso AjustarStock [esperando-merge] PR #12
      AC: emite evento StockAjustado
      AC: no toca infra directamente
- [ ] slice-03 (refactor: extraer-repo): Extraer repo [en-curso]
- [ ] slice-04 (backfill): Backfill [bloqueada: ci-roja] PR #13
- [ ] slice-05 (cleanup): Retirar flag [pendiente]
- [ ] no es una slice, ignorar
"""
"""Cuerpo de referencia. Usa la etiqueta vieja `AC:` a proposito: es la cobertura de los issues
abiertos antes del rename a `ACEPTACION:`.
"""


def test_parse_body_ids_en_orden() -> None:
    slices = parse_body(_BODY)
    assert [s.slice_id for s in slices] == [
        "slice-01",
        "slice-02",
        "slice-03",
        "slice-04",
        "slice-05",
    ]


def test_parse_body_checkbox_x_es_mergeada() -> None:
    s01 = parse_body(_BODY)[0]
    assert s01.estado == "mergeada"
    assert s01.pr == 11
    assert s01.name == "cantidad-vo"
    assert s01.type == "feat"


def test_parse_body_estados_intermedios() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY)}
    assert by_id["slice-02"].estado == "esperando-merge"
    assert by_id["slice-02"].pr == 12
    assert by_id["slice-03"].estado == "en-curso"
    assert by_id["slice-03"].type == "refactor"
    assert by_id["slice-03"].name == "extraer-repo"
    assert by_id["slice-04"].estado == "bloqueada"
    assert by_id["slice-04"].motivo == "ci-roja"
    assert by_id["slice-05"].estado == "pendiente"


def test_parse_body_recoge_los_criterios_de_aceptacion() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY)}
    assert by_id["slice-01"].aceptacion == ["rechaza negativos; tests en test/domain/test_cantidad.py"]
    assert by_id["slice-02"].aceptacion == [
        "emite evento StockAjustado",
        "no toca infra directamente",
    ]
    assert by_id["slice-03"].aceptacion == []


def test_parse_body_acepta_la_etiqueta_vieja_ac() -> None:
    """`AC:` se renombro a `ACEPTACION:`, pero hay issues abiertos escritos con la vieja: dejar de parsearla
    los dejaria sin criterios y sin control de verificacion.
    """
    body = "## Slices\n- [ ] slice-01 (x): T [pendiente]\n      AC: rechaza negativos\n"
    assert parse_body(body)[0].aceptacion == ["rechaza negativos"]


def test_parse_body_acepta_aceptacion_con_tilde() -> None:
    body = "## Slices\n- [ ] slice-01 (x): T [pendiente]\n      ACEPTACIÓN: rechaza negativos\n"
    assert parse_body(body)[0].aceptacion == ["rechaza negativos"]


def test_parse_body_ignora_lineas_no_slice() -> None:
    """ "- [ ] no es una slice" no debe aparecer como slice."""
    assert all(s.slice_id.startswith("slice-") for s in parse_body(_BODY))


def test_set_estado_marca_mergeada_como_checkbox() -> None:
    nuevo = set_slice_estado(_BODY, "slice-02", "mergeada")
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-02"].estado == "mergeada"
    assert "- [x] slice-02 (ajustar-stock): Caso de uso AjustarStock [mergeada] PR #12" in nuevo
    assert by_id["slice-02"].pr == 12


def test_set_estado_preserva_el_resto_del_cuerpo() -> None:
    nuevo = set_slice_estado(_BODY, "slice-03", "esperando-merge", pr=99)
    assert "- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11" in nuevo
    assert "      AC: no toca infra directamente" in nuevo
    assert "Intro de la feature." in nuevo
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-03"].estado == "esperando-merge"
    assert by_id["slice-03"].pr == 99


def test_set_estado_con_motivo() -> None:
    nuevo = set_slice_estado(_BODY, "slice-05", "bloqueada", motivo="verify")
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-05"].estado == "bloqueada"
    assert by_id["slice-05"].motivo == "verify"


def test_set_estado_preserva_trailing_newline() -> None:
    assert set_slice_estado(_BODY, "slice-05", "en-curso").endswith("\n")
    sin_nl = _BODY.rstrip("\n")
    assert not set_slice_estado(sin_nl, "slice-05", "en-curso").endswith("\n")


def test_set_estado_slice_inexistente() -> None:
    with pytest.raises(KeyError):
        set_slice_estado(_BODY, "slice-99", "en-curso")


def test_set_estado_estado_invalido() -> None:
    with pytest.raises(ValueError, match="estado no valido"):
        set_slice_estado(_BODY, "slice-01", "inventado")


def test_roundtrip_render_parse() -> None:
    sl = Slice(
        slice_id="slice-07",
        name="mi-slice",
        type="fix",
        title="Arreglar cosa",
        estado="esperando-merge",
        pr=42,
    )
    line = render_slice_line(sl)
    parsed = parse_body(f"## Slices\n{line}\n")[0]
    assert parsed.slice_id == "slice-07"
    assert parsed.name == "mi-slice"
    assert parsed.type == "fix"
    assert parsed.title == "Arreglar cosa"
    assert parsed.estado == "esperando-merge"
    assert parsed.pr == 42


def test_estados_expuestos() -> None:
    assert "esperando-merge" in tuple(issue_body.Estado)
    assert "mergeada" in tuple(issue_body.Estado)


_BODY_CON_FUENTES = """\
# Feature X

Intro de la feature.

## Fuentes de convencion
- doc: .claude/CLAUDE.md
- doc: .claude/rules/conventions/
- skill: .claude/skills/duplicate-action

## Slices
- [ ] slice-01 (vo): Crear VO [pendiente]
      ACEPTACION: rechaza negativos
"""

_BODY_SIN_FUENTES = """\
# Feature Y

## Slices
- [ ] slice-01 (vo): Crear VO [pendiente]
"""


def test_parse_fuentes_extrae_docs_y_skills_en_orden() -> None:
    fuentes = parse_fuentes(_BODY_CON_FUENTES)
    assert fuentes == [
        Fuente(tipo="doc", ruta=".claude/CLAUDE.md"),
        Fuente(tipo="doc", ruta=".claude/rules/conventions/"),
        Fuente(tipo="skill", ruta=".claude/skills/duplicate-action"),
    ]


def test_parse_fuentes_seccion_ausente_lista_vacia() -> None:
    assert parse_fuentes(_BODY_SIN_FUENTES) == []


def test_parse_fuentes_se_detiene_en_la_siguiente_seccion() -> None:
    """No debe tragarse la linea de slice de '## Slices' como fuente."""
    fuentes = parse_fuentes(_BODY_CON_FUENTES)
    assert all(f.tipo in ("doc", "skill") for f in fuentes)
    assert len(fuentes) == 3


def test_parse_fuentes_tolera_tilde_y_mayusculas_en_heading() -> None:
    body = "## Fuentes de Convención\n- skill: .claude/skills/tdd\n"
    assert parse_fuentes(body) == [Fuente(tipo="skill", ruta=".claude/skills/tdd")]


def test_tiene_seccion_fuentes_distingue_ausente_de_presente() -> None:
    assert tiene_seccion_fuentes(_BODY_CON_FUENTES) is True
    assert tiene_seccion_fuentes(_BODY_SIN_FUENTES) is False
    assert tiene_seccion_fuentes("## Fuentes de convencion\n") is True


def test_render_fuentes_section_formato_canonico() -> None:
    section = render_fuentes_section(
        [Fuente(tipo="doc", ruta=".claude/CLAUDE.md"), Fuente(tipo="skill", ruta=".claude/skills/pr")]
    )
    assert section == ("## Fuentes de convencion\n- doc: .claude/CLAUDE.md\n- skill: .claude/skills/pr")


def test_render_fuentes_tipo_invalido() -> None:
    with pytest.raises(ValueError, match="tipo de fuente no valido"):
        render_fuentes_section([Fuente(tipo="regla", ruta=".claude/CLAUDE.md")])


def test_set_fuentes_anade_seccion_cuando_no_existe() -> None:
    nuevo = set_fuentes(_BODY_SIN_FUENTES, [Fuente(tipo="doc", ruta=".claude/CLAUDE.md")])
    assert tiene_seccion_fuentes(nuevo)
    assert parse_fuentes(nuevo) == [Fuente(tipo="doc", ruta=".claude/CLAUDE.md")]
    assert [s.slice_id for s in parse_body(nuevo)] == ["slice-01"]


def test_set_fuentes_reemplaza_seccion_existente_preservando_el_resto() -> None:
    """El upsert reemplaza la seccion entera y no toca nada de alrededor.

    Ni la intro de antes, ni las slices y sus criterios de despues: es lo que permite reescribir
    las fuentes de un issue vivo sin perder el estado del run.
    """
    nuevo = set_fuentes(_BODY_CON_FUENTES, [Fuente(tipo="skill", ruta=".claude/skills/tdd")])
    assert parse_fuentes(nuevo) == [Fuente(tipo="skill", ruta=".claude/skills/tdd")]
    assert "duplicate-action" not in nuevo
    assert "Intro de la feature." in nuevo
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-01"].aceptacion == ["rechaza negativos"]


def test_set_fuentes_preserva_trailing_newline() -> None:
    assert set_fuentes(_BODY_SIN_FUENTES, [Fuente(tipo="doc", ruta="x")]).endswith("\n")
    sin_nl = _BODY_SIN_FUENTES.rstrip("\n")
    assert not set_fuentes(sin_nl, [Fuente(tipo="doc", ruta="x")]).endswith("\n")


def test_roundtrip_render_parse_fuentes() -> None:
    fuentes = [Fuente(tipo="doc", ruta="docs/conventions/"), Fuente(tipo="skill", ruta=".claude/skills/x")]
    parsed = parse_fuentes(render_fuentes_section(fuentes) + "\n")
    assert parsed == fuentes


_GKE = "mercadona/mercadona.online.gke"

_BODY_CON_SENAL = """\
# Feature Z

## Fuentes de convencion
- doc: CLAUDE.md

### mercadona/mercadona.online.gke
- doc: templates/CLAUDE.md
- doc: tests/prometheus/README.md

## Slices
- [ ] slice-01 (ajustar-stock): Caso de uso AjustarStock [pendiente]
      ACEPTACION: incrementa stock_ajustado_total{motivo}
      SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
- [ ] slice-02 (alerta-ajuste): Alerta de ajustes fallidos [pendiente]
      REPO: mercadona/mercadona.online.gke
      ACEPTACION: promtool test dispara ShopAjusteFallido con 3 fallos
      SENAL: prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory
- [ ] slice-03 (extraer-repo): Extraer repositorio [pendiente]
      ACEPTACION: sin cambio de comportamiento
      SENAL: exenta - refactor puro
"""


def test_parse_body_recoge_senal() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}
    assert by_id["slice-01"].senal == ["prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical"]
    assert by_id["slice-03"].senal == ["exenta - refactor puro"]


def test_parse_body_senal_ausente_es_lista_vacia() -> None:
    """Una spec legacy sin SENAL no revienta: slice-runner avisa, no bloquea."""
    assert parse_body(_BODY)[0].senal == []


def test_parse_body_acepta_senal_con_tilde() -> None:
    body = "## Slices\n- [ ] slice-01 (x): T [pendiente]\n      SEÑAL: prometheus foo > 0\n"
    assert parse_body(body)[0].senal == ["prometheus foo > 0"]


def test_parse_body_senal_no_se_confunde_con_ac() -> None:
    s01 = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}["slice-01"]
    assert s01.aceptacion == ["incrementa stock_ajustado_total{motivo}"]


def test_parse_body_recoge_repo_destino() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}
    assert by_id["slice-02"].repo == _GKE
    assert by_id["slice-01"].repo is None


def test_set_estado_preserva_senal_y_repo() -> None:
    nuevo = set_slice_estado(_BODY_CON_SENAL, "slice-02", "en-curso", pr=7)
    s02 = {s.slice_id: s for s in parse_body(nuevo)}["slice-02"]
    assert s02.estado == "en-curso"
    assert s02.pr == 7
    assert s02.repo == _GKE
    assert s02.senal == ['prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory']


def test_parse_fuentes_atribuye_subseccion_al_repo_destino() -> None:
    assert parse_fuentes(_BODY_CON_SENAL) == [
        Fuente(tipo="doc", ruta="CLAUDE.md"),
        Fuente(tipo="doc", ruta="templates/CLAUDE.md", repo=_GKE),
        Fuente(tipo="doc", ruta="tests/prometheus/README.md", repo=_GKE),
    ]


def test_fuentes_para_filtra_por_repo() -> None:
    fuentes = parse_fuentes(_BODY_CON_SENAL)
    assert fuentes_para(fuentes) == [Fuente(tipo="doc", ruta="CLAUDE.md")]
    assert [f.ruta for f in fuentes_para(fuentes, _GKE)] == [
        "templates/CLAUDE.md",
        "tests/prometheus/README.md",
    ]


def test_fuentes_para_repo_sin_vara_declarada() -> None:
    """No inventa una vara heredada: si el repo destino no declara fuentes, esta vacio y slice-runner para en
    el paso 1 en vez de medir con la del repo de la app.
    """
    assert fuentes_para(parse_fuentes(_BODY_CON_SENAL), "mercadona/otro") == []


def test_render_fuentes_agrupa_por_repo_en_subsecciones() -> None:
    section = render_fuentes_section(
        [
            Fuente(tipo="doc", ruta="CLAUDE.md"),
            Fuente(tipo="doc", ruta="templates/CLAUDE.md", repo=_GKE),
            Fuente(tipo="skill", ruta=".claude/skills/x"),
        ]
    )
    assert section == (
        "## Fuentes de convencion\n"
        "- doc: CLAUDE.md\n"
        "- skill: .claude/skills/x\n"
        "\n"
        f"### {_GKE}\n"
        "- doc: templates/CLAUDE.md"
    )


def test_roundtrip_render_parse_fuentes_por_repo() -> None:
    fuentes = [
        Fuente(tipo="doc", ruta="CLAUDE.md"),
        Fuente(tipo="doc", ruta="templates/CLAUDE.md", repo=_GKE),
        Fuente(tipo="skill", ruta="settings/README.md", repo="mercadona/mo.sre.grafana-configs"),
    ]
    assert parse_fuentes(render_fuentes_section(fuentes) + "\n") == fuentes


def test_set_fuentes_reemplaza_tambien_las_subsecciones_de_repo() -> None:
    nuevo = set_fuentes(_BODY_CON_SENAL, [Fuente(tipo="doc", ruta="CLAUDE.md")])
    assert parse_fuentes(nuevo) == [Fuente(tipo="doc", ruta="CLAUDE.md")]
    assert "tests/prometheus/README.md" not in nuevo
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-03"].senal == ["exenta - refactor puro"]


_BODY_CON_INTENCION = """\
# Feature W

## Intencion
Hoy el ajuste de stock se hace a mano en la consola y nadie sabe quien lo hizo.
Cuando el recuento no cuadra no hay forma de reconstruir que paso.

## Fuentes de convencion
- doc: CLAUDE.md

## Slices
- [ ] slice-01 (ajustar-stock): Caso de uso AjustarStock [pendiente]
      INTENCION: hoy el ajuste se hace a mano y no queda rastro de quien lo hizo
      ACEPTACION: emite evento StockAjustado
      SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
- [ ] slice-02 (extraer-repo): Extraer repositorio [pendiente]
      INTENCION: hoy el caso de uso habla con la base de datos y no se puede testear sin ella
      ACEPTACION: sin cambio de comportamiento
"""


def test_parse_body_recoge_intencion_de_la_slice() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY_CON_INTENCION)}
    assert by_id["slice-01"].intencion == ["hoy el ajuste se hace a mano y no queda rastro de quien lo hizo"]
    assert by_id["slice-02"].intencion == [
        "hoy el caso de uso habla con la base de datos y no se puede testear sin ella"
    ]


def test_parse_body_intencion_ausente_es_lista_vacia() -> None:
    """Un issue anterior a este mecanismo no revienta: la PR declara que la infirio."""
    assert parse_body(_BODY)[0].intencion == []


def test_parse_body_acepta_intencion_con_tilde() -> None:
    body = "## Slices\n- [ ] slice-01 (x): T [pendiente]\n      INTENCIÓN: hoy falla en silencio\n"
    assert parse_body(body)[0].intencion == ["hoy falla en silencio"]


def test_parse_body_intencion_no_se_confunde_con_ac_ni_senal() -> None:
    s01 = {s.slice_id: s for s in parse_body(_BODY_CON_INTENCION)}["slice-01"]
    assert s01.aceptacion == ["emite evento StockAjustado"]
    assert s01.senal == ["prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical"]


def test_parse_intencion_devuelve_el_texto_de_la_seccion() -> None:
    assert parse_intencion(_BODY_CON_INTENCION) == (
        "Hoy el ajuste de stock se hace a mano en la consola y nadie sabe quien lo hizo.\n"
        "Cuando el recuento no cuadra no hay forma de reconstruir que paso."
    )


def test_parse_intencion_seccion_ausente_es_none() -> None:
    """None y "" son casos distintos a proposito: ambos degradan la PR, pero solo el script decide cual es,
    no el criterio del agente.
    """
    assert parse_intencion(_BODY) is None


def test_parse_intencion_seccion_vacia_es_cadena_vacia() -> None:
    assert parse_intencion("# F\n\n## Intencion\n\n## Slices\n") == ""


def test_parse_intencion_no_arrastra_la_seccion_siguiente() -> None:
    texto = parse_intencion(_BODY_CON_INTENCION)
    assert texto is not None
    assert "Fuentes de convencion" not in texto
    assert "slice-01" not in texto


def test_set_estado_preserva_la_intencion_de_la_slice() -> None:
    nuevo = set_slice_estado(_BODY_CON_INTENCION, "slice-01", "en-curso", pr=7)
    s01 = {s.slice_id: s for s in parse_body(nuevo)}["slice-01"]
    assert s01.estado == "en-curso"
    assert s01.intencion == ["hoy el ajuste se hace a mano y no queda rastro de quien lo hizo"]
    assert parse_intencion(nuevo) is not None


def test_set_fuentes_preserva_la_seccion_de_intencion() -> None:
    nuevo = set_fuentes(_BODY_CON_INTENCION, [Fuente(tipo="doc", ruta="otro.md")])
    assert parse_intencion(nuevo) == parse_intencion(_BODY_CON_INTENCION)


_BODY_CON_CONTROLES = """\
# Feature X

## Controles
- lint: make linting
- types: make check-types
- tests: make test ARGS=-x

### mercadona/mercadona.online.gke
- schema: make test_prometheus_rules

## Slices
- [ ] slice-01 (vo): Crear VO [pendiente]
"""

_BODY_CON_EXENCION = """\
# Feature X

## Controles
- lint: make linting

### mercadona/grafana
- ninguno: la CI solo publica en master, no valida en PR

## Slices
- [ ] slice-01 (panel): Panel [pendiente]
"""


def test_parse_controles_extrae_pares_en_orden() -> None:
    assert parse_controles(_BODY_CON_CONTROLES) == [
        Control(nombre="lint", comando="make linting"),
        Control(nombre="types", comando="make check-types"),
        Control(nombre="tests", comando="make test ARGS=-x"),
        Control(nombre="schema", comando="make test_prometheus_rules", repo="mercadona/mercadona.online.gke"),
    ]


def test_parse_controles_seccion_ausente_lista_vacia() -> None:
    assert parse_controles(_BODY) == []


def test_tiene_seccion_controles_distingue_ausente_de_vacia() -> None:
    """Ausente = el issue nunca los declaro -> slice-runner para. Vacia = declarada pero sin lineas, que es
    un issue mal formado y NO lo mismo que no tener controles.
    """
    assert tiene_seccion_controles(_BODY_CON_CONTROLES) is True
    assert tiene_seccion_controles(_BODY) is False
    assert tiene_seccion_controles("## Controles\n") is True


def test_parse_controles_se_detiene_en_la_siguiente_seccion() -> None:
    """La linea de slice `- [ ] slice-01 (vo): ...` esta bajo `## Slices`: no es un control."""
    assert all(c.nombre != "slice-01" for c in parse_controles(_BODY_CON_CONTROLES))


def test_controles_para_filtra_por_repo_destino() -> None:
    controles = parse_controles(_BODY_CON_CONTROLES)
    assert [c.nombre for c in controles_para(controles)] == ["lint", "types", "tests"]
    assert [c.nombre for c in controles_para(controles, "mercadona/mercadona.online.gke")] == ["schema"]


def test_controles_para_repo_sin_subseccion_no_hereda_los_del_issue() -> None:
    """Heredar los del repo de la app mediria una alerta con `make test` de otro repo: es la misma desviacion
    silenciosa que heredar su vara de medir.
    """
    assert controles_para(parse_controles(_BODY_CON_CONTROLES), "mercadona/otro") == []


def test_exencion_ninguno_se_lee_como_exenta_con_motivo() -> None:
    exencion = controles_para(parse_controles(_BODY_CON_EXENCION), "mercadona/grafana")[0]
    assert exencion.exento is True
    assert exencion.motivo == "la CI solo publica en master, no valida en PR"


def test_un_control_de_verdad_no_es_exento() -> None:
    control = controles_para(parse_controles(_BODY_CON_EXENCION))[0]
    assert control.exento is False
    assert control.motivo == ""


def test_render_controles_section_formato_canonico() -> None:
    section = render_controles_section(
        [
            Control(nombre="tests", comando="make test"),
            Control(nombre="schema", comando="make validate", repo="org/manifiestos"),
        ]
    )
    assert section == ("## Controles\n- tests: make test\n\n### org/manifiestos\n- schema: make validate")


def test_render_controles_rechaza_mezclar_exencion_con_controles() -> None:
    """ "no hay controles" y "hay estos" no pueden ser ciertas a la vez: dejarlo pasar haria que la ejecucion
    dependiera de cual se leyera primero.
    """
    with pytest.raises(ValueError, match="no admite otros controles"):
        render_controles_section(
            [Control(nombre="ninguno", comando="no hay CI"), Control(nombre="tests", comando="make test")]
        )


def test_render_controles_permite_exencion_en_un_repo_y_controles_en_otro() -> None:
    section = render_controles_section(
        [
            Control(nombre="tests", comando="make test"),
            Control(nombre="ninguno", comando="no valida en PR", repo="org/grafana"),
        ]
    )
    assert "- ninguno: no valida en PR" in section


def test_set_controles_anade_seccion_cuando_no_existe() -> None:
    nuevo = set_controles(_BODY, [Control(nombre="tests", comando="make test")])
    assert tiene_seccion_controles(nuevo)
    assert parse_controles(nuevo) == [Control(nombre="tests", comando="make test")]


def test_set_controles_reemplaza_preservando_el_resto_del_cuerpo() -> None:
    nuevo = set_controles(_BODY_CON_CONTROLES, [Control(nombre="tests", comando="make test-unit")])
    assert parse_controles(nuevo) == [Control(nombre="tests", comando="make test-unit")]
    assert [s.slice_id for s in parse_body(nuevo)] == ["slice-01"]


def test_set_controles_no_toca_las_fuentes_de_convencion() -> None:
    nuevo = set_controles(_BODY_CON_FUENTES, [Control(nombre="tests", comando="make test")])
    assert parse_fuentes(nuevo) == parse_fuentes(_BODY_CON_FUENTES)


def test_roundtrip_render_parse_controles() -> None:
    controles = [
        Control(nombre="lint", comando="make linting"),
        Control(nombre="schema", comando="make v", repo="org/repo"),
    ]
    assert parse_controles(render_controles_section(controles) + "\n") == controles


def test_normaliza_motivo_traduce_la_forma_vieja() -> None:
    assert normaliza_motivo("puertas") == "controles"
    assert normaliza_motivo("ci-roja") == "ci-roja"


def test_parse_body_normaliza_bloqueada_puertas_de_un_issue_viejo() -> None:
    """Hay issues abiertos con este marcador escrito: renombrar no puede dejarlos ilegibles."""
    body = "## Slices\n- [ ] slice-01 (vo): Crear VO [bloqueada: puertas]\n"
    sl = parse_body(body)[0]
    assert (sl.estado, sl.motivo) == ("bloqueada", "controles")


def _fake_gh(monkeypatch: pytest.MonkeyPatch, view_out: str, view_rc: int = 0) -> list[list[str]]:
    """Sustituye `subprocess.run` y devuelve la lista de argv invocados."""
    llamadas: list[list[str]] = []

    def run(argv: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        llamadas.append(argv)
        if "view" in argv:
            return subprocess.CompletedProcess(argv, view_rc, view_out, "boom" if view_rc else "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("issue_body.subprocess.run", run)
    return llamadas


def test_cli_show_emite_slice_fuentes_controles_y_derivados(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """La siguiente sin cerrar, no la primera: slice-01 esta mergeada en el fixture."""
    _fake_gh(monkeypatch, _BODY)
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["slice"]["slice_id"] == "slice-02"
    assert data["slice"]["rama"] == "slice/02-ajustar-stock"
    assert data["slice"]["scope"] == "feat(ajustar-stock)"
    assert data["slice"]["aceptacion"]


def test_cli_show_de_una_slice_concreta(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _fake_gh(monkeypatch, _BODY)
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3", "--slice", "slice-01", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["slice"]["slice_id"] == "slice-01"


def test_cli_show_emite_el_checklist_entero_con_el_estado_de_cada_slice(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El alcance del issue es un dato del run, no memoria del orquestador.

    El paso 7 se lo pasa al verificador para que distinga "esto falta" de "esto lo cubre otra slice
    declarada". Sin esta clave el orquestador tendria que improvisar un `gh issue view` a mano, que es
    justo lo que la skill prohibe.
    """
    _fake_gh(monkeypatch, _BODY)
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["checklist"] == [
        {"slice_id": "slice-01", "titulo": "Crear VO", "estado": "mergeada", "motivo": ""},
        {"slice_id": "slice-02", "titulo": "Caso de uso AjustarStock", "estado": "esperando-merge", "motivo": ""},
        {"slice_id": "slice-03", "titulo": "Extraer repo", "estado": "en-curso", "motivo": ""},
        {"slice_id": "slice-04", "titulo": "Backfill", "estado": "bloqueada", "motivo": "ci-roja"},
        {"slice_id": "slice-05", "titulo": "Retirar flag", "estado": "pendiente", "motivo": ""},
    ]
    assert data["slices"] == 5


def test_cli_show_emite_el_checklist_aunque_no_quede_ninguna_slice_sin_cerrar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Las claves se emiten siempre: quien consume el JSON no ramifica sobre cuales existen."""
    _fake_gh(monkeypatch, "- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11\n")
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["slice"] is None
    assert data["checklist"] == [{"slice_id": "slice-01", "titulo": "Crear VO", "estado": "mergeada", "motivo": ""}]


def test_cli_show_exit_2_si_la_slice_no_esta(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_gh(monkeypatch, _BODY)
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3", "--slice", "slice-99"]) == 2


def test_cli_no_reescribe_nada_si_el_cuerpo_viene_vacio(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El fallo que justifica la CLI: un `gh issue view` que devuelve vacio y un `edit` detras dejan el issue
    en blanco, o sea la spec y el estado del run perdidos. Falla ruidosamente y NO llama a edit.
    """
    llamadas = _fake_gh(monkeypatch, "")
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-02",
            "--estado",
            "en-curso",
        ]
    )
    assert code == 1
    assert "vino vacio" in capsys.readouterr().err
    assert not any("edit" in a for a in llamadas)


def test_cli_set_estado_escribe_el_cuerpo_reescrito(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas = _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-03",
            "--estado",
            "bloqueada",
            "--motivo",
            "ci-indeterminada",
        ]
    )
    assert code == 0
    assert "ci-indeterminada" in capsys.readouterr().out
    assert any("edit" in a for a in llamadas)


def test_cli_set_estado_rechaza_un_motivo_que_no_es_canonico(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas = _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-03",
            "--estado",
            "bloqueada",
            "--motivo",
            "inventado",
        ]
    )
    assert code == 2
    assert not any("edit" in a for a in llamadas)


def test_cli_set_estado_no_llama_a_edit_si_no_cambia_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas = _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-02",
            "--estado",
            "esperando-merge",
        ]
    )
    assert code == 0
    assert "sin cambios" in capsys.readouterr().out
    assert not any("edit" in a for a in llamadas)


def test_rama_y_scope_son_deterministas() -> None:
    """Alimentan la rama y el scope del commit sin derivar slugs de texto libre."""
    s = issue_body.parse_body(_BODY)[1]
    assert issue_body.rama_de(s) == "slice/02-ajustar-stock"
    assert issue_body.scope_de(s) == "feat(ajustar-stock)"


def test_cli_set_estado_exige_motivo_en_bloqueada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas = _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-03",
            "--estado",
            "bloqueada",
        ]
    )
    assert code == 2
    assert not any("edit" in a for a in llamadas)


def test_cli_set_estado_rechaza_motivo_en_un_estado_que_no_lo_lleva(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas = _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-03",
            "--estado",
            "en-curso",
            "--motivo",
            "controles",
        ]
    )
    assert code == 2
    assert not any("edit" in a for a in llamadas)


def test_cli_show_es_humano_por_defecto(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Mismo contrato que `controles.py`: humano salvo `--json`. La incoherencia anterior -aqui JSON siempre
    y `--pretty`, alli humano salvo `--json`- hizo tropezar en la sonda del 2026-07-30 a quien habia
    escrito los dos scripts el dia antes.
    """
    _fake_gh(monkeypatch, _BODY)
    assert issue_body.main(["show", "--repo", "o/r", "--issue", "3"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("[show]")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_cli_set_estado_tiene_modo_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _fake_gh(monkeypatch, _BODY)
    code = issue_body.main(
        [
            "set-estado",
            "--repo",
            "o/r",
            "--issue",
            "3",
            "--slice",
            "slice-03",
            "--estado",
            "bloqueada",
            "--motivo",
            "verify",
            "--json",
        ]
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "control": "set-estado",
        "issue": "o/r#3",
        "slice": "slice-03",
        "estado": "bloqueada",
        "motivo": "verify",
        "linea": data["linea"],
    }
    assert "bloqueada: verify" in data["linea"]
