#!/usr/bin/env python3
"""
One-off correction for the --heavy phase: finance_interp (FinQA
"AMAT/2013/page_37.pdf-2") was locked with a facit ("3829") that turned out
to be a FinQA annotation bug — the qa.answer string is missing a trailing
zero. qa.exe_ans is 38290.0, and the FinQA program (subtract(138.29,
const_100), divide(100000, const_100), multiply) computes 38290 directly.
The question itself is also genuinely ambiguous between the profit (38290)
and the ending portfolio value (138290 = 100000 + 38290) — see
src/heavy_tasks.py and src/heavy_grader.py, which now encode both.

Re-grades every finance_interp row in an existing --heavy JSONL against both
accepted readings, using the extracted_answer ALREADY STORED on each row —
no new model calls, no re-extraction from answer_text. code and finance_calc
rows pass through byte-identical. Never overwrites the source file.

Usage: python3 regrade_heavy_finance_interp.py results/heavy/<run_id>.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.heavy_grader import _parse_number, _relative_close  # noqa: E402

ACCEPTED_FACIT_NUMERIC: dict[float, str] = {38290.0: "return", 138290.0: "final_value"}
OLD_FACIT_STRING = "3829"


def _regrade_row(row: dict) -> tuple[dict, bool]:
    """Returns (possibly-updated row, flipped) — flipped is True iff domain is
    finance_interp, status is ok, and correct changed."""
    if row.get("domain") != "finance_interp" or row.get("status") != "ok":
        return row, False

    extracted = row.get("extracted_answer")
    primary = _parse_number(extracted) if extracted else None

    matched_label = None
    if primary is not None:
        for fn, label in ACCEPTED_FACIT_NUMERIC.items():
            if _relative_close(primary, fn):
                matched_label = label
                break

    old_correct = row.get("correct")
    new_correct = matched_label is not None

    new_row = dict(row)
    new_row["correct"] = new_correct
    gd = dict(row.get("grading_detail") or {})
    gd["accepted_facit_numerics"] = sorted(ACCEPTED_FACIT_NUMERIC)
    gd["matched_interpretation"] = matched_label
    gd["corrected_from_facit"] = OLD_FACIT_STRING
    gd["correction_note"] = (
        "facit '3829' was a FinQA annotation bug (qa.exe_ans=38290.0, missing "
        "a trailing zero); both 38290 (return) and 138290 (final_value) are "
        "accepted readings of the ambiguous 'total return' question."
    )
    gd["previous_correct"] = old_correct
    new_row["grading_detail"] = gd

    return new_row, (new_correct != old_correct)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 regrade_heavy_finance_interp.py <source.jsonl>")
        sys.exit(1)

    src = Path(sys.argv[1])
    rows = [json.loads(line) for line in src.open(encoding="utf-8") if line.strip()]

    out_rows: list[dict] = []
    n_flipped = 0
    n_finance_interp = 0
    for row in rows:
        new_row, flipped = _regrade_row(row)
        if row.get("domain") == "finance_interp":
            n_finance_interp += 1
        if flipped:
            n_flipped += 1
        out_rows.append(new_row)

    dest = src.with_name(src.stem + "_corrected.jsonl")
    with dest.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        f"Wrote {dest}  ({len(out_rows)} rows total, "
        f"{n_finance_interp} finance_interp rows, {n_flipped} flipped incorrect->correct)"
    )


if __name__ == "__main__":
    main()
