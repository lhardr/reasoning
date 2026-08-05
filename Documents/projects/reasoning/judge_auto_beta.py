"""
Legibility judge run on the 35 judge-eligible light-suite rows from the
openrouter/auto-beta candidate test (results/auto/20260805T080708_autobeta.jsonl),
so the quality claim in docs/cc_debrief_auto_beta.md's routing sections can be
substantiated or refuted against the panel's own judge scores.

SCOPE: P1, P2, P3, P4, P8, P9, P10 (7 prompts x 5 passes = 35 rows). P5-P7
(programmatically correctness-graded) are out of scope — already judged on
correctness, not touched here.

SETUP — matches the panel's own Phase 2 judge run (docs/legibilitets_rubrik.md
/ judges-light-new.json) for comparability:
  - Same two judge models, same (undated) OpenRouter slugs as panel.yaml's
    `minimax`/`gemini_3_1_pro` rows: minimax/minimax-m3, google/gemini-3.1-pro-preview.
    Both were confirmed still live on OpenRouter's catalog before this script
    was written (panel.yaml never pinned a dated snapshot for either judge —
    there was no deeper pin to lose). If either had disappeared from the
    catalog, this script would not have been written — the brief was to STOP
    and report instead of substituting a different judge.
  - Same rubric: src/judge.py's build_rubric_prompt() / _RUBRIC_TEMPLATE,
    imported unmodified. (src/judge_rubric.py's ANCHORED_RUBRIC_TEMPLATE is
    byte-identical to judge.py's own _RUBRIC_TEMPLATE today — confirmed by
    direct comparison — so there is no separate "anchored" variant to apply;
    judge.py's default already IS the anchored rubric.)
  - Same two dimensions, same JSON output shape: redundancy + coherence only.
    No "quality" or "correctness" field exists in judges-light-new.json's
    schema (nor in src/judge.py's DIMENSIONS) — the legibility judge has
    never scored correctness, only how followable the trace/answer is. This
    script does not invent a new dimension.
  - Blind: build_rubric_prompt()'s template never mentions model identity or
    routing — used unmodified, so this is blind by construction. No model
    name, "auto-beta", or "router" string is ever injected into the prompt.

DELIBERATE DEVIATION FROM THE PANEL'S SETUP, per explicit instruction: the
panel's Phase 2 always scores raw_reasoning_trace, never answer_text (see
run.py lines ~1308/1475, `trace_text = row.get("raw_reasoning_trace") or ""`).
This script scores answer_text instead, for every one of the 35 rows
uniformly. Two reasons this was the explicit instruction, not a mistake:
  1. It was stated as a direct instruction ("Grader SVARENE (answer_text)"),
     not conditional on the panel's behavior.
  2. It's the only way to include the P8 cell at all: P8 was routed to
     anthropic/claude-sonnet-5, which returned trace_status="absent" (no
     usable raw_reasoning_trace) — exactly the condition under which the
     panel's own Phase 2 EXCLUDES a model entirely (LEGIBILITY_EXCLUDED
     covers claude_sonnet_4_6/opus_4_8 for precisely this reason). Since the
     brief explicitly wants a P8/Sonnet-5 note, trace-based scoring would
     have made that impossible for this run.
This means the resulting scores are NOT a strict apples-to-apples measurement
against judges-light-new.json's trace-based numbers — see the comparability
caveat in docs/cc_debrief_auto_beta.md's addendum. Answers are shorter and
more structured than raw CoT traces, so redundancy/coherence scores computed
on answers should be expected to trend cleaner across the board regardless of
routing.

Cost guard: PRICE_CAP_USD, script stops (not crashes) and reports if crossed.
Never touches judges-light-new.json, reasoning-data.json, results/full,
results/heavy, or docs/reasoning_findings.md.

Output: results/auto/judges-autobeta.json, same "cells" list shape as
judges-light-new.json (each cell: {"judge": ..., "redundancy": ...,
"coherence": ..., "redJust": ..., "cohJust": ...}), with each cell keyed by
prompt_id + pass_index + the actually-routed model_version (recorded for our
own bookkeeping only — never sent to the judges).
"""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.config_loader import load_panel, load_pricing, load_prompts
from src.judge import DIMENSIONS, build_rubric_prompt, call_judge_openrouter

SCOPE_PROMPT_IDS = ["P1", "P2", "P3", "P4", "P8", "P9", "P10"]
JUDGE_KEYS = ["minimax", "gemini_3_1_pro"]
PRICE_CAP_USD = 3.0
SOURCE_JSONL = Path(__file__).parent / "results" / "auto" / "20260805T080708_autobeta.jsonl"
OUT_PATH = Path(__file__).parent / "results" / "auto" / "judges-autobeta.json"


def load_scope_rows() -> list[dict]:
    rows = [json.loads(l) for l in open(SOURCE_JSONL, encoding="utf-8")]
    scope = [r for r in rows if r["task_id"] in SCOPE_PROMPT_IDS]
    assert len(scope) == 35, f"expected 35 rows, got {len(scope)}"
    return scope


def resolve_judge_ids() -> dict[str, str]:
    panel = load_panel()
    ids = {}
    for key in JUDGE_KEYS:
        or_id = panel[key]["openrouter_model_id"]
        ids[key] = or_id
    return ids


def main() -> None:
    scope_rows = load_scope_rows()
    prompts = load_prompts()
    judge_ids = resolve_judge_ids()
    load_pricing()  # sanity: pricing.yaml must have minimax/gemini_3_1_pro rows

    print(f"scope_rows={len(scope_rows)}  judges={judge_ids}  price_cap_usd={PRICE_CAP_USD}")
    print("-" * 100)

    cells: list[dict] = []
    total_cost = 0.0
    stopped_reason = None

    for row in scope_rows:
        if stopped_reason:
            break
        pid = row["task_id"]
        prompt_text = prompts[pid]["prompt"]
        answer_text = row["answer_text"] or ""

        rubric = build_rubric_prompt(prompt_text, answer_text)

        judge_results = []
        for judge_key in JUDGE_KEYS:
            if total_cost >= PRICE_CAP_USD:
                stopped_reason = (
                    f"PRICE CAP REACHED: cumulative cost_usd={total_cost:.4f} >= "
                    f"{PRICE_CAP_USD} before prompt={pid} pass={row['pass_index']} judge={judge_key}"
                )
                print(f"\n!!! {stopped_reason}")
                break

            or_id = judge_ids[judge_key]
            jr = call_judge_openrouter(or_id, rubric, pricing_key=judge_key)
            total_cost += jr.cost_usd

            if not jr.parse_ok:
                print(f"  WARN parse_error pid={pid} pass={row['pass_index']} judge={judge_key}: {jr.parse_error}")

            judge_results.append({
                "judge": judge_key,
                "redundancy": jr.scores.get("redundancy", 0),
                "coherence": jr.scores.get("coherence", 0),
                "redJust": jr.justifications.get("redundancy", ""),
                "cohJust": jr.justifications.get("coherence", ""),
                "parse_ok": jr.parse_ok,
                "judge_model_version": jr.model_version,
                "judge_cost_usd": round(jr.cost_usd, 6),
            })
            print(
                f"  ok  pid={pid:<4} pass={row['pass_index']} judge={judge_key:<13} "
                f"red={jr.scores.get('redundancy')} coh={jr.scores.get('coherence')} "
                f"cost=${jr.cost_usd:.5f}  cum=${total_cost:.4f}"
            )

        if judge_results:
            cells.append({
                "prompt_id": pid,
                "pass_index": row["pass_index"],
                "model_version": row["model_version"],
                "served_by": row["served_by"],
                "trace_status": row["trace_status"],
                "graded_field": "answer_text",
                "judges": judge_results,
            })

    print("-" * 100)
    print(f"cells_written={len(cells)}/35  total_cost_usd={total_cost:.4f}")
    if stopped_reason:
        print(f"STOPPED EARLY: {stopped_reason}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "source_run_id": "20260805T080708_autobeta",
        "source_jsonl": str(SOURCE_JSONL.relative_to(Path(__file__).parent)),
        "judge_openrouter_ids": judge_ids,
        "dimensions": DIMENSIONS,
        "graded_field": "answer_text",
        "graded_field_note": (
            "Deliberate deviation from the panel's Phase 2 (which always scores "
            "raw_reasoning_trace) — see judge_auto_beta.py docstring."
        ),
        "price_cap_usd": PRICE_CAP_USD,
        "total_cost_usd": round(total_cost, 4),
        "stopped_early": stopped_reason,
        "cells": cells,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"results: {OUT_PATH}")


if __name__ == "__main__":
    main()
