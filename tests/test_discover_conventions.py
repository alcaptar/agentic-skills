"""Tests del descubrimiento determinista de candidatos a fuente de convencion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import escribe

from discover_conventions import Fuente, discover_candidates

if TYPE_CHECKING:
    from pathlib import Path


def _build_repo(root: Path) -> None:
    """Un arbol parecido al de un repo real (estilo mo.picking.api)."""
    escribe(root, ".claude/CLAUDE.md")
    escribe(root, ".claude/rules/conventions/testing.md")
    escribe(root, ".claude/rules/conventions/delivery.md")
    escribe(root, ".claude/skills/duplicate-action/SKILL.md")
    escribe(root, ".claude/skills/deprecate-hermes-handler/SKILL.md")
    escribe(root, "CONTRIBUTING.md")
    escribe(root, "src/app/CLAUDE.md")
    escribe(root, ".git/config")
    escribe(root, "__pycache__/x.pyc")
    escribe(root, "node_modules/dep/CLAUDE.md")
    escribe(root, "src/app/service.py")


def test_descubre_docs_y_skills(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    fuentes = discover_candidates(tmp_path)

    docs = {f.ruta for f in fuentes if f.tipo == "doc"}
    skills = {f.ruta for f in fuentes if f.tipo == "skill"}

    assert ".claude/CLAUDE.md" in docs
    assert "CONTRIBUTING.md" in docs
    assert "src/app/CLAUDE.md" in docs
    assert ".claude/skills/duplicate-action/" in skills
    assert ".claude/skills/deprecate-hermes-handler/" in skills


def test_directorio_de_convencion_como_puntero_al_outermost(tmp_path: Path) -> None:
    """El puntero apunta al directorio de reglas mas externo.

    Ni a cada `.md` de dentro ni al `conventions/` anidado: uno solo cubre el arbol entero, y los
    de dentro serian ruido en la vara de medir.
    """
    _build_repo(tmp_path)
    docs = {f.ruta for f in discover_candidates(tmp_path) if f.tipo == "doc"}
    assert ".claude/rules/" in docs
    assert ".claude/rules/conventions/" not in docs
    assert ".claude/rules/conventions/testing.md" not in docs


def test_ignora_directorios_ruido(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    rutas = {f.ruta for f in discover_candidates(tmp_path)}
    assert not any(".git" in r for r in rutas)
    assert not any("__pycache__" in r for r in rutas)
    assert not any("node_modules" in r for r in rutas)


def test_orden_determinista_docs_luego_skills(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    fuentes = discover_candidates(tmp_path)
    tipos = [f.tipo for f in fuentes]
    assert tipos == sorted(tipos, key=lambda t: 0 if t == "doc" else 1)
    docs = [f.ruta for f in fuentes if f.tipo == "doc"]
    skills = [f.ruta for f in fuentes if f.tipo == "skill"]
    assert docs == sorted(docs)
    assert skills == sorted(skills)


def test_ignora_dirs_ocultos_dentro_de_skills(tmp_path: Path) -> None:
    """`.claude/skills/.nwave/` es estado de herramienta, no una skill de proyecto."""
    escribe(tmp_path, ".claude/skills/duplicate-action/SKILL.md")
    escribe(tmp_path, ".claude/skills/.nwave/config.json")
    skills = {f.ruta for f in discover_candidates(tmp_path) if f.tipo == "skill"}
    assert skills == {".claude/skills/duplicate-action/"}


def test_repo_sin_candidatos_lista_vacia(tmp_path: Path) -> None:
    escribe(tmp_path, "src/main.py")
    assert discover_candidates(tmp_path) == []


def test_devuelve_fuentes(tmp_path: Path) -> None:
    escribe(tmp_path, "CLAUDE.md")
    fuentes = discover_candidates(tmp_path)
    assert fuentes == [Fuente(tipo="doc", ruta="CLAUDE.md")]
