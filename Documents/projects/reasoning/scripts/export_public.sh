#!/usr/bin/env bash
# Idempotent sync: private harness repo -> public export directory.
#
# Explicit include-list only (FILES_1TO1 + RENAMES below) — NEVER
# exclude-based. A new file added anywhere in this repo is invisible to
# this script by default; it only ever leaves if someone deliberately adds
# its path to one of the two lists below. That is the whole safety
# property this script exists to provide.
#
# Usage:
#   scripts/export_public.sh [DEST_DIR]
#   DEST_DIR defaults to ../reasoning-economy-harness (sibling directory).
#
# What it does:
#   1. rsync each listed file from this repo into DEST_DIR, preserving path
#      for FILES_1TO1 and remapping path for RENAMES.
#   2. Run the same three-layer secret/personal-reference grep used during
#      the initial public export over the synced result.
#   3. Exit non-zero (and print what matched) if anything hits. Exit 0 and
#      print a reminder to review the diff otherwise.
#
# What it deliberately does NOT do: commit, push, or touch git state in
# DEST_DIR at all. Review `git -C DEST_DIR diff`, then commit (and push, if
# desired) yourself. This script only ever writes files under DEST_DIR; it
# never runs git commands there.
#
# KNOWN GAP (read before relying on this for a real update): a one-time
# cleanup pass was applied directly in the public export directory after
# the initial sync (personal-name removal, dangling docs/ references
# removed, config_loader.py's data/ -> config/ path fix, adapter module
# renames to *_adapter.py, an __import__("os") cleanup, and upfront
# credential checks in run.py/run_phase3.py — see
# docs/cc_debrief_public_release.md for the full list). None of those
# edits exist in THIS (private) repo's source files, because this repo was
# left read-only during that pass. Running this script will overwrite the
# public copies of those specific files with the un-cleaned private
# content, silently reverting that pass. Before you trust an unattended
# run of this script: either port the equivalent edits into this repo's
# source files (then this script becomes a pure mechanical mirror again,
# as intended), or always read the diff this script leaves you before
# committing it — never sync-and-commit blind.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/../reasoning-economy-harness"
if [[ "${1:-}" != "" ]]; then
  DEST="$1"
fi

if [[ ! -d "$DEST/.git" ]]; then
  echo "ERROR: $DEST is not a git repository — refusing to sync into it." >&2
  echo "(This script only ever writes files; it never runs 'git init'.)" >&2
  exit 1
fi

# --- 1:1 path mirror (source path == dest path, relative to repo root) ---
FILES_1TO1=(
  analyse.py
  run.py
  run_phase2.py
  run_phase3.py
  run_auto_router.py
  run_opus5_panel.py
  run_langcost_k3_inkling.py
  requirements.txt
  .env.example
  config/panel.yaml
  config/pricing.yaml
  tests/__init__.py
  src/__init__.py
  src/accounting.py
  src/config_loader.py
  src/cost.py
  src/grader.py
  src/heavy_grader.py
  src/heavy_tasks.py
  src/judge_rubric.py
  src/judge.py
  src/language_metric.py
  src/metrics.py
  src/model_resolver.py
  src/report.py
  src/storage.py
  src/tool_loop.py
  src/tools.py
  src/adapters/__init__.py
  src/adapters/base.py
  src/adapters/anthropic_adapter.py
  src/adapters/google_adapter.py
  src/adapters/mistral_adapter.py
  src/adapters/openai_adapter.py
  scripts/compute_findings.py
)

# --- renamed / relocated paths: "source/relative/path dest/relative/path" ---
# (plain arrays instead of an associative array so this runs under bash 3.2,
# macOS's default — no `declare -A` portability risk.)
RENAMES=(
  "data/prompts.yaml config/prompts.yaml"
  "data/prompts_multilang.yaml config/prompts_multilang.yaml"
  "src/adapters/deepseek.py src/adapters/deepseek_adapter.py"
  "src/adapters/gemma.py src/adapters/gemma_adapter.py"
  "src/adapters/minimax.py src/adapters/minimax_adapter.py"
  "src/adapters/moonshot.py src/adapters/moonshot_adapter.py"
  "src/adapters/thinkingmachines.py src/adapters/thinkingmachines_adapter.py"
  "src/adapters/zai.py src/adapters/zai_adapter.py"
)

# NEVER synced from source — deliberately excluded (dead code / one-off /
# internal-only), or authored directly in the public repo and not sourced
# from here at all:
#   src/adapters/local.py            -- orphaned, never wired into PROVIDER_MAP
#   scripts/build_galleri.py         -- internal report builder, needs results/report/datasite
#   regrade_heavy_finance_interp.py  -- one-off patch for a specific historical run file
#   _smoke_test.py                   -- self-deleting temp script
#   data/heavy/*                     -- gitignored third-party download cache, not curated content
#   README.md, LICENSE, config/README.md, .gitignore, config/prompts*.yaml's header
#     comments -- authored/maintained directly in the public repo
#   scripts/make_data_release.py     -- reads from this repo's own results/ paths by
#     design; has no meaning inside the public repo, which never contains results/
#   CHANGELOG.md                     -- documents how to read THIS repo's own historical
#     result files; nothing in the public repo (no shipped results/) needs it yet
#   data_release/                    -- gitignored staged output, never committed anywhere

echo "==> Mirroring 1:1 files"
for f in "${FILES_1TO1[@]}"; do
  if [[ ! -f "$SRC/$f" ]]; then
    echo "ERROR: expected source file missing: $f" >&2
    exit 1
  fi
  mkdir -p "$DEST/$(dirname "$f")"
  rsync -a --checksum "$SRC/$f" "$DEST/$f"
done

echo "==> Mirroring renamed/relocated files"
for pair in "${RENAMES[@]}"; do
  src_rel="${pair%% *}"
  dest_rel="${pair#* }"
  if [[ ! -f "$SRC/$src_rel" ]]; then
    echo "ERROR: expected source file missing: $src_rel" >&2
    exit 1
  fi
  mkdir -p "$DEST/$(dirname "$dest_rel")"
  rsync -a --checksum "$SRC/$src_rel" "$DEST/$dest_rel"
done

echo "==> Secret / personal-reference scan on synced result"
HITS=0
cd "$DEST"

run_check() {
  local label="$1"
  local pattern="$2"
  local matches
  matches="$(grep -rInE "$pattern" . --exclude-dir=.git 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo
    echo "  HIT ($label):"
    echo "$matches" | sed 's/^/    /'
    HITS=1
  fi
}

run_check "api-key-pattern" 'sk-[a-zA-Z0-9_-]{8,}|sk-or-[a-zA-Z0-9_-]{8,}|sk-ant-[a-zA-Z0-9_-]{8,}|Bearer [A-Za-z0-9._-]{10,}|AIza[A-Za-z0-9_-]{10,}'
run_check "env-key-literal-assignment" '\b[A-Z][A-Z0-9_]*_(API_)?KEY\b[[:space:]]*=[[:space:]]*["'"'"'][A-Za-z0-9]{10,}["'"'"']'
run_check "personal-name" '\bLars\b|larsharder|Lars Harder'
run_check "personal-email" '[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo)\.[a-z]{2,}'
run_check "absolute-home-path" '/Users/[a-zA-Z]+|/home/[a-zA-Z]+'

if [[ "$HITS" -ne 0 ]]; then
  echo
  echo "Sync completed but the scan found the hit(s) above." >&2
  echo "Fix the SOURCE file(s) in the private repo and re-run this script — do not hand-edit the public copy only, or the next sync will reintroduce the same hit." >&2
  exit 1
fi

echo
echo "==> Clean. No secret or personal-reference hits."
echo "==> Now: cd $DEST && git diff   (review before committing)"
