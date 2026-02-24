# Advisor Agent Plan

Design spec for an AI advisor agent to automate the match-rate improvement loop.

**Status:** Idea — team review pending.
**Related plan:** `C:\Users\Tony.Gilpin\.claude\plans\memoized-puzzling-kahan.md`

---

## Problem

The current improvement process is highly iterative and manual:

> Run matcher → check match rate → identify unmapped reasons → edit synonyms/category_mapping/noise phrases → re-run → repeat

---

## What the Agent Would Do

- Ingest the gap analysis report + unmapped output file
- Diagnose unmapped reasons by category (product filter / no match / no keywords / noise)
- Prioritise fixes by estimated URL yield (biggest wins first)
- Suggest specific edits: exact synonym pairs, category_mapping entries, noise phrases
- Validate suggestions against article content (Summary/Description) before proposing
- Apply fixes (patch files) and trigger a re-run, then report delta
- Repeat until target match rate reached or no further gains possible

---

## Key Inputs

| Input | Description |
|-------|-------------|
| `taxonomy_match_{CC}.xlsx` | Results sheet — unmapped rows |
| `TAXONOMY_GAP_ANALYSIS_REPORT_{CC}.xlsx` | Near-misses, never-matched topics |
| `countries/{CC}/synonyms.json`, `category_mapping.json` | Country config |
| `taxonomy.xlsx` | Full topic list |
| Target match rate | e.g. 80% |

---

## Key Tools

- `apply_synonym_patch.py` — apply synonym changes
- `apply_url_exclusions.py` — remove noise URLs from denominator
- `unmapped_review.html` exports — category fixes, synonym patches, noise phrases
- Gap Analysis report generation

---

## Design Considerations

- Should work per-country (BE, GB, NL, SE have different languages/taxonomies)
- Needs to distinguish fixable unmapped (synonyms, product mapping) from genuinely unmappable (off-topic content)
- Could run as a Claude Code sub-agent or standalone CLI tool
- Human-in-the-loop confirmation is important — agent should show evidence before applying
