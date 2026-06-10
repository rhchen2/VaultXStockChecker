# SortSwift Clone — Execution Plan (Sprint-Level)

> Third document in the series:
> 1. `SORTSWIFT_REVERSE_ENGINEERING.md` — what it is, feasibility, cost
> 2. `SORTSWIFT_FEATURE_MAP_AND_PLAN.md` — feature map, data model, phases
> 3. **This file** — resolved decisions, repo scaffold, sprint-by-sprint tickets with acceptance criteria for Phases 0–2 (the path to "first sellable").
>
> Feature IDs (e.g. `5.1`) reference the feature map in document 2.

---

## 1. Gating Decisions — RESOLVED

These were the open calls in Part G of the feature map. Resolved with research as of June 2026:

### D1. Price/catalog data: use aggregators + free per-game sources (not TCGPlayer direct)
**Finding:** TCGPlayer (eBay-owned) **closed its API to new developers in late 2024** — no application form, no waitlist, and existing keys are being deprecated. Direct access is not a viable plan; scraping their internal endpoints is a ToS/legal risk and explicitly avoided.
**Decision:**
- **Catalog ground truth (free/community):** PokemonTCG.io for Pokémon; **OPTCG API** (optcgapi.com — all sets OP-01→OP-15 + starter decks) for One Piece, with arjunkai/optcg-api as secondary. (Scryfall/MTGJSON for MTG when MTG is added later.)
- **Market prices:** a third-party aggregator API — shortlist **JustTCG** (condition/printing-specific prices, covers One Piece + Pokémon, multiple refreshes/day), **TCGAPIs** (40+ games), **TCG API** (per-printing + sealed). Run a 2-week paid bake-off in Sprint 1 **with One Piece coverage as a hard requirement**; pick one primary + one fallback.
- **Direct integrations where APIs exist:** CardTrader and Cardmarket have real developer APIs — integrate later for both pricing *and* selling.
- Budget: **$100–$1,000/mo** early (aggregator tiers), revisit at scale.

### D2. Recognition: piggyback on TCGPlayer's app scanner (scan → CSV export → import), own scanner later
**Owner decision (validated):** rather than building or licensing recognition for MVP, **use the TCGPlayer mobile app's free Scan & Identify as the recognizer**. Confirmed feasible: Scan & Identify supports **Pokémon and One Piece** (also MTG/YGO/Lorcana), and the app exports scanned lists as **CSV** — this is the officially documented workflow TCGPlayer itself promotes for importing into BinderPOS, so it is an accepted integration pattern, not a ToS-risky hack.
**Pipeline:** shop staff scan piles in the TCGPlayer app → export CSV → import via our column mapper, which auto-detects the TCGPlayer CSV format and maps to catalog variants (incl. condition/printing).
**Trade-offs accepted:** manual two-app workflow (no in-app camera at MVP); dependent on TCGPlayer keeping scan/export free and stable; no custom capture UX. **Mitigation/upgrade path:** the CSV importer is format-agnostic (ManaBox, Moxfield, BinderPOS exports also work), and an embedded scanner (Ximilar API ≈99% accuracy, or in-house) remains the Phase 3+ upgrade — slotting into the same `ScanJob` interface. This removes recognition entirely from the MVP critical path and cuts Phase 1 scope by ~6–8 eng-weeks.

### D3. Mobile stack: **React Native (Expo)** — deferred to Phase 3
With D2, no first-party scan app is needed at MVP; the shop dashboard is web. Expo RN remains the choice when the embedded scanner / consumer app arrives.

### D4. Launch games: **One Piece + Pokémon** (owner decision)
Pokémon = largest market, best free catalog data. One Piece = fast-growing and underserved by incumbents (a differentiation wedge). Both are covered by TCGPlayer Scan & Identify (D2) and JustTCG pricing. MTG and Yu-Gi-Oh follow in Phase 3.

### D5. Hardware: **shelved, with a DIY feasibility note kept warm (owner decision)**
Owner is interested in the feasibility of self-building a sorter but is shelving it for now. See **Appendix A** for a DIY Super-Sorter feasibility sketch so the option stays evaluated, not forgotten. Nothing hardware-related enters the software roadmap before M3.

### D6. Commission model: **0%, subscription-only** — matching SortSwift neutralizes their headline differentiator; we compete on price tiers and recognition UX.

---

## 2. Repository & Stack Scaffold

```
tcg-platform/                  (new monorepo)
├── apps/
│   ├── api/                   # NestJS (TypeScript) — REST + webhooks
│   ├── web/                   # Next.js — shop dashboard
│   ├── mobile/                # Expo RN — scan app (later: consumer app)
│   └── workers/               # queue consumers: reprice, sync, ingest
├── packages/
│   ├── db/                    # Prisma schema + migrations (Postgres)
│   ├── pricing-engine/        # pure-function rules pipeline (no I/O — unit-testable)
│   ├── catalog/               # importers: scryfall, mtgjson, pokemontcg.io
│   ├── market-data/           # aggregator adapters (justtcg | tcgapis), snapshot store
│   ├── channels/              # marketplace adapters: shopify, ebay, …
│   └── shared/                # types, auth, tenancy guards
├── infra/                     # Terraform/SST — Postgres, Redis, S3, queues, cron
└── .github/workflows/         # CI: typecheck, test, migrate-check, deploy
```

**Stack:** TypeScript end-to-end · Postgres (+ pgvector later) · Redis + BullMQ · S3 for scan images · Stripe (+ Terminal) · EasyPost · Expo RN · deployed on AWS (or Fly/Render until scale).
**Two load-bearing design rules:**
1. `pricing-engine` is **pure functions** (inventory item + rules + market snapshot → price + explanation trace). The explanation trace is what powers the dry-run simulator and investigator (5.9) for free.
2. `channels/*` adapters implement one interface (`pushListing`, `delist`, `pullOrders`, `webhook`) so the unified ledger (8.8) is written once.

---

## 3. Sprint Plan — Phase 0: Foundations (Sprints 1–4, weeks 1–8, 3 eng)

### Sprint 1 (wk 1–2) — skeleton + data bake-off
| # | Ticket | Acceptance criteria |
|---|---|---|
| 0.1 | Monorepo scaffold, CI, envs | `pnpm test` + typecheck green in CI; dev/staging deploy on merge |
| 0.2 | Tenancy + auth (1.1–1.2) | Store signup, JWT sessions, role guard (owner/manager/clerk); every table row carries `store_id`; cross-tenant access test fails closed |
| 0.3 | Catalog schema (2.1–2.2) | `CatalogCard` + `CatalogVariant` per data-model sketch; migration applied |
| 0.4 | **Aggregator bake-off** (D1) | JustTCG + TCGAPIs trialed against 200 known cards; report on coverage/freshness/price-accuracy; primary chosen |

### Sprint 2 (wk 3–4) — catalog import
| # | Ticket | Acceptance criteria |
|---|---|---|
| 0.5 | PokemonTCG.io importer | Full Pokémon EN catalog imported; variant model covers reverse-holo/1st-ed; idempotent re-run |
| 0.6 | One Piece importer (OPTCG API) | All OP sets + starter decks imported incl. alt-arts/manga rares/DON; secondary source cross-check |
| 0.7 | Card search API + UI | Autocomplete over both games <100 ms p95 (Postgres trigram or OpenSearch) |

### Sprint 3 (wk 5–6) — market data pipeline
| # | Ticket | Acceptance criteria |
|---|---|---|
| 0.8 | Aggregator adapter (2.4) | `market-data` fetches per-variant condition/printing prices for both games |
| 0.9 | Daily snapshot job (2.5) | Nightly cron persists `PriceSnapshot`; missing-data rate dashboarded; re-run safe |
| 0.10 | Price display | Card page shows latest market/low/mid per condition with source + timestamp |

### Sprint 4 (wk 7–8) — CSV in/out → **Milestone M0**
| # | Ticket | Acceptance criteria |
|---|---|---|
| 0.11 | CSV import + column mapper (3.8) | Upload arbitrary CSV → map columns UI → fuzzy-match to catalog → review screen of unmatched rows |
| 0.12 | CSV export (10.2 core) | Export inventory selection to CSV/XLSX with chosen columns |
| 0.13 | **M0 demo** | Import a 1,000-row list, see priced catalog matches; staging tenant live |

---

## 4. Sprint Plan — Phase 1: Price & Intake (Sprints 5–10, weeks 9–20, 4 eng)

### Sprints 5–6 (wk 9–12) — pricing engine core
| # | Ticket | Acceptance criteria |
|---|---|---|
| 1.1 | Rules pipeline (5.1) | Ordered steps: baseline → multipliers → offsets → guards → rounding; pure functions; 95%+ branch coverage |
| 1.2 | Baseline + fallback chains (5.2, 5.8) | 4-slot source fallback; follow/highest/lowest/average modes |
| 1.3 | Multipliers + guards + rounding (5.3, 5.5, 5.6) | Condition/printing/language multipliers; cost-plus floor, max-move cap, ceiling, override lock; 9 rounding modes incl. .49/.95/.99 |
| 1.4 | Explanation trace | Every computed price carries an ordered step-by-step trace (input → each step's delta → output) |

### Sprints 7–8 (wk 13–16) — inventory + manual intake
| # | Ticket | Acceptance criteria |
|---|---|---|
| 1.5 | Inventory model (4.1) | `InventoryItem` + event-sourced `InventoryEvent` timeline (4.7); qty/cost/bin/status |
| 1.6 | Swift-Add rapid entry (3.5) | Keyboard-first add: search → condition/printing hotkeys → enter; ≥6 cards/min sustained by a tester |
| 1.7 | Bulk ops (4.3) | Select-all-matching bulk edit/reprice/delete on 50K rows without timeout |
| 1.8 | Batch reprice job (5.10) | Nightly reprice of full store inventory; resumable; per-store rate caps |
| 1.9 | Dry-run simulator (5.9) | Run rule changes against live inventory with zero writes; diff view (old→new price per item) using the trace from 1.4 |

### Sprints 9–10 (wk 17–20) — TCGPlayer-scan intake pipeline → **Milestone M1**
| # | Ticket | Acceptance criteria |
|---|---|---|
| 1.10 | TCGPlayer CSV auto-detect import (D2) | TCGPlayer-app export CSV recognized automatically; rows mapped to catalog variants incl. condition/printing; ≥98% auto-match on a 200-card real export, rest queued for one-click review |
| 1.11 | Other-format importers | ManaBox / Moxfield / BinderPOS export formats auto-detected via same mapper; format fixtures in CI |
| 1.12 | Intake review queue | Unmatched/ambiguous rows resolved in a keyboard-first review UI; resolved mappings remembered per store |
| 1.13 | **M1 demo** | 100-card mixed One Piece/Pokémon pile scanned in TCGPlayer app → CSV → imported: ≥95% land as correct variants, each auto-priced into inventory with timeline entry |

---

## 5. Sprint Plan — Phase 2: Sell & Sync (Sprints 11–18, weeks 21–36, 5–6 eng)

### Sprints 11–12 (wk 21–24) — Shopify
| # | Ticket | Acceptance criteria |
|---|---|---|
| 2.1 | Channel adapter interface (8.x base) | `pushListing/delist/pullOrders/webhook` contract + sync-state machine per listing |
| 2.2 | Shopify push (8.1) | Inventory → Shopify products/variants incl. price + qty; metafields for card attrs; 10K-item store syncs <30 min |
| 2.3 | Shopify orders inbound | Order webhook → `Order` → auto stock deduction (8.9) → fulfillment status round-trip |

### Sprints 13–14 (wk 25–28) — unified ledger + POS core
| # | Ticket | Acceptance criteria |
|---|---|---|
| 2.4 | Unified ledger (8.8) | Single stock pool per item; channel sale triggers delist-everywhere; concurrency test: 2 simultaneous sales of last copy → exactly one succeeds, other auto-refund flagged |
| 2.5 | POS checkout (6.1) | Register UI: scan/search → cart → cash or card; receipt; till open/close |
| 2.6 | Stripe Terminal (6.3) | Card-present payment on physical reader in staging store |

### Sprints 15–16 (wk 29–32) — eBay
| # | Ticket | Acceptance criteria |
|---|---|---|
| 2.7 | eBay listing push (8.2) | Inventory → eBay listings (Sell API), category/condition mapping, ≤5-min qty updates |
| 2.8 | eBay orders/refunds inbound | Orders deduct via ledger; refunds restock with timeline event |

### Sprints 17–18 (wk 33–36) — fulfillment → **Milestone M2 (first sellable)**
| # | Ticket | Acceptance criteria |
|---|---|---|
| 2.9 | Store credit + gift cards (6.4) | Credit ledger; bi-directional Shopify customer-credit sync |
| 2.10 | Shipping labels (9.1) | EasyPost USPS/UPS/FedEx label purchase from order screen; tracking writeback to channel |
| 2.11 | Pick/pack queue (9.4) | Cross-channel unified pick list; pack → mark fulfilled everywhere |
| 2.12 | Label designer v1 (10.1) | Template editor with name/price/SKU/barcode elements; prints to common thermal sizes |
| 2.13 | **M2 pilot** | One real pilot shop runs 2 weeks: in-store + Shopify + eBay concurrently, zero oversells, ships real orders |

---

## 6. Phase 3+ (summary — detailed ticketing deferred until M2 learnings)

- **Sprints 19–28 (→ M3, V1 GA):** buylist portal + price math (7.1–7.4) · CardTrader + ManaPool + Square adapters (8.3–8.5) · TCGPlayer semi-sync Chrome extension (8.7 — see risk note) · **embedded first-party scanner** (Expo app + Ximilar or in-house, replacing the D2 two-app workflow) · reporting templates + builder (10.3–10.4) · staging/bins/transfers (4.2, 4.4–4.5) · pricing config hierarchy (5.7) · more games (MTG, Yu-Gi-Oh, Lorcana next).
- **Sprint 29+ (M4):** kiosk, consumer app (collections/trading), events, loyalty, consignment, AI assistant — sequenced by pilot-shop demand, not speculation.

---

## 7. Team & Budget (Phases 0–2)

| Role | Phase 0 | Phase 1 | Phase 2 |
|---|---|---|---|
| Full-stack TS (lead) | ✅ | ✅ | ✅ |
| Full-stack TS | ✅ | ✅ | ✅ |
| Backend/data eng | ✅ | ✅ | ✅ |
| Mobile (RN) | — | — | — (joins Phase 3 for embedded scanner) |
| Integrations eng | — | — | ✅ (+1 by S15) |
| Design (contract) | ¼ | ¼ | ½ |

**Cost through M2:** ~36 weeks · 3→5 eng ≈ **$380K–$520K** loaded (US senior; 40–60% less blended/offshore) + **$300–$1.5K/mo** services (aggregator API, infra, Stripe/EasyPost pass-through — no per-scan ML cost at MVP thanks to D2). Below the original $0.35–0.6M MVP envelope; the saving comes from removing recognition and the mobile app from the critical path.

---

## 8. Top Risks & Mitigations (execution-level)

| Risk | Mitigation |
|---|---|
| Aggregator price API shut down / repriced (same fate as TCGPlayer's) | Two adapters behind one interface from day 1 (bake-off keeps the loser as fallback); snapshots are *ours* — historical data survives any cutoff |
| TCGPlayer app changes/removes scan CSV export (D2 dependency) | Importer is format-agnostic (ManaBox/Moxfield/BinderPOS exports also accepted); embedded scanner (Ximilar/in-house) is the planned Phase 3 replacement, can be pulled forward if export breaks |
| One Piece catalog sources are community-run (OPTCG API) | Import to *our* schema with a secondary source cross-check (ticket 0.6); we own the data once imported |
| TCGPlayer semi-sync fragility (Phase 3) | Treat the Chrome extension as a *labeled-beta* module with its own on-call rotation; never in the M2 critical path |
| Oversell bugs destroy shop trust | Ledger concurrency tests in CI (ticket 2.4); pilot with one forgiving shop before GA |
| Scope creep toward SortSwift's alpha modules | Phase gates: nothing from §6 starts before M2 pilot signs off |

---

## 9. Immediate Next Actions (week 1)

1. Create the new `tcg-platform` repo from the §2 scaffold.
2. Sign up: JustTCG + TCGAPIs (bake-off keys — verify One Piece coverage first), PokemonTCG.io key, OPTCG API access, Stripe + EasyPost test accounts.
3. **Validate D2 end-to-end by hand:** scan 50 mixed One Piece + Pokémon cards in the TCGPlayer app, export the CSV, and document its exact columns/quirks (foils, alt-arts, Japanese cards) — this de-risks tickets 1.10–1.13 before any code.
4. Recruit 1–2 pilot shops now (they gate M2; lead time is long).
5. Start Sprint 1 tickets 0.1–0.4.

---

## Appendix A — DIY Super-Sorter Feasibility Sketch (shelved, on request)

A self-built card sorter is feasible as a hobby-grade project but is a serious robotics program at production grade. What it takes:

- **Mechanics:** card feeder (the hard part — singulating sleeved/unsleeved cards without damage; vacuum or friction-wheel feed), transport path, and a bin array. SortSwift uses 29 bins; a DIY v1 is realistic at 8–12 bins with a rotating chute or diverter gates.
- **Sensing/compute:** a global-shutter camera + ring light over the transport, Raspberry Pi 5 / Jetson Orin Nano running the recognizer (could call the same cloud `ScanJob` API as the software platform — reuse, not new ML).
- **Actuation:** stepper/servo drivers (grbl/Klipper-class controller), 3D-printed + laser-cut frame.
- **Realistic budget:** **$1.5K–$4K BOM** and **3–6 months of evenings** for a 1-card/2-sec, ~95%-feed-reliability prototype; the gap from there to a sellable product (jam recovery, foil/toploader handling, duty cycle, safety, support) is what makes SortSwift's unit a $0.5–2M program.
- **Verdict:** worth a weekend-scale spike *after* M2 only as R&D; never on the software critical path. Open-source prior art to study first: existing community card-sorter builds (search "MTG card sorter Raspberry Pi") and the Fujitsu-scanner Simple-Sifter pattern, which delivers 80% of the intake speedup at 5% of the effort.
