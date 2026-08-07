# Changelog

Instrumentation/harness fixes only. Not a record of experiment runs (see
`docs/` for those) — this tracks changes to the measurement code itself,
which matter for interpreting historical result files correctly.

## 2026-08-07 — trace_status provider-awareness fix (tool_loop.py)

**Bug:** `src/tool_loop.py`'s shared OpenAI-dialect tool-calling loop
(`run_openai_tool_loop`, used by every adapter's `call_with_tools()` path,
including the Anthropic-family OpenRouter fallback) computed `trace_status`
purely from whether reasoning text was present in the response:
`"raw" if reasoning_text else ("count_only" if reasoning_tokens else
"absent")`. This is correct for open-weight models and for Google Gemini
(confirmed empirically: presence of text there does mean a genuine raw
trace), but wrong for Anthropic: Anthropic's API always returns a
*summary* of its reasoning, never the raw chain-of-thought, regardless of
route. Non-empty summarized text was therefore mislabeled `"raw"` on every
Anthropic-family row that went through a tool-invited call
(`--heavy`'s `invited_auto` condition, `--tools`/`--tools3`, and the
`invited_auto` condition in the standalone router scripts).

This was already documented as a known, unfixed defect —
`docs/reasoning_findings.md` §4.5 ("tool_loop.py-defekten er dokumenteret,
ikke rettet").

**Fix:** `src/adapters/base.py` gains `classify_provider_regime(resolved_model_id)`,
which classifies the model that actually answered (`resp.model` — not the
requested model id, so this also works correctly for router calls like
`openrouter/auto-beta` where the answering model is only known after the
response comes back) into `"summarized"` (Anthropic), `"count_only"`
(OpenAI's reasoning-model family), or `"raw"` (everything else — unchanged
default). `tool_loop.py`'s two `trace_status` assignment sites (no-tool-call
return, and the combined tool-called return) now call this instead of the
old presence-only check.

**Scope of the fix:** `src/tool_loop.py` and `src/adapters/base.py` only.
The single-call (non-tool) Anthropic paths in `src/adapters/anthropic_adapter.py`
already computed `trace_status` correctly (`"summarized" if reasoning else
"absent"`, hardcoded per-adapter) — they were never affected by this bug.
`src/adapters/local.py` (dead code, not wired into `PROVIDER_MAP`, never
called) has its own unrelated hardcoded `"raw"` and was left untouched.

**Historical result files are NOT touched or re-labeled by this fix.** Every
`--heavy`/`--tools`/`--tools3` run (and the `invited_auto` cells of both
`run_auto_router.py` and `run_auto_beta.py`) performed *before* this commit
carries the old, incorrect `trace_status="raw"` stamp on Anthropic-family
tool-invited rows. Per §4.5, read those historical rows as `summarized`
for Anthropic (Sonnet 4.6, Opus 4.8, Fable 5, Claude Opus 5, and any router
row that landed on one of them) — the register already carries this caveat;
re-labeling the historical files themselves is explicitly out of scope here
("Om-mærkning af de historiske Anthropic-rækker udestår i en separat arm").
Runs from this commit onward carry the corrected label directly.

## 2026-08-07 — reasoning_source persistence: verified, no change needed

Checked whether `reasoning_source` (the `ModelResponse` field recording
whether reasoning-token counts came from `"api"` usage metadata or a
`"text_estimate"` fallback split) reaches the saved JSONL rows. It already
does, in every `ModelResponse`-based save function in `src/storage.py`
(`save_result`, `save_langcost_result`, `save_tools_result`,
`save_variance_result`, `save_heavy_result` — each includes it inside the
row's `tokens` sub-object). `save_phase2_result` doesn't carry it because
Phase 2 records a `JudgeResponse`, not a `ModelResponse` — there is no
reasoning-token estimate to persist there. No code change was made.
