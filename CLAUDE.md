# CLAUDE.md — Project Context

This file is auto-loaded by Claude Code (desktop and web). It carries context
between sessions and machines. Keep it current.

## Standing convention (owner instruction)

**Whenever a set of instructions is completed, append a dated entry to
`SESSION_NOTES.md` (what was done, key learnings, open threads), update this
file if durable context changed, and commit + push** so the next session —
on any machine — can pick up where this one left off.

## What this repo is

Two things live here:

1. **VaultX stock checker (original purpose):** Python scripts that scrape
   vaultx.com stock (`scrape_vaultx.py`), build a static dashboard
   (`build_web_data.py`, `make_b2b_site.py`, output in `web/`), and track
   orders (`update_orders.py`). Daily snapshot commits land on `main`.

2. **SortSwift / TCG-platform project (active):** research + planning for
   building a TCG shop inventory/pricing platform inspired by SortSwift.
   This is the current focus. Owner: ryhchen2@gmail.com.

## SortSwift project — read these in order

| Doc | Contents |
|---|---|
| `SORTSWIFT_REVERSE_ENGINEERING.md` | Teardown of SortSwift: features, architecture guesses, feasibility, cost analysis |
| `SORTSWIFT_FEATURE_MAP_AND_PLAN.md` | Complete feature inventory + phased build plan |
| `SORTSWIFT_EXECUTION_PLAN.md` | **The operative plan.** Sprint-level tickets, milestones M1–M3, costs, risks. All gating decisions resolved. |

## Key decisions (owner-confirmed, do not re-litigate)

- **D1 — Pricing/catalog data:** TCGPlayer API is closed to new devs. Use
  aggregators (JustTCG primary candidate, TCGAPIs fallback — Sprint 1
  bake-off, One Piece coverage is a hard requirement). Catalog: PokemonTCG.io
  (Pokémon) + OPTCG API (One Piece).
- **D2 — Recognition:** no ML build/buy at MVP. Use the **TCGPlayer mobile
  app's free Scan & Identify → CSV export → our importer**. Validated: it
  supports One Piece + Pokémon and CSV export is TCGPlayer's own documented
  BinderPOS workflow. Embedded scanner (Ximilar or in-house) is the Phase 3
  upgrade.
- **D3 — Mobile:** React Native (Expo), deferred to Phase 3 (no app needed
  at MVP because of D2).
- **D4 — Launch games:** **One Piece + Pokémon.** MTG/Yu-Gi-Oh in Phase 3.
- **D5 — Hardware sorter:** shelved. Owner is curious about self-building;
  DIY feasibility sketch lives in Appendix A of the execution plan.

## Current state / where to pick up

- Branch `claude/sortswift-reverse-engineer-okpb18` holds all three SortSwift
  docs (not yet merged to `main`).
- Nothing of the platform is built yet. Week-1 actions are in
  `SORTSWIFT_EXECUTION_PLAN.md` §9 — notably: hand-scan ~50 One Piece/Pokémon
  cards in the TCGPlayer app and document the exported CSV's exact columns
  (de-risks the M1 intake pipeline before any code), API signups, and
  scaffolding a new `tcg-platform` repo (this repo stays scraper + docs).

## Session log

See `SESSION_NOTES.md` for the dated, append-only history of sessions,
decisions, and learnings.
