"""Tests de la logica pura del cuerpo del issue (issue_body.py)."""

from __future__ import annotations

import pytest

import issue_body
from issue_body import (
    Fuente,
    Slice,
    fuentes_para,
    parse_body,
    parse_fuentes,
    render_fuentes_section,
    render_slice_line,
    set_fuentes,
    set_slice_estado,
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


def test_parse_body_recoge_ac() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY)}
    assert by_id["slice-01"].ac == ["rechaza negativos; tests en test/domain/test_cantidad.py"]
    assert by_id["slice-02"].ac == ["emite evento StockAjustado", "no toca infra directamente"]
    assert by_id["slice-03"].ac == []


def test_parse_body_ignora_lineas_no_slice() -> None:
    # "- [ ] no es una slice" no debe aparecer como slice.
    assert all(s.slice_id.startswith("slice-") for s in parse_body(_BODY))


def test_set_estado_marca_mergeada_como_checkbox() -> None:
    nuevo = set_slice_estado(_BODY, "slice-02", "mergeada")
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-02"].estado == "mergeada"
    assert "- [x] slice-02 (ajustar-stock): Caso de uso AjustarStock [mergeada] PR #12" in nuevo
    # conserva el PR aunque no se pase
    assert by_id["slice-02"].pr == 12


def test_set_estado_preserva_el_resto_del_cuerpo() -> None:
    nuevo = set_slice_estado(_BODY, "slice-03", "esperando-merge", pr=99)
    # otras slices intactas
    assert "- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11" in nuevo
    # AC de slice-02 intactos
    assert "      AC: no toca infra directamente" in nuevo
    # intro intacta
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
    with pytest.raises(ValueError):
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
    assert "esperando-merge" in issue_body.ESTADOS
    assert "mergeada" in issue_body.ESTADOS


# --- Fuentes de convencion ---

_BODY_CON_FUENTES = """\
# Feature X

Intro de la feature.

## Fuentes de convencion
- doc: .claude/CLAUDE.md
- doc: .claude/rules/conventions/
- skill: .claude/skills/duplicate-action

## Slices
- [ ] slice-01 (vo): Crear VO [pendiente]
      AC: rechaza negativos
"""

_BODY_SIN_FUENTES = """\
# Feature Y

## Slices
- [ ] slice-01 (vo): Crear VO [pendiente]
"""


def test_parse_fuentes_extrae_docs_y_skills_en_orden() -> None:
    fuentes = parse_fuentes(_BODY_CON_FUENTES)
    assert fuentes == [
        Fuente("doc", ".claude/CLAUDE.md"),
        Fuente("doc", ".claude/rules/conventions/"),
        Fuente("skill", ".claude/skills/duplicate-action"),
    ]


def test_parse_fuentes_seccion_ausente_lista_vacia() -> None:
    assert parse_fuentes(_BODY_SIN_FUENTES) == []


def test_parse_fuentes_se_detiene_en_la_siguiente_seccion() -> None:
    # No debe tragarse la linea de slice de '## Slices' como fuente.
    fuentes = parse_fuentes(_BODY_CON_FUENTES)
    assert all(f.tipo in ("doc", "skill") for f in fuentes)
    assert len(fuentes) == 3


def test_parse_fuentes_tolera_tilde_y_mayusculas_en_heading() -> None:
    body = "## Fuentes de Convención\n- skill: .claude/skills/tdd\n"
    assert parse_fuentes(body) == [Fuente("skill", ".claude/skills/tdd")]


def test_tiene_seccion_fuentes_distingue_ausente_de_presente() -> None:
    assert tiene_seccion_fuentes(_BODY_CON_FUENTES) is True
    assert tiene_seccion_fuentes(_BODY_SIN_FUENTES) is False
    # presente pero vacia sigue contando como presente
    assert tiene_seccion_fuentes("## Fuentes de convencion\n") is True


def test_render_fuentes_section_formato_canonico() -> None:
    section = render_fuentes_section(
        [Fuente("doc", ".claude/CLAUDE.md"), Fuente("skill", ".claude/skills/pr")]
    )
    assert section == (
        "## Fuentes de convencion\n- doc: .claude/CLAUDE.md\n- skill: .claude/skills/pr"
    )


def test_render_fuentes_tipo_invalido() -> None:
    with pytest.raises(ValueError):
        render_fuentes_section([Fuente("regla", ".claude/CLAUDE.md")])


def test_set_fuentes_anade_seccion_cuando_no_existe() -> None:
    nuevo = set_fuentes(_BODY_SIN_FUENTES, [Fuente("doc", ".claude/CLAUDE.md")])
    assert tiene_seccion_fuentes(nuevo)
    assert parse_fuentes(nuevo) == [Fuente("doc", ".claude/CLAUDE.md")]
    # preserva las slices existentes
    assert [s.slice_id for s in parse_body(nuevo)] == ["slice-01"]


def test_set_fuentes_reemplaza_seccion_existente_preservando_el_resto() -> None:
    nuevo = set_fuentes(_BODY_CON_FUENTES, [Fuente("skill", ".claude/skills/tdd")])
    assert parse_fuentes(nuevo) == [Fuente("skill", ".claude/skills/tdd")]
    # la vieja lista de docs desaparece
    assert "duplicate-action" not in nuevo
    # lo de despues de la seccion sigue intacto
    assert "Intro de la feature." in nuevo
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-01"].ac == ["rechaza negativos"]


def test_set_fuentes_preserva_trailing_newline() -> None:
    assert set_fuentes(_BODY_SIN_FUENTES, [Fuente("doc", "x")]).endswith("\n")
    sin_nl = _BODY_SIN_FUENTES.rstrip("\n")
    assert not set_fuentes(sin_nl, [Fuente("doc", "x")]).endswith("\n")


def test_roundtrip_render_parse_fuentes() -> None:
    fuentes = [Fuente("doc", "docs/conventions/"), Fuente("skill", ".claude/skills/x")]
    parsed = parse_fuentes(render_fuentes_section(fuentes) + "\n")
    assert parsed == fuentes


# --- SENAL y REPO: observabilidad y slices cross-repo ---

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
      AC: incrementa stock_ajustado_total{motivo}
      SENAL: prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
- [ ] slice-02 (alerta-ajuste): Alerta de ajustes fallidos [pendiente]
      REPO: mercadona/mercadona.online.gke
      AC: promtool test dispara ShopAjusteFallido con 3 fallos
      SENAL: prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory
- [ ] slice-03 (extraer-repo): Extraer repositorio [pendiente]
      AC: sin cambio de comportamiento
      SENAL: exenta - refactor puro
"""


def test_parse_body_recoge_senal() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}
    assert by_id["slice-01"].senal == [
        "prometheus rate(stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical"
    ]
    assert by_id["slice-03"].senal == ["exenta - refactor puro"]


def test_parse_body_senal_ausente_es_lista_vacia() -> None:
    # Una spec legacy sin SENAL no revienta: slice-runner avisa, no bloquea.
    assert parse_body(_BODY)[0].senal == []


def test_parse_body_acepta_senal_con_tilde() -> None:
    body = "## Slices\n- [ ] slice-01 (x): T [pendiente]\n      SEÑAL: prometheus foo > 0\n"
    assert parse_body(body)[0].senal == ["prometheus foo > 0"]


def test_parse_body_senal_no_se_confunde_con_ac() -> None:
    s01 = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}["slice-01"]
    assert s01.ac == ["incrementa stock_ajustado_total{motivo}"]


def test_parse_body_recoge_repo_destino() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY_CON_SENAL)}
    assert by_id["slice-02"].repo == _GKE
    # ausente = el repo del issue
    assert by_id["slice-01"].repo is None


def test_set_estado_preserva_senal_y_repo() -> None:
    nuevo = set_slice_estado(_BODY_CON_SENAL, "slice-02", "en-curso", pr=7)
    s02 = {s.slice_id: s for s in parse_body(nuevo)}["slice-02"]
    assert s02.estado == "en-curso"
    assert s02.pr == 7
    assert s02.repo == _GKE
    assert s02.senal == [
        'prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory'
    ]


def test_parse_fuentes_atribuye_subseccion_al_repo_destino() -> None:
    assert parse_fuentes(_BODY_CON_SENAL) == [
        Fuente("doc", "CLAUDE.md"),
        Fuente("doc", "templates/CLAUDE.md", _GKE),
        Fuente("doc", "tests/prometheus/README.md", _GKE),
    ]


def test_fuentes_para_filtra_por_repo() -> None:
    fuentes = parse_fuentes(_BODY_CON_SENAL)
    assert fuentes_para(fuentes) == [Fuente("doc", "CLAUDE.md")]
    assert [f.ruta for f in fuentes_para(fuentes, _GKE)] == [
        "templates/CLAUDE.md",
        "tests/prometheus/README.md",
    ]


def test_fuentes_para_repo_sin_vara_declarada() -> None:
    # No inventa una vara heredada: si el repo destino no declara fuentes, esta vacio
    # y slice-runner para en el paso 1 en vez de medir con la del repo de la app.
    assert fuentes_para(parse_fuentes(_BODY_CON_SENAL), "mercadona/otro") == []


def test_render_fuentes_agrupa_por_repo_en_subsecciones() -> None:
    section = render_fuentes_section(
        [
            Fuente("doc", "CLAUDE.md"),
            Fuente("doc", "templates/CLAUDE.md", _GKE),
            Fuente("skill", ".claude/skills/x"),
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
        Fuente("doc", "CLAUDE.md"),
        Fuente("doc", "templates/CLAUDE.md", _GKE),
        Fuente("skill", "settings/README.md", "mercadona/mo.sre.grafana-configs"),
    ]
    assert parse_fuentes(render_fuentes_section(fuentes) + "\n") == fuentes


def test_set_fuentes_reemplaza_tambien_las_subsecciones_de_repo() -> None:
    nuevo = set_fuentes(_BODY_CON_SENAL, [Fuente("doc", "CLAUDE.md")])
    assert parse_fuentes(nuevo) == [Fuente("doc", "CLAUDE.md")]
    assert "tests/prometheus/README.md" not in nuevo
    # las slices y sus SENAL siguen intactas
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-03"].senal == ["exenta - refactor puro"]
