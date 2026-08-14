from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.infrastructure.uv_program_origin import UvProgramOrigin

if TYPE_CHECKING:
    from pathlib import Path


class TestTheCheckoutTheProgramCameFrom:
    @staticmethod
    def _dist_info(tools_root: Path) -> Path:
        directory = (
            tools_root / "agentic-skills" / "lib" / "python3.11" / "site-packages" / "agentic_skills-0.0.0.dist-info"
        )
        directory.mkdir(parents=True)

        return directory

    def test_a_well_formed_direct_url_resolves_to_its_local_checkout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))
        checkout = tmp_path / "repos" / "agentic-skills"
        directory = self._dist_info(tmp_path)
        (directory / "direct_url.json").write_text(
            json.dumps({"url": f"file://{checkout}", "dir_info": {}}), encoding="utf-8"
        )

        assert UvProgramOrigin().checkout() == checkout

    def test_no_direct_url_file_at_all_raises_instead_of_pretending_the_origin_is_known(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))

        with pytest.raises(UnreadableProvenanceError):
            UvProgramOrigin().checkout()

    def test_a_direct_url_file_that_is_not_valid_json_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))
        directory = self._dist_info(tmp_path)
        (directory / "direct_url.json").write_text("not json", encoding="utf-8")

        with pytest.raises(UnreadableProvenanceError, match="not valid JSON"):
            UvProgramOrigin().checkout()

    def test_a_direct_url_without_the_url_key_is_an_unrecognized_shape_and_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))
        directory = self._dist_info(tmp_path)
        (directory / "direct_url.json").write_text(json.dumps({"dir_info": {}}), encoding="utf-8")

        with pytest.raises(UnreadableProvenanceError, match="does not carry a readable url"):
            UvProgramOrigin().checkout()

    def test_a_direct_url_pointing_to_a_remote_source_is_an_unrecognized_shape_and_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))
        directory = self._dist_info(tmp_path)
        (directory / "direct_url.json").write_text(
            json.dumps({"url": "https://github.com/alcaptar/agentic-skills", "vcs_info": {}}), encoding="utf-8"
        )

        with pytest.raises(UnreadableProvenanceError, match="is not a local file"):
            UvProgramOrigin().checkout()

    def test_a_sibling_dist_info_that_sorts_first_is_not_mistaken_for_the_programs_own(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path))
        site_packages = tmp_path / "agentic-skills" / "lib" / "python3.11" / "site-packages"
        sibling = site_packages / "aaa-dependency-1.0.dist-info"
        sibling.mkdir(parents=True)
        (sibling / "direct_url.json").write_text(
            json.dumps({"url": "https://example.invalid/aaa-dependency", "vcs_info": {}}), encoding="utf-8"
        )
        checkout = tmp_path / "repos" / "agentic-skills"
        directory = self._dist_info(tmp_path)
        (directory / "direct_url.json").write_text(
            json.dumps({"url": f"file://{checkout}", "dir_info": {}}), encoding="utf-8"
        )

        assert UvProgramOrigin().checkout() == checkout
