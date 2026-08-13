from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.role_spend import RoleSpend


class ClosedSliceMetricsView:
    WIDTH = 480
    HEIGHT = 220

    @classmethod
    def rendered(
        cls,
        *,
        repo: str | None,
        since: datetime,
        until: datetime,
        records: tuple[ClosedSliceRecord, ...],
        role_spend: tuple[RoleSpend, ...],
    ) -> str:
        return (
            '<!doctype html><html><head><meta charset="utf-8"><title>slice-runner metrics</title></head><body>'
            f"{cls._header(repo=repo, since=since, until=until, records=records)}"
            f"{cls._gaps()}"
            f"{cls._duplicates(records)}"
            f"{cls._cost_against_size(records)}"
            f"{cls._spend_by_role(role_spend)}"
            f"{cls._rounds_over_time(records)}"
            "</body></html>"
        )

    @staticmethod
    def _header(*, repo: str | None, since: datetime, until: datetime, records: tuple[ClosedSliceRecord, ...]) -> str:
        scope = repo or "every repo"
        return (
            f"<section><h1>slice-runner metrics</h1>"
            f"<p>{scope}, from {since.isoformat()} to {until.isoformat()}: {len(records)} closed slice(s)</p>"
            "</section>"
        )

    @staticmethod
    def _gaps() -> str:
        return (
            "<section><h2>what this view cannot say</h2><ul>"
            "<li>diff size: only present when a verify ran in the invocation that closed the slice; "
            "a resumed slice closes with no size measured</li>"
            "<li>configuration: budgets and models by role travel as the snapshot the run closed with, "
            "and today every run shares the same defaults, so no variation is shown yet</li>"
            "<li>input and output tokens: the durable log never carried them, only cost, turns, "
            "duration and cache reads</li>"
            "</ul></section>"
        )

    @staticmethod
    def _duplicates(records: tuple[ClosedSliceRecord, ...]) -> str:
        counted: dict[tuple[str, int, str], int] = {}
        for record in records:
            key = (record.repo, record.issue, record.slice_id)
            counted[key] = counted.get(key, 0) + 1

        repeated = {key: count for key, count in counted.items() if count > 1}
        if not repeated:
            return "<section><h2>slices closed more than once</h2><p>no slice was recorded more than once</p></section>"

        rows = "".join(
            f'<li data-repo="{repo}" data-issue="{issue}" data-slice-id="{slice_id}" data-rows="{count}">'
            f"{repo}#{issue} {slice_id}: {count} rows</li>"
            for (repo, issue, slice_id), count in repeated.items()
        )
        return f"<section><h2>slices closed more than once</h2><ul>{rows}</ul></section>"

    @classmethod
    def _cost_against_size(cls, records: tuple[ClosedSliceRecord, ...]) -> str:
        measured = tuple(record for record in records if record.diff is not None and record.spend is not None)
        if not measured:
            return (
                "<section><h2>cost against size</h2>"
                "<p>no slice in this window measured both its size and its spend</p></section>"
            )

        sizes = tuple(record.diff.lines_added + record.diff.lines_deleted for record in measured)  # type: ignore[union-attr]
        widest = max(sizes) or 1
        costliest = max(record.spend.cost_usd for record in measured) or 1  # type: ignore[union-attr]
        points = "".join(
            f'<circle data-slice-id="{record.slice_id}" data-lines="{lines}" '
            f'data-cost-usd="{record.spend.cost_usd}" '  # type: ignore[union-attr]
            f'cx="{cls._scaled(lines, widest, cls.WIDTH)}" '
            f'cy="{cls.HEIGHT - cls._scaled(record.spend.cost_usd, costliest, cls.HEIGHT)}" r="4"/>'  # type: ignore[union-attr]
            for record, lines in zip(measured, sizes, strict=True)
        )
        return (
            "<section><h2>cost against size</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{points}</svg>'
            "</section>"
        )

    @classmethod
    def _spend_by_role(cls, role_spend: tuple[RoleSpend, ...]) -> str:
        if not role_spend:
            return "<section><h2>spend by role</h2><p>no call was traced in this window</p></section>"

        costliest = max(entry.spend.cost_usd for entry in role_spend) or 1
        bar_width = cls.WIDTH / len(role_spend)
        bars = "".join(
            f'<rect data-step="{entry.step}" data-cost-usd="{entry.spend.cost_usd}" '
            f'x="{index * bar_width}" y="{cls.HEIGHT - cls._scaled(entry.spend.cost_usd, costliest, cls.HEIGHT)}" '
            f'width="{bar_width * 0.8}" height="{cls._scaled(entry.spend.cost_usd, costliest, cls.HEIGHT)}"/>'
            for index, entry in enumerate(role_spend)
        )
        return (
            "<section><h2>spend by role</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{bars}</svg>'
            "</section>"
        )

    @classmethod
    def _rounds_over_time(cls, records: tuple[ClosedSliceRecord, ...]) -> str:
        if not records:
            return "<section><h2>rounds over time</h2><p>no slice was closed in this window</p></section>"

        ordered = sorted(records, key=lambda record: record.ts)
        widest = (ordered[-1].ts - ordered[0].ts).total_seconds() or 1
        tallest = max(record.implement_retries for record in ordered) or 1
        points = "".join(
            f'<circle data-slice-id="{record.slice_id}" data-ts="{record.ts.isoformat()}" '
            f'data-rounds="{record.implement_retries}" '
            f'cx="{cls._scaled((record.ts - ordered[0].ts).total_seconds(), widest, cls.WIDTH)}" '
            f'cy="{cls.HEIGHT - cls._scaled(record.implement_retries, tallest, cls.HEIGHT)}" r="4"/>'
            for record in ordered
        )
        return (
            "<section><h2>rounds over time</h2>"
            f'<svg viewBox="0 0 {cls.WIDTH} {cls.HEIGHT}" width="{cls.WIDTH}" height="{cls.HEIGHT}">{points}</svg>'
            "</section>"
        )

    @staticmethod
    def _scaled(value: float, widest: float, span: int) -> float:
        return round((value / widest) * span, 2)
