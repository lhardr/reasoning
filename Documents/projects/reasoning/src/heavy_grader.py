"""
--heavy phase correctness graders. Quality control, not the primary metric —
the phase measures HOW models solve heavy tasks (tokens, cost, tool behavior);
correctness is here so a cheap/fast row isn't mistaken for a good one.

code: extract the candidate function from the model's answer, execute it
against the official HumanEval test suite inside the SAME sandbox tools.py
uses for python_exec (network disabled, no persistent writes, 5s timeout) —
reusing the harness's own sandbox rather than a second one.

finance_calc / finance_interp: extract a numeric answer from free text and
compare against the FinQA facit with 1% relative tolerance. Free-text
extraction is inherently imperfect — every row logs raw_extracted_numbers so
the regex can be revised without re-running the experiment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .tools import execute_tool

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
_NUMBER_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*%?")

RELATIVE_TOLERANCE = 0.01


@dataclass
class GradeResult:
    correct: bool
    extracted_answer: str
    detail: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# code
# ---------------------------------------------------------------------------

def _extract_python_code(answer_text: str, entry_point: str) -> tuple[str, str]:
    """Returns (code, extraction_method) — method is logged for data-quality review."""
    blocks = _CODE_FENCE_RE.findall(answer_text)
    with_entry = [b for b in blocks if f"def {entry_point}" in b]
    if with_entry:
        return with_entry[-1], "fenced_with_entry_point"
    if blocks:
        return blocks[-1], "fenced_fallback_no_entry_point_match"
    if f"def {entry_point}" in answer_text:
        return answer_text, "raw_text_fallback"
    return answer_text, "raw_text_no_def_found"


def grade_code(answer_text: str, entry_point: str, test_code: str) -> GradeResult:
    code, extraction_method = _extract_python_code(answer_text, entry_point)
    full_code = f"{code}\n\n{test_code}\n\ncheck({entry_point})\n"
    result = execute_tool("python_exec", {"code": full_code})
    correct = result.get("error") is None
    return GradeResult(
        correct=correct,
        extracted_answer=code.strip()[:2000],
        detail={
            "extraction_method": extraction_method,
            "sandbox_error": result.get("error"),
            "sandbox_stdout": (result.get("stdout") or "")[:1000],
        },
    )


# ---------------------------------------------------------------------------
# finance_calc / finance_interp
# ---------------------------------------------------------------------------

def _parse_number(raw: str) -> Optional[float]:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    cleaned = cleaned.rstrip("%")
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        v = _parse_number(m.group())
        if v is not None:
            out.append(v)
    return out


def _relative_close(a: float, b: float, tol: float = RELATIVE_TOLERANCE) -> bool:
    if b == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) <= tol


def grade_finance(answer_text: str, facit_answer: str) -> GradeResult:
    """
    Primary heuristic: the LAST number in the answer is the model's final
    answer (matches "Final answer: X" instruction). Also checks whether ANY
    number in the text matches, for data-quality review when the primary
    heuristic and the tolerance check disagree.
    """
    facit_numeric = _parse_number(facit_answer)
    numbers = _extract_numbers(answer_text)
    primary = numbers[-1] if numbers else None
    correct = (
        primary is not None
        and facit_numeric is not None
        and _relative_close(primary, facit_numeric)
    )
    any_match = facit_numeric is not None and any(
        _relative_close(n, facit_numeric) for n in numbers
    )
    return GradeResult(
        correct=correct,
        extracted_answer=str(primary) if primary is not None else "",
        detail={
            "facit_numeric": facit_numeric,
            "raw_extracted_numbers": numbers[:20],
            "any_number_in_text_matches": any_match,
            "primary_matched": correct,
        },
    )


def grade(domain: str, answer_text: str, facit_grading: dict) -> GradeResult:
    """Dispatch by domain — code vs the two finance domains."""
    if domain == "code":
        return grade_code(answer_text, facit_grading["entry_point"], facit_grading["test"])
    return grade_finance(answer_text, facit_grading["answer"])
