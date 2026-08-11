# Debrief: public-release export of the reasoning harness

**Nothing was published.** Everything below lives in a new sibling
directory, `../reasoning-economy-harness` (fresh `git init`, no remote
configured, no push run). This repo (the private working repo) was
read-only for the entire run except for this file and the new
`scripts/export_public.sh`, per the guards in the task.

Review this, then the checklist at the bottom, before you publish anything.

## What's in the public export

Fresh scoped copy, not a filtered git history — the old repo's history was
never touched or exported (see the history-scan section below for why that
matters).

```
reasoning-economy-harness/
├── README.md              (new)
├── LICENSE                 (new, MIT, Lars Harder / Nowable, 2026)
├── .gitignore               (new)
├── .env.example
├── requirements.txt
├── analyse.py
├── run.py, run_phase2.py, run_phase3.py,
│   run_auto_router.py, run_opus5_panel.py, run_langcost_k3_inkling.py
├── config/
│   ├── README.md            (new)
│   ├── panel.yaml
│   ├── pricing.yaml
│   ├── prompts.yaml          (moved from data/, header comments translated)
│   └── prompts_multilang.yaml (moved from data/, header comments translated)
├── src/                     (all modules except adapters/local.py — see below)
│   └── adapters/             (renamed to a consistent *_adapter.py suffix)
└── tests/                    (empty scaffold — __init__.py only, as it is here)
```

39 tracked files, 3 commits (raw export → cleanup pass → docs/license).

## What's excluded, and why

| Excluded | Reason |
|---|---|
| `docs/` (findings register, cc-briefs, handovers) | Internal method/results notes — explicitly out of scope per your instructions. |
| `results/`, `data/` (except the two prompt YAMLs), `datasite/`, `report/` | Run outputs and the internal results site — out of scope. `data/heavy/` specifically is a gitignored *download cache* (HumanEval/FinQA fetched on demand by `src/heavy_tasks.py`), not curated content, so excluding it costs nothing — a fresh clone re-downloads it automatically on first `--heavy` run. |
| `.claude/`, `__pycache__/`, `.DS_Store` | Tooling/build artifacts. |
| `reasoning_tokens_research_summary.md` | Internal, not in your scope list. |
| `scripts/build_galleri.py` | Judgment call — it only reads from `results/`/writes to `report/`, both excluded, and it's an internal HTML-gallery builder, not part of the harness itself. It would be dead weight (references directories that don't exist) in the public repo. |
| `regrade_heavy_finance_interp.py` | One-off correction script for historical `results/heavy/*.jsonl` files that predate a facit fix. The fix itself is already permanent in `src/heavy_tasks.py`/`src/heavy_grader.py` (both shipped) — this script only mattered for patching already-generated result files, which aren't shipped. |
| `_smoke_test.py` | Explicitly a temporary script (`"""Temporary smoke test — delete after confirming."""`) that deletes itself on run. Clearly not meant to survive. |
| `src/adapters/local.py` | Dead code — never imported by `src/adapters/__init__.py`, never in `PROVIDER_MAP`, and its `call()` signature doesn't even match `BaseAdapter`'s (missing `reasoning_effort`) so it would `TypeError` if anything ever called it. Deleted as part of the cleanup pass, not just left out of the copy. |

## Cleanup pass (no logic changes — verified by `py_compile` on every touched file)

- `src/config_loader.py`: `load_prompts()`/`load_multilang_prompts()` now
  read from `config/` instead of `data/`, matching the relocation above.
  Docstrings and cross-references in `run.py`, `run_opus5_panel.py`,
  `run_auto_router.py`, `run_langcost_k3_inkling.py`, `src/heavy_tasks.py`
  updated to match.
- Adapter modules renamed to a consistent `*_adapter.py` suffix
  (`deepseek`, `gemma`, `minimax`, `moonshot`, `thinkingmachines`, `zai` —
  `anthropic_adapter.py`/`google_adapter.py`/`mistral_adapter.py`/
  `openai_adapter.py` already had it). `src/adapters/__init__.py`'s imports
  updated accordingly.
- `src/adapters/anthropic_adapter.py`: replaced a stray
  `__import__("os").environ[...]` one-liner with a normal `import os`.
- **Fail-early gap closed**: `run_phase3.py`'s `main()` and `run.py`'s
  `run_judge()`/`run_validate_judges()` now check `OPENROUTER_API_KEY` up
  front and exit with a clear message before doing any work, instead of
  running P5/P6/P7's programmatic grades first and only then failing on the
  first LLM-graded prompt. Verified against the credential-handling review
  below.
- Removed personal-name references (5 instances of "Lars" in
  comments/docstrings/printed output, one of which was landing inside
  generated Phase 2 HTML report output, not just source) and dangling
  `docs/...` path references that don't exist in the public repo
  (`docs/legibilitets_rubrik.md`, `docs/forsoegsspec_sprog_omkostning_reasoning.md`,
  `docs/handover`, `docs/reasoning_findings.md`).
- Translated `config/prompts.yaml` / `config/prompts_multilang.yaml`
  header **comments** to English. Task content and `facit` values were left
  untouched — those are the actual Danish-language benchmark subject
  matter (and in the multilang file, deliberately trilingual), not
  boilerplate, and touching `facit` risked a real (if subtle) correctness
  change to grading, which was out of scope.

## Secret scan results

**Three layers, all clean on the final export.**

- **(a) Key-pattern grep** (`sk-`, `sk-or-`, `sk-ant-`, `Bearer `, `AIza`,
  literal `*_KEY = "..."` assignments) across the full export: zero real
  hits. Two harmless substring false-positives remain and are expected —
  `"task-dependent"` and `"Task-order-stable"` both happen to contain the
  literal substring `sk-`.
- **(b) Personal-reference grep** (`larsharder`, `Lars Harder`, email
  addresses, `/Users/...` paths, bare `Lars`): zero unintended hits. The
  only matches are the deliberate MIT copyright line and citation block in
  `LICENSE`/`README.md` — that's supposed to be there.
- **(c) Old repo git history scan** (`git log -p --all`, 62 commits, same
  pattern set plus filename/private-key/password sweeps): **clean**. `.env`
  itself was never committed at any point in history (verified via `git log
  --all --full-history -- .env`, empty). The one alarming-looking match
  batch (several `BSA...`-prefixed strings, which is the Brave Search key
  format) turned out to be coincidental substrings inside a base64-encoded,
  gzip-compressed `datasite/*.html` bundler-manifest blob — confirmed by
  checking the exact current `.env` key values against the full history
  (zero matches) and by inspecting the surrounding context (it's inside
  `"data":"H4sI..."`, a compressed JSON blob, not anywhere near an env-var
  assignment). No `.pem`/`.key`/`credential`/`secret`-named files were ever
  added at any point in history either.
  - **What this means for "can the old repo ever go public"**: content-wise,
    nothing blocks it — no secrets found anywhere in 62 commits of history.
    The real blocker is `docs/` (full of internal working notes, many with
    "Lars" mentioned directly, per the ~69 bare-`Lars` hits in history vs.
    only 6 in the 33 files reviewed for this export) and the fact that
    every one of the 62 commits carries your real name and Gmail address in
    its author metadata (`Lars Harder <hr.harder@gmail.com>`) regardless of
    file content — that's a git-history property, not something a
    `.gitignore` or file-level scan touches. If you ever want this repo
    itself public, that's a separate decision (squash/rewrite history and
    accept the personal git-author-metadata question, or just accept it —
    plenty of public repos carry a real name+email) — not something this
    export needed to resolve, since the export is a fresh-history copy, not
    a filtered version of this repo.

## Verification

- **Fresh clone + clean venv install**: `git clone` into a scratch
  directory, new venv, `pip install -r requirements.txt`, imports of every
  top-level dependency (`openai`, `anthropic`, `dotenv`, `yaml`, `requests`,
  `langdetect`) — all clean.
- **Dummy/missing-key behavior**: `python3 run.py --smoke` with no `.env`
  at all → every one of the 13 panel models prints a clear
  `SKIPPED — missing env var(s): ...` line, `exit 0`, `ALL CHECKS PASSED`
  (i.e. the run correctly recognizes "nothing runnable" isn't itself an
  error). With a syntactically-valid-but-fake `OPENROUTER_API_KEY` and a
  single model selected, the run stopped at `model_resolver.py`'s catalog
  check with a clear message and `exit 1` — no raw traceback either way.
- **One real end-to-end call**: your local `.env` (real keys) does exist,
  so I ran it — **but not against `gemma_4`**. Its `openrouter_model_id`
  pin (`google/gemma-4-31b-it-20260402`) is now stale on OpenRouter's live
  catalog (pins do go stale — this is expected, documented behavior in
  `panel.yaml`'s own comments, not an export bug; 8 of the 13 dated pins
  failed the same live catalog check on 2026-08-05). I substituted
  `claude_sonnet_4_6` (resolves via the direct Anthropic route, so it
  sidesteps the stale-pin issue entirely) for the one real call instead:
  `python3 run.py --smoke --model claude_sonnet_4_6` → real response, 29
  input / 85 reasoning / 159 output tokens, **$0.00375**, 6.04s,
  `TraceStatus PASS`, correct JSONL written. Confirms the full adapter →
  API → cost-accounting → storage pipeline works end-to-end in the export.
  Your real `.env` was copied into an isolated scratch clone for this one
  test only, never into the actual public export directory, and was
  deleted immediately after (verified: `git status` in the public export
  directory was clean throughout, and no `results/`/`.env` ever touched
  it).
  - **Flag for you**: several dated OpenRouter pins in `config/panel.yaml`
    are stale as of 2026-08-05 (`deepseek_v4`, `glm_5_2`, `kimi_k2_7`,
    `gpt_5_5`, `gemma_4`, `mistral_medium_3_5`, `kimi_k3`, `inkling` all
    failed the live catalog check; `claude_sonnet_4_6`, `opus_4_8`,
    `fable_5`, `claude_opus_5` resolve fine via the direct route;
    `gpt_5_6_sol` resolves fine via OpenRouter since it's an undated slug).
    This is a private-repo data-freshness question, not something this
    export changed or should fix — just worth knowing before you run
    anything for real, in either repo.
- **Final grep report**: re-ran all three scan layers on the finished
  export after the cleanup pass and doc-writing — zero unintended hits
  (see Secret scan results above).

## `scripts/export_public.sh` (new, in this repo)

Idempotent sync script for future updates: edit source files here, run the
script, review the diff it leaves in the public directory, commit (and push,
if you want) there yourself. Explicit include-list (`FILES_1TO1` +
`RENAMES` arrays in the script) — never exclude-based, so a new file added
anywhere in this repo is invisible to it by default. Runs the same
three-layer secret/personal-reference scan on the synced result and exits
non-zero if anything hits.

**Important known gap, and I verified it's real, not theoretical**: this
cleanup pass's edits (Lars-name removal, dangling `docs/` references
removed, the `data/`→`config/` path fix, adapter renames, the `__import__`
cleanup, the upfront credential checks) exist **only** in the public
export directory — I was not permitted to touch this repo's source this
run. I test-ran the script against a throwaway copy (never the real public
directory) and confirmed: it *would* silently reintroduce every one of the
5 "Lars" mentions on a real sync, because this repo's `run.py`,
`run_phase3.py`, `src/report.py`, and `src/adapters/mistral_adapter.py`
still have the original text. The script's own secret-scan step caught this
and exited 1 rather than letting it through — so it fails safe — but you
should still either (a) port the small set of edits listed under "Cleanup
pass" above into this repo's actual source files (then the script goes back
to being a pure mechanical mirror), or (b) always read the script's output
and the diff before committing, never sync-and-commit blind.

## Open items / judgment calls worth a second look

- **FinQA license**: I cited FinQA in the README/task-set docs but did not
  independently verify its license terms (unlike HumanEval, which is
  confirmed MIT). Worth a five-minute check against FinQA's own repository
  before publishing, since the README currently says "verify FinQA's
  license before redistributing beyond benchmarking use" rather than
  asserting a specific license.
- **`src/judge_rubric.py` vs. `src/judge.py`'s built-in rubric**: flagged by
  the recon pass as possibly redundant (both templates already read as
  "anchored," and `judge_rubric.py`'s docstring describes replacing a
  "loose" version that `judge.py` no longer seems to have). I left this
  alone — determining whether they're actually equivalent needs domain
  judgment about rubric semantics, not a mechanical check, and touching it
  would have been a logic change, out of scope for this pass. Worth you
  taking a look.
- **Cost-warning figures in the README** are pulled from real measured
  totals in this repo's own `docs/cc_debrief_*.md` files (Opus 5 addition:
  $0.89/40 calls; heavy recap: $1.06/70 calls; auto-router: $1.11/80 calls;
  Mistral recap: $0.22/10 calls) extrapolated to "tens of dollars" for a
  full 12+1-model, all-phases run — that extrapolation is mine, not a
  measured figure, since no single historical run covers the entire panel
  across every phase at once. Worth sanity-checking against your own sense
  of what a full run has actually cost, if you've ever run one end to end.
- **`tests/` is genuinely empty** (just `__init__.py`, matching this repo)
  — included per your explicit scope, but there's no real test coverage to
  advertise. The README doesn't claim any.

## Checklist before you publish

- [x] Repo name — resolved 2026-08-11: published as
      `nowable-tech/reasoning-economy-harness` (renamed from the initial
      `reasoning-harness-public` once the "public" suffix was dropped).
      Citation URL in README.md is current.
- [ ] GitHub org/account to publish under.
- [ ] Essay link(s) — README's "What this is" section has a `(link: TBD)`
      placeholder for the Nowable essay series.
- [ ] Confirm the MIT license text and "Lars Harder / Nowable, 2026"
      copyright line in `LICENSE` are what you want (verbatim, as
      requested — I didn't add a contributor list or anything beyond the
      standard MIT template).
- [ ] Decide on the FinQA license question above before publishing the
      heavy-suite task content.
- [ ] Either port the cleanup-pass edits upstream into this repo, or commit
      to always reviewing `export_public.sh`'s diff before pushing future
      updates (see the known-gap note above).
- [ ] `config/panel.yaml`'s stale dated pins (see Verification above) —
      not blocking for publishing the *code*, but worth knowing that a
      fresh clone's `--smoke` won't fully pass today without a pin refresh.
- [ ] Actually `git push` to the remote of your choice — this run created
      no remote and pushed nothing, exactly as instructed.
