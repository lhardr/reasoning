#!/usr/bin/env python3
"""
Flag inter-judge disagreement in the canonical judge files.

datasite/data/judges-heavy.json and judges-light-new.json each carry two
independent judges (minimax, gemini_3_1_pro) per scored cell, but neither
file stores an `agreement` field — the run that produced them never called
src/judge.py's compute_agreement(), unlike the earlier Phase 2 validation
runs. This script calls it after the fact, one cell at a time, and reports
every cell where compute_agreement() flags high_disagreement (max
per-dimension diff >= 2 on the 1-5 scale) — the same threshold the codebase
already defines, just never applied to this data.

Read-only: does not modify the judge files. Usage:
    python3 scripts/check_judge_agreement.py
"""
from __future__ import annotations

import json
import pathlib
import sys

PROJECT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT))

from src.judge import compute_agreement, DIMENSIONS  # noqa: E402

DATA_FILES = {
    "heavy": PROJECT / "datasite/data/judges-heavy.json",
    "light": PROJECT / "datasite/data/judges-light-new.json",
}


def cell_label(suite: str, cell: dict) -> str:
    if suite == "heavy":
        return f"{cell['model']}/{cell['task']}/{cell['condition']}/pass{cell['pass_index']}"
    return f"{cell['model']}/{cell.get('prompt', '?')}"


def is_parse_failure(judge_entry: dict) -> bool:
    # Real judge rows always carry non-empty justification text. A parse
    # failure falls back to a placeholder score with empty redJust/cohJust —
    # same shape as a real 2-judge cell, so compute_agreement() can't tell
    # the difference on its own.
    name = judge_entry.get("judge", "")
    return "⚠" in name or "fejl" in name.lower() or "error" in name.lower() or (
        not judge_entry.get("redJust") and not judge_entry.get("cohJust")
    )


def check_file(suite: str, path: pathlib.Path) -> tuple[list[dict], list[dict], dict]:
    data = json.loads(path.read_text())
    cells = data["cells"]
    flagged = []
    parse_failures = []
    per_judge_sums: dict[str, dict[str, float]] = {}
    n_judged = 0
    n_two = 0
    for cell in cells:
        judges = cell.get("judges", [])
        if not judges:
            continue
        n_judged += 1
        for j in judges:
            if is_parse_failure(j):
                parse_failures.append({"suite": suite, "label": cell_label(suite, cell), "judge": j})
                continue
            s = per_judge_sums.setdefault(j["judge"], {"redundancy": 0.0, "coherence": 0.0, "n": 0})
            s["redundancy"] += j["redundancy"]
            s["coherence"] += j["coherence"]
            s["n"] += 1
        if len(judges) != 2:
            continue
        n_two += 1
        scores1 = {dim: judges[0][dim] for dim in DIMENSIONS}
        scores2 = {dim: judges[1][dim] for dim in DIMENSIONS}
        agreement = compute_agreement(scores1, scores2)
        if agreement["high_disagreement"]:
            flagged.append({
                "suite": suite,
                "label": cell_label(suite, cell),
                "model": cell["model"],
                "task_or_prompt": cell.get("task") or cell.get("prompt"),
                "condition": cell.get("condition"),
                "agreement": agreement,
                "judges": judges,
            })
    print(f"\n{suite}: {len(cells)} cells total, {n_judged} judged, "
          f"{n_two} with exactly 2 judges, {len(flagged)} high-disagreement "
          f"({100 * len(flagged) / n_two:.0f}%)" if n_two else f"\n{suite}: no 2-judge cells")
    return flagged, parse_failures, per_judge_sums


def main() -> None:
    all_flagged = []
    all_parse_failures = []
    all_judge_sums: dict[str, dict[str, dict[str, float]]] = {}
    for suite, path in DATA_FILES.items():
        flagged, parse_failures, per_judge_sums = check_file(suite, path)
        all_flagged.extend(flagged)
        all_parse_failures.extend(parse_failures)
        all_judge_sums[suite] = per_judge_sums

    if all_parse_failures:
        print(f"\n{'=' * 100}\nPARSE-FAILURE JUDGE ENTRIES (placeholder score, no justification "
              f"text — excluded from agreement stats above)\n{'=' * 100}")
        for pf in all_parse_failures:
            print(f"  [{pf['suite']}] {pf['label']}: {pf['judge']}")

    print(f"\n{'=' * 100}\nPER-JUDGE MEAN SCORES (systematic leniency check)\n{'=' * 100}")
    for suite, sums in all_judge_sums.items():
        print(f"{suite}:")
        for jname, s in sums.items():
            print(f"  {jname:<16} n={int(s['n']):<4} "
                  f"mean_redundancy={s['redundancy']/s['n']:.2f}  mean_coherence={s['coherence']/s['n']:.2f}")

    print(f"\n{'=' * 100}\nHIGH-DISAGREEMENT CELLS (max per-dimension diff >= 2)\n{'=' * 100}")
    for f in all_flagged:
        j0, j1 = f["judges"]
        print(f"\n[{f['suite']}] {f['label']}")
        print(f"  dim_diffs={f['agreement']['dim_diffs']}  max_diff={f['agreement']['max_diff']}")
        for j in (j0, j1):
            print(f"    {j['judge']:<14} redundancy={j['redundancy']} coherence={j['coherence']}")

    print(f"\n{'=' * 100}\nCONCENTRATION\n{'=' * 100}")
    by_task = {}
    by_model = {}
    for f in all_flagged:
        key_task = (f["suite"], f["task_or_prompt"])
        by_task[key_task] = by_task.get(key_task, 0) + 1
        by_model[f["model"]] = by_model.get(f["model"], 0) + 1
    print("By suite/task-or-prompt:")
    for k, v in sorted(by_task.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    print("By model:")
    for k, v in sorted(by_model.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
