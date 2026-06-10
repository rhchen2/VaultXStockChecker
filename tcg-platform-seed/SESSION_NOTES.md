# Session Notes — append-only handoff log

Newest entries at the top. Each completed instruction set gets an entry:
what was done, learnings, open threads. See `CLAUDE.md` for durable context.

---

## 2026-06-10 (later) — Migrated project out of VaultXStockChecker into this repo

Owner directed that the SortSwift/TCG-platform work live in its own repo,
not the VaultX scraper. Docs (`SORTSWIFT_*.md`), `CLAUDE.md`, and this log
were moved here; the originals are being removed from the
`claude/sortswift-reverse-engineer-okpb18` branch of VaultXStockChecker,
which should be deleted without merging once this repo is confirmed pushed.
Note: the cloud session's GitHub integration could not create repos (403),
so the repo itself was created manually by the owner.

---

## 2026-06-10 — SortSwift research → execution plan (cloud session, originally on VaultXStockChecker branch `claude/sortswift-reverse-engineer-okpb18`)

### What was done
1. **`SORTSWIFT_REVERSE_ENGINEERING.md`** — full teardown of SortSwift
   (features, inferred architecture, feasibility, cost analysis).
2. **`SORTSWIFT_FEATURE_MAP_AND_PLAN.md`** — complete feature inventory and
   phased build plan.
3. **`SORTSWIFT_EXECUTION_PLAN.md`** — sprint-level plan with tickets,
   milestones M1–M3, team/cost model, risk table. Gating decisions D1–D5
   resolved with the owner and baked in (summarized in `CLAUDE.md`).

### Key learnings (verified by research, not assumption)
- **TCGPlayer's developer API is closed** to new applicants since late 2024;
  existing keys being deprecated. Plans must not depend on direct API access.
- **TCGPlayer's mobile app Scan & Identify supports One Piece and Pokémon**
  (also MTG/YGO/Lorcana) and exports scans as CSV. The CSV export → import
  flow is TCGPlayer's own documented BinderPOS workflow → safe to build on
  (this became decision D2: no recognition ML at MVP).
- **One Piece catalog data exists**: OPTCG API (optcgapi.com, OP-01→OP-15 +
  starter decks); arjunkai/optcg-api as secondary; JustTCG has One Piece
  prices. One Piece coverage made a hard requirement in the price-API
  bake-off.
- Dropping recognition + mobile app from MVP cut cost-through-M2 to
  ~$380K–$520K and the team to 3→5 engineers.

### Owner decisions of record
- Recognition via TCGPlayer scan→CSV→import (own scanner = Phase 3).
- Launch games: One Piece + Pokémon.
- Hardware sorter shelved; DIY feasibility sketch in execution plan
  Appendix A (~$1.5K–4K BOM hobby build; feeder is the hard part).

### Open threads / where to pick up
- **Week-1 actions** (execution plan §9): hand-scan ~50 One Piece/Pokémon
  cards in the TCGPlayer app and document the exported CSV's exact columns
  and quirks (foils, alt-arts, JP cards) — do this before writing importer
  code. Also: JustTCG/TCGAPIs bake-off signups, PokemonTCG.io + OPTCG API
  keys, Stripe/EasyPost test accounts, recruit 1–2 pilot shops.
- Scaffold a separate `tcg-platform` repo (this repo remains the VaultX
  scraper + planning docs).
- Branch not yet merged to `main`; no PR opened (owner hasn't asked).
