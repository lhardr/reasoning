# Debrief: README hardening session (reasoning_source, Limitations, Known pitfalls, judge agreement)

Session scope: verify and document `reasoning_source` persistence, draft a
Limitations section, document the `FULL_MODEL_ORDER`/`TRACE_TEXT_MODELS`
freeze, and check inter-judge agreement on the canonical judge files. All
code/doc changes are committed and pushed to `origin/main`.

## What actually changed

1. **`reasoning_source`** — confirmed already persisted end-to-end (every
   `save_*` in `src/storage.py`), matching the 2026-08-07 CHANGELOG check.
   No code change. Documented in README's token-accounting table.
   Bagudfyldning: possible but low-value — only 33 rows across 11 Phase-0
   smoke-test files (all predate the field's introduction, commit
   `5eb17df`) lack it, and none feed any canonical dataset.
2. **README "Limitations" section (draft, points only)** — six sourced
   points: contamination (public HumanEval/FinQA heavy tasks vs.
   self-written Danish light prompts), OpenRouter's 7-14-backend routing
   lottery, n=1 on light, judge inter-agreement (see #4 below), the June
   run's route being inferred from `model_version`'s string shape
   (`via_openrouter`/`request_model_id` postdate it by ~3 weeks), and 4 of
   13 models' generating code being an uncommitted standalone script.
3. **README "Known pitfalls" section** — `FULL_MODEL_ORDER` and
   `TRACE_TEXT_MODELS` (`run.py`) are both frozen at the original 8 models.
   `TOOLS_MODELS`/`VARIANCE_MODELS`/`HEAVY_MODELS` are literally
   `= FULL_MODEL_ORDER`, so all four run modes share one gate. Consequence:
   a model added to `panel.yaml` alone is silently invisible to
   `--full`/`--tools`/`--variance`/`--heavy` (no error), and even when
   wired in via a side script, `kimi_k3`/`inkling` — which genuinely have
   raw traces — get scored as if they had none, because the language-metric
   call site branches on `TRACE_TEXT_MODELS` membership, not on whether a
   trace actually exists. Documented what to do instead: extend both lists
   together with any `panel.yaml` addition, rather than repeating the
   uncommitted-standalone-script pattern that produced the 4 unverifiable
   models in Limitations point 6.
4. **`scripts/check_judge_agreement.py`** (new, committed) — calls
   `src/judge.py`'s `compute_agreement()` against `datasite/data/judges-
   heavy.json` and `judges-light-new.json`, which never call it themselves.
   Findings: **11/55 heavy cells (20%)** and **7/20 light cells (35%)**
   high-disagreement (max per-dimension diff ≥2 on the 1-5 scale, the
   codebase's own threshold). Heavy disagreement is spread fairly evenly
   across tasks (code 5, finance_interp 3, finance_calc 3) and models (no
   model has more than 2). Light disagreement is concentrated:
   `kimi_k3` alone accounts for 5 of 7 (half its own 10 light cells),
   `inkling` the other 2. Also surfaced, unprompted: one judge entry is a
   parse-failure placeholder (`"minimax ⚠ parse-fejl"`, empty
   justification text) silently counted as a real score on
   `mistral_medium_3_5/finance_calc/invited_auto/pass4`; and a systematic
   leniency gap — `gemini_3_1_pro`'s mean coherence sits near ceiling
   across ALL judged cells (4.71 heavy / 4.95 light), not just the flagged
   ones, vs. `minimax`'s 3.83 / 3.90.

Commits (all pushed): `830d0c6`, `c2e676a`, `e92dc65`, `2da5d17`.

## Backlog (not done this session)

### 1. `compute_agreement()` still isn't called live
`scripts/check_judge_agreement.py` checks the canonical files after the
fact; it doesn't fix the underlying gap. The run path that actually
produces `judges-heavy.json`/`judges-light-new.json` still never calls
`compute_agreement()` or stores an `agreement` field, unlike the earlier
Phase 2 validation runs did. To close this: wire the call into whatever
produced those two files, and while there — decide what to do with the one
parse-failure placeholder entry found above (re-judge it or exclude it;
right now it's indistinguishable from a real score unless you grep the
judge name for "fejl").

### 2. Coherence dimension's status in published output
Investigated, not fixed. It's internally observed as low-signal
(`docs/cc_catchup_brief_phase2.md`: "Gemini gives near-flat scores
(coherence 5 on every prompt)" — reconfirmed this session, see #4 above),
and `docs/reasoning_findings.md` itself only cites it once (TEMA 6.2) and
immediately discounts it there. But it has leaked past internal docs:
`datasite/reasoning-data.json` bakes a flat `coherence` field into all 208
light-suite cells, and `Reasoning Explorer.html`/`.dc.html` (built for
artifact-hosting, per the `window.__resources` reference in the bundled
JS) render it as a live, sortable, highlighted table column labeled
"Coherence" with hint "1–5, higher is better" — a straight unweighted mean
of both judges, which #4's leniency-gap finding means is pulled upward by
`gemini_3_1_pro` specifically. `report/reasoning_rapport_v1.md`, the
narrative summary, and the public `data_release/` bundle are clean (the
latter explicitly excludes `datasite/`, per
`docs/cc_debrief_public_release.md`). Decision needed: relabel as
low-confidence in the UI, drop the column, or reconcile via
agreement-weighting once #1 is wired up.

### 3. The export scanner's two weaknesses
`scripts/export_public.sh`'s three-layer grep (lines ~147-172) is
narrower than it looks:
- **API-key pattern coverage**: `run_check "api-key-pattern"` only matches
  `sk-`, `sk-or-`, `sk-ant-`, `Bearer `, and `AIza` (Google) shapes, plus a
  generic `_KEY = "..."` literal-assignment pattern. The panel includes
  DeepSeek, Z.ai, Moonshot, Mistral, and Thinking Machines — none of those
  providers' key formats are covered, so a hardcoded key from any of them
  (in a comment, docstring, or example) would not be caught.
- **Personal-reference pattern is single-person-shaped**: `\bLars\b|
  larsharder|Lars Harder`, an email regex limited to
  `gmail|outlook|hotmail|yahoo`, and `/Users/[a-zA-Z]+|/home/[a-zA-Z]+`
  (bare-alphabetic usernames only — a username with a digit, hyphen, or
  underscore, e.g. most real macOS account names, would not match). A
  co-author's name, a work-domain email, or a differently-shaped username
  would all slip through silently.
Neither weakness is caught by the scanner's own "clean" exit — it would
report success on an export containing either kind of miss.

### 4. Private repo's facit → answer_key rename
The sibling public export (`../reasoning-economy-harness`) has `facit`
renamed to `answer_key`/`answer_key_grading` throughout —
`config/prompts.yaml`, `src/config_loader.py`, `src/heavy_tasks.py`,
`src/heavy_grader.py`, `src/grader.py` all use the new name consistently
in code and in the security-invariant docstrings/asserts. This repo (the
private original) still uses `facit` everywhere — the rename was done
**only** in the public directory, matching the "cleanup pass exists only
in the public export" gap already flagged in
`docs/cc_debrief_public_release.md`. What's new here: `export_public.sh`'s
`FILES_1TO1` list includes `src/config_loader.py`, `src/heavy_tasks.py`,
`src/heavy_grader.py`, and `src/grader.py` as straight 1:1 mirrors, and
`data/prompts.yaml → config/prompts.yaml` as a path-only `RENAMES` entry
(content untouched) — so **running the script today would silently
overwrite the public repo's `answer_key` naming back to `facit`** in both
the code and the data file, together and consistently (so it wouldn't
break at runtime), but it would revert a deliberate, documented rename
with zero warning. The script's own "KNOWN GAP" comment block (lines
24-40) lists personal-name removal, dangling docs references, the
`data/`→`config/` path fix, adapter renames, the `__import__` cleanup, and
credential checks as at-risk from a resync — it does **not** mention the
facit/answer_key rename, so anyone reading only that warning would miss
this one. Also found in passing: the public README (line ~261) says
"`answer_key`/`facit_grading` string" — `facit_grading` was never a real
field name; the actual one is `answer_key_grading`. Leftover half-edit,
worth a one-line fix whenever this is picked up.

### 5. Sync-list's test files
`export_public.sh`'s `FILES_1TO1` lists `tests/__init__.py` but not
`tests/test_compute_findings.py` — even though that file already exists,
byte-identical, in both repos (diffed clean this session). It got into the
public repo some other way (manual copy, presumably during the same
cleanup pass) and isn't tracked by the sync mechanism, so a future edit to
the private version won't propagate, and there's no record of why the
public copy already matches. Separately: `tests/test_answer_key_security.py`
exists **only** in the public repo — it tests the exact request-path
security invariant (`load_prompts()`/`load_multilang_prompts()` in
`src/config_loader.py` must strip the blind answer field before return)
using the new `answer_key` name. This repo has the identical runtime
`assert`-based guard (under the `facit` name) but **no automated test for
it at all** — the safety-critical property is only covered by a test in
the derived public copy, not the original it was copied from.

## What a future session should read first

1. `README.md`'s **Limitations** and **Known pitfalls** sections (both new
   this session) — the entry point for known gaps in this repo's data and
   run mechanics.
2. This file, for the backlog above — items 3-5 in particular touch a
   second repo (`../reasoning-economy-harness`) that this session only
   read, never modified; confirm it hasn't moved since before acting on
   them.
3. `docs/reasoning_findings.md`'s conventions block (top of file) — still
   the canonical statement of aggregation rules; nothing this session
   changed contradicts it.
4. `scripts/check_judge_agreement.py` — run it directly
   (`python3 scripts/check_judge_agreement.py`) rather than trusting this
   debrief's numbers if `judges-heavy.json`/`judges-light-new.json` have
   changed since 2026-08-11.
5. `scripts/export_public.sh` + `docs/cc_debrief_public_release.md` before
   touching anything sync-related (items 3-5) — the script's own
   "KNOWN GAP" header is necessary but, per item 4 above, not sufficient
   context on its own.
