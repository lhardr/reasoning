# CC Brief — Phase 1 Pilot

## Context
Phase 0 harness is green: six models, locked reasoning effort, every reasoning value
tagged measured/estimated. Now we validate on real prompts before spending on the full run.
This pilot runs TWO prompts across the full panel, economy axis only. No judges, no
correctness scoring yet (those are Phase 2 and 3).

## Inputs
Add the provided prompt dataset to the repo at `data/prompts.yaml` (10 prompts, file
supplied). Only the `prompt` field is ever sent to a model. The `facit` field is blind,
reserved for Phase 3, and must NEVER appear in any request. Add a guard that strips/ignores
`facit` on the request path.

## What to run
Pilot on exactly two prompts, chosen to span the language probe:
- **P3** (da_legal, da_forcing) — should pull Danish legal terms into the trace.
- **P5** (math, da_framed_neutral) — Danish framing, language-neutral content; tests
  whether the trace stays English/symbolic or switches to Danish.

Run both across all six models (5 scored + Gemma anchor), using the locked
`experiment.reasoning_effort` from config. Economy axis only.

## What to capture and print
Per (model, prompt):
- input / reasoning / output token counts (separate), reasoning_share
- reasoning_source ("api" | "text_estimate")
- cost (using pricing.yaml + caching), latency
- trace_status, and SAVE the raw reasoning trace where exposed (raw/summarized) to
  `results/pilot/` so we can eyeball the language probe by hand.

## Assertions (fail loudly)
- reasoning_tokens > 0 for deepseek, glm, kimi, gemma on both prompts. If zero, FAIL.
- facit never present in any outgoing request (assert on the request path).

## Cost projection
After the pilot, print a projected cost for the FULL run (10 prompts × 6 models) based on
the pilot's per-model average cost per prompt. We decide go/no-go on the full run from this
number, so make it prominent.

## Out of scope (do NOT build)
- No legibility judges (Phase 2).
- No correctness scoring against facit (Phase 3).
- No language-detection metric yet — for the pilot we just save the raw traces and read
  them by hand; the automated language metric comes with the full run.

## Constraints
- python3. Read keys from env. Use the locked effort from config, never hardcode.
- Git hygiene: commit after each change, push, verify `git log origin/main..HEAD` empty
  before any deploy.

## Definition of done
- data/prompts.yaml loaded; facit-strip guard in place and asserted.
- Pilot runs P3 and P5 across all six models, prints the per-model economy table with
  reasoning_source, saves raw traces to results/pilot/.
- Non-zero-reasoning assertions pass.
- Full-run cost projection printed.
- Committed and pushed.
