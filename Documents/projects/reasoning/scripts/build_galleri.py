#!/usr/bin/env python3
"""
Build report/galleri.html — browsable gallery of 8 models × 10 prompts.
Reads from existing data files only. No API calls.

Usage:  python3 scripts/build_galleri.py
"""
from __future__ import annotations
import json, pathlib, html as H, statistics, sys, textwrap

PROJECT = pathlib.Path(__file__).parent.parent
RESULTS = PROJECT / "results"
OUT = PROJECT / "report/galleri.html"
OUT.parent.mkdir(exist_ok=True)

MODEL_ORDER = [
    "deepseek_v4", "glm_5_2", "kimi_k2_7", "gpt_5_5",
    "claude_sonnet_4_6", "gemma_4", "opus_4_8", "mistral_medium_3_5",
]
PROMPT_ORDER = [f"P{i}" for i in range(1, 11)]

ABBREV = {
    "deepseek_v4": "deepseek", "glm_5_2": "glm", "kimi_k2_7": "kimi",
    "gpt_5_5": "gpt-5.5", "claude_sonnet_4_6": "sonnet", "gemma_4": "gemma",
    "opus_4_8": "opus", "mistral_medium_3_5": "mistral",
}
MODEL_FULL = {
    "deepseek_v4": "DeepSeek V4", "glm_5_2": "GLM 5.2", "kimi_k2_7": "Kimi K2.7",
    "gpt_5_5": "GPT-5.5", "claude_sonnet_4_6": "Claude Sonnet 4.6",
    "gemma_4": "Gemma 4", "opus_4_8": "Claude Opus 4.8",
    "mistral_medium_3_5": "Mistral Med 3.5",
}
REGIME_BADGE = {
    "raw": ("raw", "#22c55e"),
    "raw_anchor": ("raw-a", "#86efac"),
    "summarized": ("sum", "#f59e0b"),
    "count_only": ("cnt", "#94a3b8"),
    "absent": ("abs", "#f87171"),
}
TRACE_STATUS_NOTE = {
    "summarized": "⚠ Spor er Anthropics SAMMENFATNING af CoT — ikke rå reasoning",
    "count_only": "⚠ Spor FRAVÆRENDE — kun token-antal eksponeret (GPT-5.5)",
    "absent": "⚠ Spor FRAVÆRENDE — model eksponerer ingen CoT-tekst",
    "raw_anchor": "ℹ Gemma: trace eksponeret, men ikke sammenlignelig med andre raw-modeller",
}
VERDICT_SYMBOL = {"correct": "✓", "partial": "½", "incorrect": "✗"}
VERDICT_COLOR = {"correct": "#22c55e", "partial": "#f59e0b", "incorrect": "#f87171"}

CURATED: dict[str, str] = {
    "deepseek_v4::P1": "Clerical optælling — 932 reas-tok på simpel forespørgsel",
    "glm_5_2::P9":     "Stramt trace — lav redundans, høj koherens",
    "kimi_k2_7::P9":   "Udskydende trace",
    "mistral_medium_3_5::P4": "§17-fejlen — forkert paragrafhenvisning for partshøring",
    "opus_4_8::P9":    "Adaptive nul — 0 reasoning-tokens; model sprang tænkning over",
}
for m in MODEL_ORDER:
    CURATED[f"{m}::P3"] = "Langfredag-taksonomi: 3. april 2026 = Langfredag"

# ── Load data ────────────────────────────────────────────────────────────────

def read_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

full = read_jsonl(RESULTS / "full/combined_8models_full.jsonl")
p2   = read_jsonl(RESULTS / "phase2/combined_8models_phase2.jsonl")
p3   = read_jsonl(RESULTS / "phase3/combined_8models_phase3.jsonl")

# Organise into cells[model::prompt]
cells: dict[str, dict] = {}
for r in full:
    k = f"{r['model_key']}::{r['prompt_id']}"
    cells[k] = {"economy": r, "legibility": [], "correctness": None}

for r in p2:
    k = f"{r['model_key']}::{r['prompt_id']}"
    if k in cells:
        cells[k]["legibility"].append(r)

for r in p3:
    k = f"{r['model_key']}::{r['prompt_id']}"
    if k in cells:
        cells[k]["correctness"] = r

# Per-prompt metadata (from first occurrence)
prompt_meta: dict[str, dict] = {}
for r in full:
    pid = r["prompt_id"]
    if pid not in prompt_meta:
        prompt_meta[pid] = {
            "type": r["prompt_type"],
            "probe": r["language_probe"],
            "load": r["reasoning_load"],
            "text": r["prompt"],
        }

# ── HTML helpers ─────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return H.escape(str(s), quote=True)

def badge(text: str, color: str, title: str = "") -> str:
    t = f' title="{esc(title)}"' if title else ""
    return (f'<span class="badge" style="background:{color};color:#fff"{t}>'
            f'{esc(text)}</span>')

def avg_legibility(scores: list[dict]) -> tuple[float | None, float | None]:
    reds = [r["scores"]["redundancy"] for r in scores if r.get("scores") and "redundancy" in r["scores"]]
    cohs = [r["scores"]["coherence"]  for r in scores if r.get("scores") and "coherence"  in r["scores"]]
    return (
        round(statistics.mean(reds), 1) if reds else None,
        round(statistics.mean(cohs), 1) if cohs else None,
    )

# ── Cell rendering ────────────────────────────────────────────────────────────

def render_cell(model: str, prompt: str) -> str:
    k = f"{model}::{prompt}"
    cell = cells.get(k)
    if cell is None:
        return '<td class="cell cell-missing"><span class="no-data">—</span></td>'

    eco  = cell["economy"]
    leg  = cell["legibility"]
    corr = cell["correctness"]

    regime   = eco.get("regime", "unknown")
    ts       = eco.get("trace_status", "?")
    reas_tok = eco["tokens"]["reasoning"]
    out_tok  = eco["tokens"]["output"]
    reas_src = eco["tokens"].get("reasoning_source", "?")
    trace    = eco.get("raw_reasoning_trace") or ""
    answer   = eco.get("answer_text") or ""
    cost     = eco.get("cost_usd", 0)
    lat      = eco.get("latency_s", 0)
    lm       = eco.get("language_metric") or {}
    lang     = lm.get("primary_trace_language") or "—"
    sw_count = lm.get("language_switch_count", 0)

    red_avg, coh_avg = avg_legibility(leg)
    is_curated = k in CURATED
    curated_note = CURATED.get(k, "")

    rb_text, rb_color = REGIME_BADGE.get(regime, ("?", "#64748b"))
    regime_b = badge(rb_text, rb_color, f"Regime: {regime}")
    ts_note  = TRACE_STATUS_NOTE.get(ts, "")

    # Correctness
    corr_html = ""
    if corr:
        v = corr.get("verdict", "?")
        vsym = VERDICT_SYMBOL.get(v, v)
        vcol = VERDICT_COLOR.get(v, "#94a3b8")
        j = corr.get("extracted_or_justification") or ""
        corr_html = f'<span class="corr" style="color:{vcol}" title="{esc(j[:200])}">{vsym}</span>'

    # Legibility badge
    leg_html = ""
    if red_avg is not None:
        leg_html = (f'<span class="score-leg" title="Redundans {red_avg}/5 · Koherens {coh_avg}/5">'
                    f'r:{red_avg} c:{coh_avg}</span>')

    # Language switch flag
    sw_flag = f'<span class="sw-warn" title="{sw_count} sprogskift">⚡{sw_count}</span>' if sw_count > 0 else ""

    # Reasoning chars
    reas_chars = len(trace)

    # Compact number formatting
    def fmt(n: int) -> str:
        return f"{n/1000:.1f}k" if n >= 1000 else str(n)

    # ── COLLAPSED (always visible) ──────────────────────────────────────────
    # Single status badge (regime_b is redundant when ts matches regime label)
    stats_tip = f"reas:{reas_tok} tok ({reas_src}) · out:{out_tok} tok · {reas_chars:,} chars · {lat:.2f}s"
    collapsed = f"""
<div class="cell-header">
  <span class="ts-badge ts-{ts}" title="trace_status: {ts} ({reas_src})">{esc(rb_text)}</span>
  <span class="lang-flag" title="Primær sporsprog: {esc(lang)}">{esc(lang)}{sw_flag}</span>
  {corr_html}{leg_html}
</div>
<div class="cell-stats" title="{esc(stats_tip)}">r:{fmt(reas_tok)} o:{fmt(out_tok)} {fmt(reas_chars)}ch · {lat:.1f}s</div>"""

    # ── EXPANDED (hidden until click) ────────────────────────────────────────
    # Regime warning
    warn_html = ""
    if ts_note:
        warn_html = f'<div class="trace-warning">{esc(ts_note)}</div>'

    # Trace
    if trace:
        trace_html = f'<pre class="trace-text">{esc(trace)}</pre>'
    else:
        placeholder = f"[{ts} — reasoning tekst ikke eksponeret]"
        trace_html = f'<pre class="trace-text trace-absent">{esc(placeholder)}</pre>'

    # Answer
    answer_html = f'<pre class="answer-text">{esc(answer)}</pre>' if answer else '<em class="no-data">Ingen svar</em>'

    # Phase 2 scores section
    leg_detail_html = ""
    if leg:
        rows_html = ""
        for lr in leg:
            judge = lr.get("judge", "?")
            sc = lr.get("scores") or {}
            red = sc.get("redundancy", "?")
            coh = sc.get("coherence", "?")
            just = lr.get("justifications") or {}
            rj = just.get("redundancy", "") if isinstance(just, dict) else ""
            cj = just.get("coherence", "") if isinstance(just, dict) else ""
            parse_note = "" if lr.get("parse_ok", True) else " ⚠ parse-fejl"
            rows_html += f"""
<tr>
  <td class="judge-name">{esc(judge)}{esc(parse_note)}</td>
  <td class="score-val">{red}</td>
  <td class="score-val">{coh}</td>
  <td class="just-text">{esc(rj[:120])}</td>
  <td class="just-text">{esc(cj[:120])}</td>
</tr>"""
        leg_detail_html = f"""
<details class="leg-section" open>
  <summary class="section-head">Phase 2 — Legibilitet (dommer)</summary>
  <table class="leg-table">
    <thead><tr><th>Dommer</th><th>Redundans/5</th><th>Koherens/5</th>
    <th>Redundans-begrundelse</th><th>Koherens-begrundelse</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</details>"""

    # Phase 3 section
    p3_detail_html = ""
    if corr:
        v = corr.get("verdict", "?")
        j = corr.get("extracted_or_justification") or "—"
        gm = corr.get("grading_method", "?")
        vcol = VERDICT_COLOR.get(v, "#94a3b8")
        vsym = VERDICT_SYMBOL.get(v, v)
        p3_detail_html = f"""
<details class="p3-section" open>
  <summary class="section-head">Phase 3 — Korrekthed</summary>
  <p><strong style="color:{vcol}">{esc(vsym)} {esc(v)}</strong>
  <span class="grading-method">({esc(gm)})</span></p>
  <p class="just-full">{esc(j[:500])}</p>
</details>"""

    # Curated note
    curated_html = ""
    if is_curated and curated_note:
        curated_html = f'<div class="curated-note">★ {esc(curated_note)}</div>'

    # Economy metadata
    eco_html = f"""
<details class="eco-section">
  <summary class="section-head">Økonomi-detaljer</summary>
  <table class="eco-table">
    <tr><td>Input tok</td><td>{eco["tokens"]["input"]}</td></tr>
    <tr><td>Reasoning tok</td><td>{reas_tok} <small>[{reas_src}]</small></td></tr>
    <tr><td>Output tok</td><td>{out_tok}</td></tr>
    <tr><td>Kost</td><td>${cost:.5f}</td></tr>
    <tr><td>Latens</td><td>{lat:.2f}s</td></tr>
    <tr><td>Model-version</td><td>{esc(eco.get("model_version","?"))}</td></tr>
  </table>
</details>"""

    expanded = f"""
<div class="expanded-body">
  {curated_html}
  {warn_html}
  <details class="trace-section" open>
    <summary class="section-head">Reasoning Trace
      <span class="stat-inline">({reas_tok} tok · {reas_chars:,} chars)</span>
    </summary>
    {trace_html}
  </details>
  <details class="answer-section" open>
    <summary class="section-head">Svar</summary>
    {answer_html}
  </details>
  {leg_detail_html}
  {p3_detail_html}
  {eco_html}
</div>"""

    curated_cls = " curated" if is_curated else ""
    data_attrs = (f'data-model="{model}" data-prompt="{prompt}" '
                  f'data-type="{eco.get("prompt_type","")}" '
                  f'data-regime="{regime}" data-ts="{ts}"')

    return f"""<td class="cell{curated_cls}" {data_attrs}>
  <div class="cell-inner" onclick="toggleCell(this)">
    <div class="collapsed">{collapsed}</div>
    <div class="expanded" style="display:none">{expanded}</div>
  </div>
</td>"""

# ── Build grid ────────────────────────────────────────────────────────────────

def render_grid() -> str:
    # <colgroup> — one <col> per column; JS changes width to expand/collapse
    col_prompt = '<col id="col-prompt" style="width:130px">'
    col_models = "".join(
        f'<col id="col-{m}" data-model="{m}" style="width:160px">'
        for m in MODEL_ORDER
    )
    colgroup = f'<colgroup>{col_prompt}{col_models}</colgroup>'

    # Model header row
    th_cells = '<th class="corner-cell"></th>'
    for m in MODEL_ORDER:
        abbr = ABBREV[m]
        full_name = MODEL_FULL[m]
        th_cells += (f'<th class="model-header" data-model="{m}">'
                     f'<span title="{esc(m)}">{esc(abbr)}</span>'
                     f'<br><small>{esc(full_name)}</small></th>')

    header_row = f'<tr class="header-row">{th_cells}</tr>'

    # Prompt rows
    body_rows = ""
    for pid in PROMPT_ORDER:
        meta = prompt_meta.get(pid, {})
        ptype = meta.get("type", "?")
        probe = meta.get("probe", "?")
        load  = meta.get("load", "?")
        ptext = meta.get("text", "")
        ptext_short = ptext[:80].replace("\n", " ")

        row_header = (f'<th class="prompt-header" data-prompt="{pid}">'
                      f'<span class="pid">{pid}</span>'
                      f'<br><span class="ptype" title="{esc(probe)}">{esc(ptype)}</span>'
                      f'<br><span class="pload">{esc(load)}</span>'
                      f'<br><span class="ptext-prev" title="{esc(ptext_short)}">'
                      f'{esc(ptext_short[:40])}…</span>'
                      f'</th>')

        row_cells = row_header
        for m in MODEL_ORDER:
            row_cells += render_cell(m, pid)

        body_rows += f'<tr class="prompt-row" data-prompt="{pid}" data-type="{esc(ptype)}">{row_cells}</tr>\n'

    return f"""
<div class="grid-wrap">
  <table class="gallery-grid" id="galleryGrid">
    {colgroup}
    <thead>{header_row}</thead>
    <tbody>{body_rows}</tbody>
  </table>
</div>"""

# ── Filter controls ───────────────────────────────────────────────────────────

def render_controls() -> str:
    # Model checkboxes
    model_checks = ""
    for m in MODEL_ORDER:
        abbr = ABBREV[m]
        model_checks += (f'<label class="check-label">'
                         f'<input type="checkbox" class="model-check" value="{m}" checked>'
                         f' {esc(abbr)}</label>')

    # Prompt checkboxes
    prompt_checks = ""
    for pid in PROMPT_ORDER:
        prompt_checks += (f'<label class="check-label">'
                          f'<input type="checkbox" class="prompt-check" value="{pid}" checked>'
                          f' {pid}</label>')

    # Prompt-type dropdown
    types = sorted({r["prompt_type"] for r in full})
    type_opts = '<option value="">Alle typer</option>'
    for t in types:
        type_opts += f'<option value="{esc(t)}">{esc(t)}</option>'

    return f"""
<div class="controls" id="controls">
  <div class="control-row">
    <span class="ctrl-label">Modeller:</span>
    <span class="check-group" id="modelChecks">{model_checks}</span>
    <button class="btn-sm" onclick="toggleAll('model-check', true)">Alle</button>
    <button class="btn-sm" onclick="toggleAll('model-check', false)">Ingen</button>
  </div>
  <div class="control-row">
    <span class="ctrl-label">Prompts:</span>
    <span class="check-group" id="promptChecks">{prompt_checks}</span>
    <button class="btn-sm" onclick="toggleAll('prompt-check', true)">Alle</button>
    <button class="btn-sm" onclick="toggleAll('prompt-check', false)">Ingen</button>
  </div>
  <div class="control-row">
    <span class="ctrl-label">Type:</span>
    <select id="typeFilter" onchange="applyFilters()">
      {type_opts}
    </select>
    <span class="ctrl-label" style="margin-left:1rem">Trace:</span>
    <select id="tsFilter" onchange="applyFilters()">
      <option value="">Alle trace-statusser</option>
      <option value="raw">raw</option>
      <option value="raw_anchor">raw_anchor</option>
      <option value="summarized">summarized</option>
      <option value="absent">absent</option>
      <option value="count_only">count_only</option>
    </select>
    <button id="curatedBtn" class="btn-curated" onclick="toggleCurated()"
            title="Fremhæv kuraterede eksempler">★ Kuraterede</button>
    <button class="btn-sm" onclick="collapseAll()">Fold alt ind</button>
    <button class="btn-sm" onclick="expandAll()">Fold alt ud</button>
  </div>
</div>"""

# ── JavaScript ────────────────────────────────────────────────────────────────

JS = r"""
const COL_W_COLLAPSED = '160px';
const COL_W_EXPANDED  = '480px';
let curatedActive = false;

function updateColWidth(model) {
  if (!model) return;
  const anyOpen = !!document.querySelector(
    `.cell[data-model="${model}"] .cell-inner.open`
  );
  const col = document.getElementById('col-' + model);
  if (col) col.style.width = anyOpen ? COL_W_EXPANDED : COL_W_COLLAPSED;
}

function toggleCell(inner) {
  const exp = inner.querySelector('.expanded');
  const isOpening = exp.style.display === 'none';
  exp.style.display = isOpening ? 'block' : 'none';
  inner.classList.toggle('open', isOpening);
  const td = inner.closest('td.cell');
  if (td) updateColWidth(td.dataset.model);
}

function applyFilters() {
  const activeModels = new Set(
    [...document.querySelectorAll('.model-check:checked')].map(x => x.value)
  );
  const activePrompts = new Set(
    [...document.querySelectorAll('.prompt-check:checked')].map(x => x.value)
  );
  const selType = document.getElementById('typeFilter').value;
  const selTs   = document.getElementById('tsFilter').value;

  // Show/hide model columns
  document.querySelectorAll('[data-model]').forEach(el => {
    const m = el.dataset.model;
    if (!m) return;
    const show = activeModels.has(m);
    el.style.display = show ? '' : 'none';
  });

  // Show/hide prompt rows — also hide if type/ts filter excludes them
  document.querySelectorAll('.prompt-row').forEach(row => {
    const pid = row.dataset.prompt;
    const ptype = row.dataset.type;
    let show = activePrompts.has(pid);
    if (selType && ptype !== selType) show = false;
    row.style.display = show ? '' : 'none';
  });

  // Trace-status filter: hide individual cells
  if (selTs) {
    document.querySelectorAll('.cell').forEach(cell => {
      const ts = cell.dataset.ts;
      cell.style.display = (ts === selTs) ? '' : 'none';
    });
  } else {
    document.querySelectorAll('.cell').forEach(cell => {
      // Restore display only if model column is active
      const m = cell.dataset.model;
      cell.style.display = activeModels.has(m) ? '' : 'none';
    });
  }
}

function toggleAll(cls, checked) {
  document.querySelectorAll('.' + cls).forEach(el => el.checked = checked);
  applyFilters();
}

function toggleCurated() {
  curatedActive = !curatedActive;
  document.getElementById('curatedBtn').classList.toggle('active', curatedActive);
  document.getElementById('galleryGrid').classList.toggle('curated-mode', curatedActive);
}

function collapseAll() {
  document.querySelectorAll('.cell-inner').forEach(inner => {
    inner.querySelector('.expanded').style.display = 'none';
    inner.classList.remove('open');
  });
  document.querySelectorAll('col[data-model]').forEach(col => {
    col.style.width = COL_W_COLLAPSED;
  });
}

function expandAll() {
  document.querySelectorAll('.cell-inner').forEach(inner => {
    inner.querySelector('.expanded').style.display = 'block';
    inner.classList.add('open');
  });
  document.querySelectorAll('col[data-model]').forEach(col => {
    col.style.width = COL_W_EXPANDED;
  });
}

// Wire up checkbox changes
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.model-check, .prompt-check').forEach(el => {
    el.addEventListener('change', applyFilters);
  });
});
"""

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px; background: #0f1117; color: #e2e8f0; line-height: 1.4;
}
a { color: #60a5fa; }

/* Controls */
.controls {
  position: sticky; top: 0; z-index: 100;
  background: #1e2130; border-bottom: 1px solid #334155;
  padding: 8px 12px; display: flex; flex-direction: column; gap: 6px;
}
.control-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctrl-label { font-weight: 600; color: #94a3b8; white-space: nowrap; min-width: 70px; }
.check-group { display: flex; gap: 6px; flex-wrap: wrap; }
.check-label { display: flex; align-items: center; gap: 3px;
  background: #1e293b; border: 1px solid #334155; border-radius: 4px;
  padding: 2px 6px; cursor: pointer; white-space: nowrap; }
.check-label:hover { border-color: #60a5fa; }
.btn-sm {
  padding: 3px 8px; border-radius: 4px; border: 1px solid #334155;
  background: #1e293b; color: #94a3b8; cursor: pointer; font-size: 11px;
}
.btn-sm:hover { border-color: #60a5fa; color: #e2e8f0; }
.btn-curated {
  padding: 3px 10px; border-radius: 4px; border: 1px solid #7c3aed;
  background: #1e1b4b; color: #a78bfa; cursor: pointer; font-size: 12px;
  font-weight: 600;
}
.btn-curated:hover, .btn-curated.active { background: #4c1d95; color: #e9d5ff; }

/* Page header */
.page-header {
  padding: 12px 16px 8px; border-bottom: 1px solid #1e293b;
}
.page-header h1 { font-size: 16px; color: #f1f5f9; }
.page-header p  { color: #64748b; font-size: 11px; margin-top: 3px; }

/* Grid — fixed-height scroll container so sticky thead works inside it */
.grid-wrap {
  overflow: auto;
  height: calc(100vh - 148px);
  border-top: 1px solid #1e293b;
}
.gallery-grid {
  border-collapse: collapse; min-width: 100%; table-layout: fixed;
}
.gallery-grid th, .gallery-grid td {
  border: 1px solid #1e293b; vertical-align: top;
}

/* Sticky column headers — stick at top of grid-wrap's own scroll.
   Width is controlled by <col> elements, not set here. */
.header-row th {
  position: sticky; top: 0; z-index: 10;
  background: #161b27; padding: 6px 8px; text-align: center;
  font-size: 12px; white-space: nowrap;
  border-bottom: 2px solid #334155;
  transition: width 0.15s ease;
}
.header-row .corner-cell {
  position: sticky; left: 0; top: 0; z-index: 20;
  background: #0f1117;
}
.header-row th small { color: #64748b; font-weight: 400; font-size: 10px; }

.prompt-header {
  position: sticky; left: 0; z-index: 5;
  background: #161b27; padding: 6px 8px;
  min-width: 130px; max-width: 130px; width: 130px;
  vertical-align: top; border-right: 2px solid #334155;
}
.pid { font-size: 15px; font-weight: 700; color: #f1f5f9; }
.ptype { font-size: 10px; color: #60a5fa; font-weight: 600; }
.pload { font-size: 10px; color: #94a3b8; }
.ptext-prev { font-size: 10px; color: #475569; display: block; margin-top: 4px; }

/* Cell — width controlled by <col>, no fixed constraints here */
.cell {
  padding: 0; vertical-align: top;
  transition: width 0.15s ease;
}
.cell-inner {
  cursor: pointer; padding: 6px;
  border: 2px solid transparent;
  border-radius: 2px;
  transition: border-color 0.1s;
}
.cell-inner:hover { border-color: #334155; }
.cell-inner.open  { border-color: #475569; background: #111827; cursor: default; }

.collapsed { }
.expanded  { cursor: default; }

/* Curated highlighting */
.curated-mode .curated .cell-inner {
  border-color: #7c3aed !important;
  background: #1a0533 !important;
  box-shadow: 0 0 0 1px #7c3aed inset;
}
.curated-note {
  background: #2d1b69; color: #c4b5fd; border-radius: 4px;
  padding: 5px 8px; font-size: 11px; margin-bottom: 8px; border-left: 3px solid #7c3aed;
}

/* Badges */
.badge {
  display: inline-block; font-size: 10px; font-weight: 700;
  padding: 1px 5px; border-radius: 3px; margin-right: 3px;
}
.ts-badge {
  display: inline-block; font-size: 10px; padding: 1px 4px;
  border-radius: 3px; margin-right: 3px; font-weight: 600;
}
.ts-raw       { background: #14532d; color: #86efac; }
.ts-raw_anchor { background: #052e16; color: #4ade80; }
.ts-summarized { background: #451a03; color: #fcd34d; }
.ts-count_only { background: #1e293b; color: #94a3b8; }
.ts-absent     { background: #450a0a; color: #fca5a5; }

.lang-flag { color: #94a3b8; font-size: 10px; }
.sw-warn   { color: #f59e0b; margin-left: 2px; font-size: 10px; }

/* Cell stats */
.cell-header { display: flex; align-items: center; flex-wrap: nowrap; gap: 3px; margin-bottom: 3px; overflow: hidden; }
.cell-stats { color: #64748b; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.corr   { font-weight: 700; font-size: 12px; margin-left: 2px; }
.score-leg { font-size: 10px; color: #a78bfa; }

/* Missing cell */
.cell-missing { background: #0a0f1a; text-align: center; color: #334155; }

/* Expanded body */
.expanded-body { padding-top: 6px; }

/* Trace warning */
.trace-warning {
  background: #1c1008; border-left: 3px solid #f59e0b;
  color: #fcd34d; font-size: 11px; padding: 5px 8px; margin-bottom: 6px;
  border-radius: 0 3px 3px 0;
}

/* Section details */
.section-head {
  font-size: 11px; font-weight: 700; color: #94a3b8; cursor: pointer;
  padding: 4px 0; letter-spacing: 0.05em; text-transform: uppercase;
  list-style: none; user-select: none;
}
.section-head:hover { color: #e2e8f0; }
.stat-inline { color: #475569; font-size: 10px; font-weight: 400; text-transform: none; }

/* Trace & answer */
.trace-text, .answer-text {
  font-family: "Fira Code", "Consolas", "Menlo", monospace;
  font-size: 11px; white-space: pre-wrap; word-break: break-word;
  background: #0a0e1a; color: #cbd5e1;
  padding: 8px; border-radius: 4px; margin-top: 4px;
  max-height: 400px; overflow-y: auto; line-height: 1.5;
  border: 1px solid #1e293b;
}
.trace-absent { color: #475569; font-style: italic; }
.answer-text { color: #d1fae5; background: #0a1f0f; }

/* Phase 2 / 3 tables */
.leg-section, .p3-section, .eco-section { margin-top: 6px; }
.leg-table, .eco-table {
  width: 100%; border-collapse: collapse; font-size: 10px; margin-top: 4px;
}
.leg-table th, .leg-table td,
.eco-table th, .eco-table td {
  padding: 3px 6px; border: 1px solid #1e293b; text-align: left;
}
.leg-table th { background: #1a2035; color: #94a3b8; }
.judge-name   { color: #7dd3fc; white-space: nowrap; }
.score-val    { text-align: center; font-weight: 700; color: #e2e8f0; }
.just-text    { color: #64748b; font-size: 10px; max-width: 120px; }
.grading-method { color: #475569; font-size: 10px; }
.just-full    { color: #94a3b8; font-size: 11px; margin-top: 4px; }
.eco-table td:first-child { color: #64748b; white-space: nowrap; }
.eco-table td:last-child  { font-weight: 600; }
.no-data { color: #334155; font-style: italic; }

/* Responsive — col widths handle sizing via JS; nothing to override here */
"""

# ── Final assembly ────────────────────────────────────────────────────────────

def build() -> str:
    controls = render_controls()
    grid     = render_grid()

    # Stats for page header
    n_raw = sum(1 for r in full if r.get("trace_status") == "raw")
    n_sum = sum(1 for r in full if r.get("trace_status") == "summarized")

    header = f"""
<div class="page-header">
  <h1>Reasoning Benchmark — Arbejdsgalleri (8 modeller × 10 prompts)</h1>
  <p>{len(full)} celler totalt · {n_raw} raw-trace · {n_sum} summarized
     · {len(p2)} legibilitetsvurderinger · {len(p3)} korrekthedsvurderinger
     · Klik en celle for at folde ud. ★-knap fremhæver kuraterede eksempler.</p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reasoning Galleri — 8 modeller</title>
<style>{CSS}</style>
</head>
<body>
{header}
{controls}
{grid}
<script>{JS}</script>
</body>
</html>"""

if __name__ == "__main__":
    print("Building galleri.html…", file=sys.stderr)
    html_content = build()
    OUT.write_text(html_content, encoding="utf-8")
    size_kb = OUT.stat().st_size // 1024
    print(f"Written: {OUT}  ({size_kb} KB)", file=sys.stderr)
