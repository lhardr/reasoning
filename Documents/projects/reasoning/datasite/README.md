# datasite/

## Canonical data file

`datasite/reasoning-data.json` (root) is canonical. `datasite/data/reasoning-data.json`
is a byte-identical mirror kept only because the shipped HTML files
(`Reasoning Explorer.html`, `Reasoning Explorer.dc.html`) fetch the relative
path `data/reasoning-data.json`, which resolves against the root when those
files are served from `datasite/`.

**Rule: always edit the root file, then overwrite the `data/` copy with its
content.** Never edit `datasite/data/reasoning-data.json` directly — it will
silently diverge from the root and the two Explorer HTML files will serve
stale numbers.

```
cp "datasite/reasoning-data.json" "datasite/data/reasoning-data.json"
```

Rejected alternative: rewriting the HTML fetch paths to point at the root
directly. Not done because it's unclear whether every serving context for
these files (local file open, artifact host via `window.__resources`,
future static hosting) resolves relative paths the same way, and mirroring
the file is strictly lower-risk than touching the fetch call in two
independently-maintained HTML files.

## Other data files

- `datasite/data/judges-light-new.json` — legibility judge scores (minimax,
  gemini_3_1_pro) for the four new models' light-task (P1-P10) raw-trace
  cells. Not yet merged into `reasoning-data.json`.
- `datasite/data/judges-heavy.json` — same, for the 72 heavy-task cells (55
  judged, 17 have no raw trace to score). Not yet merged.

## Reference

`docs/reasoning_findings.md` is the authoritative register of verified
figures. No number shown in any file under `datasite/` should contradict it;
where the two disagree, the register wins and the datasite file is wrong.
