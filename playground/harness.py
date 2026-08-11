from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
RUNS = Path.home() / "repos" / "as-playground" / "runs"
CALL_TIMEOUT_SECONDS = 900


@dataclass(frozen=True, kw_only=True, slots=True)
class Cell:
    task: str
    variant: str
    seed: str
    repetition: int

    @property
    def name(self) -> str:
        return f"{self.variant}__{self.seed}__{self.repetition:02d}"


class Task:
    def __init__(self, name: str) -> None:
        self.name = name
        self.root = TASKS / name
        spec = importlib.util.spec_from_file_location(f"task_{name}", self.root / "task.py")
        if spec is None or spec.loader is None:
            raise SystemExit(f"no se pudo cargar {self.root / 'task.py'}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module

    @property
    def variants(self) -> dict[str, Callable[[Path], str]]:
        return self.module.VARIANTS

    @property
    def model(self) -> str:
        return getattr(self.module, "MODEL", "sonnet")

    @property
    def tools(self) -> list[str]:
        return getattr(self.module, "TOOLS", ["Read", "Write", "Edit", "Glob", "Grep"])

    @property
    def correction(self) -> Callable[[Path], str] | None:
        return getattr(self.module, "CORRECTION", None)

    @property
    def resumes(self) -> frozenset[str]:
        return frozenset(getattr(self.module, "RESUMES", ()))

    def measure(self, tree: Path) -> dict[str, bool | None]:
        return self.module.measure(tree)


class Runner:
    def __init__(self, *, task: Task, label: str, model: str | None = None) -> None:
        self.task = task
        self.workspace = RUNS / label
        self.results = self.workspace / "results.jsonl"
        self.model = model or task.model

    def prepare(self, cell: Cell) -> Path:
        tree = self.workspace / cell.name
        if tree.exists():
            shutil.rmtree(tree)
        shutil.copytree(self.task.root / cell.seed, tree)

        return tree

    def invoke(self, *, tree: Path, prompt: str, resume: str | None = None) -> dict[str, Any]:
        argv = [
            "claude",
            "-p",
            "--model",
            self.model,
            "--output-format",
            "json",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(self.task.tools),
            "--strict-mcp-config",
            *(["--resume", resume] if resume else []),
        ]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                cwd=str(tree),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=CALL_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"failed": "timeout", "seconds": time.monotonic() - started}

        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            return {"failed": f"exit {completed.returncode}", "stderr": completed.stderr[-2000:], "seconds": elapsed}

        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"failed": "unparseable", "stdout": completed.stdout[-2000:], "seconds": elapsed}

        return {
            "cost_usd": envelope.get("total_cost_usd"),
            "turns": envelope.get("num_turns"),
            "usage": envelope.get("usage"),
            "session_id": envelope.get("session_id"),
            "seconds": elapsed,
        }

    def run(self, cell: Cell) -> dict[str, Any]:
        tree = self.prepare(cell)
        prompt = self.task.variants[cell.variant](tree)
        (tree / ".prompt.txt").write_text(prompt, encoding="utf-8")
        call = self.invoke(tree=tree, prompt=prompt)
        row: dict[str, Any] = {
            "task": cell.task,
            "variant": cell.variant,
            "seed": cell.seed,
            "repetition": cell.repetition,
            "prompt_chars": len(prompt),
            **call,
        }
        if "failed" in call:
            return row

        correction = self.task.correction
        if correction is None:
            row["rules"] = self.task.measure(tree)

            return row

        row["rules_before_the_correction"] = self.task.measure(tree)
        row["second"] = self._corrected(cell, tree=tree, correction=correction(tree), after=call)
        row["rules"] = self.task.measure(tree)

        return row

    def _corrected(self, cell: Cell, *, tree: Path, correction: str, after: dict[str, Any]) -> dict[str, Any]:
        resume = after.get("session_id") if cell.variant in self.task.resumes else None
        if cell.variant in self.task.resumes and not resume:
            return {"failed": "sin sesion que reanudar"}

        (tree / ".prompt-2.txt").write_text(correction, encoding="utf-8")

        return {"resumed": bool(resume), **self.invoke(tree=tree, prompt=correction, resume=resume)}


class Report:
    @staticmethod
    def of(rows: list[dict[str, Any]]) -> str:
        measured = [row for row in rows if "rules" in row]
        if not measured:
            return "ninguna celda produjo medida"

        rules = sorted({rule for row in measured for rule in row["rules"]})
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in measured:
            groups.setdefault((row["seed"], row["variant"]), []).append(row)

        width = max(len(rule) for rule in rules) + 2
        lines = []
        for seed in sorted({key[0] for key in groups}):
            keys = sorted(key for key in groups if key[0] == seed)
            lines.append(f"\n=== semilla: {seed} ===")
            lines.append("regla".ljust(width) + "".join(key[1].rjust(14) for key in keys))
            for rule in rules:
                cells = []
                for key in keys:
                    applicable = [row["rules"][rule] for row in groups[key] if row["rules"].get(rule) is not None]
                    if not applicable:
                        cells.append("n/a".rjust(14))
                        continue
                    passing = sum(1 for value in applicable if value)
                    cells.append(f"{passing}/{len(applicable)}".rjust(14))
                lines.append(rule.ljust(width) + "".join(cells))

            lines.append("-" * (width + 14 * len(keys)))
            lines.extend(Report._metrics(groups, keys=keys, width=width))

        return "\n".join(lines)

    @staticmethod
    def _metrics(
        groups: dict[tuple[str, str], list[dict[str, Any]]], *, keys: list[tuple[str, str]], width: int
    ) -> list[str]:
        rounds: tuple[tuple[str, str], ...] = (("", ""),)
        if any(row.get("second") for key in keys for row in groups[key]):
            rounds = (("1a vuelta ", ""), ("2a vuelta ", "second"))

        lines = []
        for prefix, source in rounds:
            for label, extract in (("coste $", "cost_usd"), ("turnos", "turns"), ("segundos", "seconds")):
                cells = [Report._averaged(groups[key], source=source, extract=extract) for key in keys]
                lines.append((prefix + label).ljust(width) + "".join(cells))

        return lines

    @staticmethod
    def _averaged(rows: list[dict[str, Any]], *, source: str, extract: str) -> str:
        values = [
            value for row in rows if (value := (row.get(source) or {} if source else row).get(extract)) is not None
        ]

        return (f"{sum(values) / len(values):.3f}" if values else "-").rjust(14)


class Main:
    @staticmethod
    def run() -> int:
        parser = argparse.ArgumentParser()
        parser.add_argument("task")
        parser.add_argument("--label", required=True)
        parser.add_argument("--variants", nargs="+")
        parser.add_argument("--seeds", nargs="+")
        parser.add_argument("--repetitions", type=int, default=5)
        parser.add_argument("--workers", type=int, default=6)
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument("--model", help="sustituye el modelo que declara la tarea, para compararlos")
        args = parser.parse_args()

        task = Task(args.task)
        runner = Runner(task=task, label=args.label, model=args.model)

        if args.report_only:
            rows = [json.loads(line) for line in runner.results.read_text(encoding="utf-8").splitlines() if line]
            print(Report.of(rows))

            return 0

        unknown = set(args.variants) - set(task.variants)
        if unknown:
            raise SystemExit(f"variantes desconocidas: {sorted(unknown)}")

        runner.workspace.mkdir(parents=True, exist_ok=True)
        cells = [
            Cell(task=args.task, variant=variant, seed=seed, repetition=repetition)
            for seed in args.seeds
            for variant in args.variants
            for repetition in range(1, args.repetitions + 1)
        ]
        print(f"{len(cells)} celdas, {args.workers} en paralelo", flush=True)

        rows: list[dict[str, Any]] = []
        with runner.results.open("a", encoding="utf-8") as log, ThreadPoolExecutor(max_workers=args.workers) as pool:
            for row in pool.map(runner.run, cells):
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                print(f"  {row['variant']}/{row['seed']}/{row['repetition']:02d} {row.get('failed', 'ok')}", flush=True)

        print(Report.of(rows))

        return 0


if __name__ == "__main__":
    sys.exit(Main.run())
