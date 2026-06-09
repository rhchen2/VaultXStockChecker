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
- **Catalog ground truth (free, legal, excellent):** Scryfall + MTGJSON for MTG; PokemonTCG.io for Pokémon; YGOPRODeck for Yu-Gi-Oh.
- **Market prices:** a third-party aggregator API — shortlist **JustTCG** (condition/printing-specific prices, multiple refreshes/day), **TCGAPIs** (40+ games), **TCG API** (per-printing + sealed). Run a 2-week paid bake-off in Sprint 1; pick one primary + one fallback.
- **Direct integrations where APIs exist:** CardTrader and Cardmarket have real developer APIs — integrate later for both pricing *and* selling.
- Budget: **$100–$1,000/mo** early (aggregator tiers), revisit at scale.

### D2. Recognition: buy first, build later ("buy-then-build")
**Finding:** **Ximilar** sells a TCG-identification API claiming ~99% accuracy on MTG/Pokémon/Yu-Gi-Oh, with language-variant (EN/JP/CN) and edition handling, plus slab-label OCR. This is essentially SortSwift's moat available for rent.
**Decision:** launch on Ximilar (Business plan, per-call pricing) to hit M1 months sooner; instrument every scan (image + confirmed match) to accumulate our **own labeled training corpus**; revisit in-house model when scan volume makes per-call cost > ~1 FTE, or accuracy gaps appear on games Ximilar covers poorly. This converts a 🔴 30–60-week build into a 🟡 3–4-week integration **without losing the long-term option to in-source**.

### D3. Mobile stack: **React Native (Expo)**
Camera quality is sufficient (capture + upload; recognition is server-side). One codebase for shop app + consumer app. Native escape hatch via Expo modules if frame-rate capture becomes a bottleneck.

### D4. Launch games: **MTG + Pokémon** first (largest markets, best free data), Yu-Gi-Oh third.

### D5. Hardware: **skip for now.** Software + 0% commission is the wedge. Revisit Simple Sifter (low-cost appliance) after M3; Super Sorter not on roadmap.

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
| 0.5 | Scryfall/MTGJSON importer | Full MTG catalog (~90K cards, all printings/finishes) imported + idempotent re-run |
| 0.6 | PokemonTCG.io importer | Full Pokémon EN catalog imported; variant model covers reverse-holo/1st-ed |
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

### Sprints 9–10 (wk 17–20) — recognition + scan app → **Milestone M1**
| # | Ticket | Acceptance criteria |
|---|---|---|
| 1.10 | Recognition service (3.1 via D2) | `ScanJob` API: image in → Ximilar → mapped to our catalog variant + confidence; every scan + confirmation stored to S3 (training corpus) |
| 1.11 | Expo scan app (3.4) | Auto-capture viewfinder, flash, zoom; candidate overlay; 1-tap confirm → inventory; offline queue |
| 1.12 | Scan metering (3.10) | Per-store monthly scan counter; free-tier cutoff at 500 with upgrade prompt |
| 1.13 | **M1 demo** | 100-card mixed MTG/Pokémon pile scanned: ≥95% top-1 correct, each confirmed card auto-priced into inventory with timeline entry |

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

- **Sprints 19–28 (→ M3, V1 GA):** buylist portal + price math (7.1–7.4) · CardTrader + ManaPool + Square adapters (8.3–8.5) · TCGPlayer semi-sync Chrome extension (8.7 — see risk note) · reporting templates + builder (10.3–10.4) · staging/bins/transfers (4.2, 4.4–4.5) · pricing config hierarchy (5.7) · 10+ games (Yu-Gi-Oh, Lorcana, One Piece next).
- **Sprint 29+ (M4):** kiosk, consumer app (collections/trading), events, loyalty, consignment, AI assistant — sequenced by pilot-shop demand, not speculation.

---

## 7. Team & Budget (Phases 0–2)

| Role | Phase 0 | Phase 1 | Phase 2 |
|---|---|---|---|
| Full-stack TS (lead) | ✅ | ✅ | ✅ |
| Full-stack TS | ✅ | ✅ | ✅ |
| Backend/data eng | ✅ | ✅ | ✅ |
| Mobile (RN) | — | ✅ | ✅ |
| Integrations eng | — | — | ✅ (+1 by S15) |
| Design (contract) | ¼ | ¼ | ½ |

**Cost through M2:** ~36 weeks · 3→6 eng ≈ **$420K–$560K** loaded (US senior; 40–60% less blended/offshore) + **$500–$2K/mo** services (aggregator API, Ximilar per-scan, infra, Stripe/EasyPost pass-through). Within the $0.35–0.6M MVP envelope from the original analysis.

---

## 8. Top Risks & Mitigations (execution-level)

| Risk | Mitigation |
|---|---|
| Aggregator price API shut down / repriced (same fate as TCGPlayer's) | Two adapters behind one interface from day 1 (bake-off keeps the loser as fallback); snapshots are *ours* — historical data survives any cutoff |
| Ximilar dependency (cost or accuracy ceiling) | Every scan stored with confirmed label → in-house model is a funded option, not a rescue project; decision gate at 250K scans/mo |
| TCGPlayer semi-sync fragility (Phase 3) | Treat the Chrome extension as a *labeled-beta* module with its own on-call rotation; never in the M2 critical path |
| Oversell bugs destroy shop trust | Ledger concurrency tests in CI (ticket 2.4); pilot with one forgiving shop before GA |
| Scope creep toward SortSwift's alpha modules | Phase gates: nothing from §6 starts before M2 pilot signs off |

---

## 9. Immediate Next Actions (week 1)

1. Create the new `tcg-platform` repo from the §2 scaffold.
2. Sign up: JustTCG + TCGAPIs (bake-off keys), Ximilar Business trial, Scryfall/MTGJSON/PokemonTCG.io (free), Stripe + EasyPost test accounts.
3. Recruit 1–2 pilot shops now (they gate M2; lead time is long).
4. Start Sprint 1 tickets 0.1–0.4.
