# SortSwift — Complete Reverse-Engineering, Feasibility & Cost Analysis

> Target: `https://app.sortswift.com/` (marketing at `https://sortswift.com/`)
> Prepared: 2026-06-09
> Purpose: Full teardown of every feature, with build feasibility and cost estimates, to inform a from-scratch rebuild in a separate repository.

---

## 1. Executive Summary

**What it is.** SortSwift is an all-in-one vertical SaaS + hardware platform for trading-card-game (TCG) retail shops ("LGS" — local game stores). It collapses what is normally 5–8 separate tools (inventory, POS, card-scanning/recognition, automated repricing, buylist, multi-marketplace sync, shipping, events) into a single system, and layers proprietary scanning hardware on top.

**Scale they claim.** 600+ live shops, $100M+ in card sales processed, 86M+ SKUs catalogued, 257,000 products repriced every 12 hours, 0% commission (their headline differentiator vs. competitors charging 2–2.5%).

**The core insight.** TCG retail is brutal because a single physical card maps to a multi-dimensional SKU (game × set × card × condition × language × printing/foil × grade), prices move daily, and shops sell the same item across many marketplaces simultaneously. SortSwift's moat is (a) fast, accurate **card recognition** (scan a messy pile, no pre-sorting), (b) a deep **rules-based repricing engine**, and (c) **bi-directional sync** to every marketplace at once — plus optional **robotic sorting hardware** (the "Super Sorter").

**Build verdict.** The *software* is a large but conventional SaaS build — feasible for a small senior team. The genuinely hard / expensive parts are:
1. The **card-recognition ML pipeline + catalog data** (the real moat).
2. **Marketplace integrations** (each one is a multi-week reverse-engineering + maintenance burden; eBay/Shopify are documented, TCGPlayer notably is *not* fully open which is why SortSwift uses a "semi-sync" Chrome extension).
3. The **hardware** (Super Sorter), which is a separate robotics/manufacturing company in disguise.

**Rough cost to a credible MVP** (scan → price → inventory → sync to Shopify + eBay + POS): **~6–9 months, 3–4 engineers, ~$350K–$600K** all-in. **Full feature parity** (everything in §4): **18–30 months, $2.5M–$5M+** including data licensing and hardware R&D. Ongoing infra+data is modest (**~$3K–$15K/mo** until significant scale).

---

## 2. Product Architecture (Inferred)

No source code is exposed; the following is reverse-engineered from behavior, feature surface, and the marketing/docs site.

**Frontend.** `app.sortswift.com` is a single-page web app (separate host from the marketing site `sortswift.com`). Behavior is consistent with a React/Next.js SPA talking to a JSON/REST + webhook backend. Marketing site is statically generated (per-feature routes like `/features/inventory`, `/features/autopricing`).

**Backend (inferred shape).**
- Multi-tenant SaaS, one logical store = one tenant, with **per-store** configuration for pricing, channels, registers, kiosks.
- A **canonical card catalog** (86M+ SKUs) — the master product database mapping every game/set/card/variant, kept in sync with external price providers.
- A **pricing engine** that runs as a scheduled batch job ("every 12 hours", "market data refreshes daily") plus on-demand single/bulk reprice. This is a rules pipeline (22+ ordered steps) evaluated per item per channel.
- A **sync layer** with per-marketplace adapters, webhooks inbound (orders/refunds), and push outbound (listings/inventory), plus a "unified ledger" reconciling stock across channels.
- An **ingestion/recognition service** receiving images from the mobile app / document scanners / hardware, returning candidate card matches.
- Mobile apps (iOS/Android) — likely React Native or Flutter given the shared "any smartphone" + web parity messaging.
- Payments via **Stripe** (Stripe Terminal for POS card-present; prepaid "wallet" for shipping).

**Data providers consumed.** TCGPlayer, Cardmarket, CardTrader, ManaPool, Card Kingdom (5–7 price sources). These are the lifeblood — pricing and catalog both depend on them.

**Hardware tier.** "Simple Sifter" = Raspberry Pi appliance driving up to 4 Fujitsu document scanners into the ingestion API. "Super Sorter" = 29-bin electromechanical sorting robot with its own recognition camera, USA-manufactured, low unit count (11 active / 26 ordered) — clearly early-stage hardware.

---

## 3. Competitive Context

Primary incumbents SortSwift positions against: **BinderPOS**, **CrystalCommerce**, **TCGplayer's Pro/POS tooling**, and Shopify-plus-spreadsheets setups. The wedge is **0% commission** + **scanning speed** + **all-in-one**. Crucial implication for a rebuild: the market is *already served* by entrenched players, so a clone competes on the same two axes (recognition quality, breadth of integrations) where SortSwift itself is strongest.

---

## 4. Complete Feature Inventory (Every Feature) + Per-Feature Feasibility

Legend — **Feasibility** = how hard to build well: 🟢 Easy / 🟡 Moderate / 🟠 Hard / 🔴 Very hard (moat). **Effort** in senior-engineer-weeks for a production-quality version (not a toy).

### 4.1 Card Recognition & Intake (the moat)

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| AI card recognition, "26+ TCGs @ 99.9%" | Image → identify game/set/card. Needs a labeled catalog of card images + an embedding/match model or OCR+visual hash hybrid. Real accuracy at this breadth is the hardest single thing in the product. | 🔴 | 30–60 wk + ongoing |
| Automatic **foil / printing** detection | Detecting foil from a single phone frame (glare/angle) is genuinely hard ML. | 🔴 | 8–16 wk |
| Automatic **language** detection (e.g. JP Pokémon) | Classifier or OCR-script detection; flag non-English for review. | 🟠 | 4–8 wk |
| Auto-capture mode + viewfinder + flash + pinch-zoom | Mobile camera UX around the recognizer. | 🟡 | 4–6 wk |
| **Swift Add** (keyboard rapid entry, hotkey remap, queue) | Power-user manual intake; no ML, just fast UX + autocomplete over catalog. | 🟢 | 2–4 wk |
| **File Upload** via document scanner batches | Accept multi-card scan sheets, segment into individual cards, recognize each. Segmentation is non-trivial. | 🟠 | 6–10 wk |
| **UPC scanner** for sealed/supplies | Barcode → product lookup. Standard. | 🟢 | 1–2 wk |
| **CSV import** from any marketplace format | Point-and-click column mapper + fuzzy matching to catalog. | 🟡 | 3–5 wk |
| Chaos sorting ("scan without pre-sorting by set") | This is a *workflow* enabled by good recognition + bin tagging, not separate tech. | 🟡 | 2–4 wk |

### 4.2 Canonical Catalog & Pricing Data

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Master catalog, 86M+ SKUs, 55+ games | Build + maintain a normalized multi-game card DB with all variants. Sourcing/licensing data is the constraint, not code. | 🟠 | 12–20 wk + licensing |
| 5–7 price sources ingested daily | Adapters to TCGPlayer/Cardmarket/CardTrader/ManaPool/Card Kingdom + nightly refresh of 257K+ products. API access/ToS per source varies. | 🟠 | 8–14 wk |
| Graded pricing (beta) | Grade-aware comparables (PSA/BGS ladders). Separate data feed. | 🟠 | 6–10 wk |
| Sealed product as first-class type | Modeling boxes/cases distinctly from singles. | 🟢 | 2–3 wk |

### 4.3 Autopricing Engine

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| 22+ drag-and-drop ordered pricing **steps** | Rules pipeline: Source/Baseline → Attribute modifiers → Offsets → Guards/Floors → Rounding. Conceptually a per-item interpreter. | 🟡 | 8–12 wk |
| 4-slot **fallback chains** for missing data | Cascade through sources. | 🟢 | 1–2 wk |
| Baseline selection (Market/Mid/Low/Direct Low) | Pick a point off source data. | 🟢 | 1 wk |
| Condition/rarity/printing/language/age **multipliers** | Per-attribute % adjustments. | 🟢 | 2–3 wk |
| Offsets: fixed $, %, **time-limited** (auto-expiring) flash sales | Scheduling + expiry. | 🟡 | 2–4 wk |
| Guards/Floors: override locks, max-move caps, cost-plus floors, cross-marketplace buylist floors, ceilings | The "don't sell below cost / don't tank price" safety logic. | 🟡 | 3–5 wk |
| Rounding: 9 modes incl. psychological (.49/.95/.99) | Trivial. | 🟢 | 1 wk |
| Config hierarchy: per **platform × set-group × card-list × price-range** | Independent strategies per channel; 8 channels, unlimited set-filter groups. Combinatorial config UI is the real work. | 🟠 | 6–10 wk |
| Marketplace-selection modes (Follow Fallbacks / Highest / Lowest / Average) | Aggregation across sources. | 🟢 | 1–2 wk |
| **Dry-run simulator** + Investigator (debug one card) | Explain *why* an item priced as it did — big UX value, real engineering. | 🟡 | 4–6 wk |
| Nightly/12h batch reprice of 250K+ products + on-demand bulk | Scalable batch jobs; idempotent, resumable. | 🟡 | 4–6 wk |

### 4.4 Inventory Management

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Multi-variant stock (condition/lang/printing/foil) | Core data model; everything hangs off this. | 🟡 | 4–6 wk |
| Staging inventory + approval gates, bulk approve/reprice/edit | Workflow states + bulk ops at scale. | 🟡 | 4–6 wk |
| Per-bin locations, capacity warnings, bin tags, inter-store transfers | Warehouse-lite. | 🟡 | 3–5 wk |
| Pre-order/release-date flagging, per-item timeline (imports/deductions/adjustments) | Event-sourced item history. | 🟡 | 3–5 wk |
| Bulk lots w/ auto-regenerating templates; master-set SKUs (set completion) | Niche but valued. | 🟡 | 3–4 wk |
| Handles "million-row inventories" | Indexing/partitioning/pagination discipline. | 🟡 | ongoing |

### 4.5 Point of Sale (POS)

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Unlimited registers, multi-till variance tracking | Standard retail POS. | 🟡 | 6–10 wk |
| Stripe Terminal card-present payments | Stripe SDK integration. | 🟢 | 2–4 wk |
| Store credit (bi-directional Shopify sync), gift cards | Ledger + sync. | 🟡 | 3–5 wk |
| Table-time billing (charge for play space) | Niche timer billing. | 🟢 | 1–2 wk |
| Random receipt coupons ("loot drops") | Gamified promo. | 🟢 | 1 wk |
| 0% commission | Business-model choice, not a feature to build. | — | — |

### 4.6 Buylist (buying cards from customers)

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Branded customer-facing buylist portal | Public web portal per store. | 🟡 | 4–6 wk |
| Cash vs. credit budgets; 7-layer buylist price math | Reverse of autopricing; per-condition buy prices. | 🟡 | 4–6 wk |
| Hotlist/darklist (want / never-buy) | Lists + matching. | 🟢 | 1–2 wk |
| Public queue board, order chat, URL source tracking, custom domain | Portal extras. | 🟡 | 3–5 wk |

### 4.7 Marketplace Sync (the second moat — and maintenance sink)

| Integration | Status (theirs) | Feasibility | Effort each |
|---|---|---|---|
| **Shopify** (orders, fulfillment, metafields, store credit) | Live, full | 🟡 well-documented API | 6–10 wk |
| **eBay** (listings, orders, refunds, ~5-min sync) | Live | 🟠 large API surface | 8–12 wk |
| **CardTrader** (product push, orders, CT0 boxes) | Live | 🟡 | 4–6 wk |
| **ManaPool** (inventory, fulfillment, reporting) | Live | 🟡 | 4–6 wk |
| **Square** (catalog, inventory, location) | Live | 🟡 | 4–6 wk |
| **Misprint** (inventory, deductions, webhooks) | Live | 🟡 | 3–5 wk |
| **TCGPlayer** "semi-sync" via Chrome extension | Partial — *no full public write API* | 🔴 fragile browser automation | 6–10 wk + perpetual upkeep |
| WooCommerce, LGS Market, Temu, Walmart, Mercari | "Coming soon" | 🟡–🟠 | 4–10 wk each |
| Unified ledger / order-deduction automation across channels | Reconcile one stock pool across N channels; oversell prevention. | 🟠 | 8–12 wk |

> **Key reverse-engineering finding:** TCGPlayer — the single most important TCG marketplace — is integrated only via a **Chrome extension "semi-sync,"** strongly implying TCGPlayer does not grant a full programmatic write API to third parties. Any clone faces the same wall and must replicate the fragile browser-automation approach. This is a recurring, high-maintenance cost, not a one-time build.

### 4.8 Orders & Shipping

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Buy USPS/UPS/FedEx labels; prepaid shipping wallet | Use EasyPost/Shippo/Stamps API rather than direct carrier integrations. | 🟢 | 3–5 wk |
| PWE (plain-white-envelope) + IMB tracking, toploader/team-bag templates, auto weights | TCG-specific packaging presets. | 🟢 | 2–3 wk |
| Unified pick/pack/fulfillment across 5+ platforms | Ties to sync layer. | 🟡 | 4–6 wk |

### 4.9 Labels, Export & Reporting

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| Drag-and-drop **label designer**, 14 element types, 4 barcode encodings, QR→live Shopify listing, 50-step undo | A mini design tool + print pipeline. | 🟡 | 6–10 wk |
| **CSV Suite** (free): 46+ columns, 20+ templates, import/merge/reprice/export, XLSX multi-sheet, per-bin ZIP | Heavy but well-trodden data tooling. | 🟡 | 4–6 wk |
| Reporting: 14 templates (P&L, ABC, dead-stock, sell-through, margin-by-channel) + custom drag-drop builder, schedule/email/share, CSV/XLSX/PDF | BI-lite over inventory/sales. | 🟡 | 6–10 wk |

### 4.10 Customer-Facing Tools

| Feature | Notes | Feasibility | Effort |
|---|---|---|---|
| **Kiosk** (self-serve buy/sell carts, unlimited, 6-digit codes, POS handoff, branding) | In-store tablet app. | 🟡 | 4–6 wk |
| **Mobile app** (free 500 scans/mo, collections, trade codes, share pages) | Consumer side of the mobile app. | 🟡 | covered by 4.1 + 6–8 wk |
| **In-person trading** (5-digit codes / QR pairing, side-by-side compare w/ live prices, 1-tap confirm) | Two-device session + valuation. | 🟡 | 4–6 wk |
| Collection management (unlimited named lists, real-time value, cross-device sync) | Consumer collection tracker. | 🟢 | 3–5 wk |
| **Store Locator** (public directory + map) | Standard. | 🟢 | 1–2 wk |
| **Community Decks** (browse winning MTG decks, share) | Content feature; needs deck data source. | 🟢 | 2–4 wk |

### 4.11 Advanced Modules (Beta/Alpha — they haven't finished these either)

| Module | Status | Notes | Feasibility | Effort |
|---|---|---|---|---|
| **Events** (Beta) | tournaments/leagues/drafts/sealed, 25+ games, Swiss/elim/RR/pod, registration/waitlist/check-in, auto store-credit payout | Substantial tournament engine. | 🟠 | 10–16 wk |
| **Warehouse** (Alpha) | location/bin/serial, cycle counts, receiving/putaway, pick/pack task queues, variance dashboard | Full WMS-lite. | 🟠 | 10–16 wk |
| **Purchasing** (Alpha) | PO lifecycle, suppliers, claims, product mapping, reorder suggestions, templates | Procurement module. | 🟡 | 8–12 wk |
| **Loyalty** (Alpha) | tiers, enrollment, earn/redeem, referrals (fixed/%/credit/free-ship) | Loyalty engine. | 🟡 | 6–10 wk |
| **Consignment** (Beta) | consignor portal, approval, status tracking, commission calc, auto payouts | Marketplace-within-store. | 🟠 | 8–12 wk |
| **Swift AI Assistant** (in dev) | Discord + web chat: browse inventory, wishlists, price-drop alerts, event reg, order tracking. "4 tiers, 112 planned features" | LLM agent over store data (RAG + tools). | 🟡 | 8–14 wk |
| **Hosted storefront** (coming soon) | full branded online store inside platform | Another sales channel surface. | 🟠 | 12–20 wk |

### 4.12 Hardware

| Item | Notes | Feasibility | Effort/Cost |
|---|---|---|---|
| **Simple Sifter** | Raspberry Pi + up to 4 Fujitsu document scanners feeding ingestion API. Mostly integration + a small appliance image. | 🟡 | 4–8 wk + ~$1–3K BOM/unit (scanners dominate) |
| **Super Sorter** | 29-bin electromechanical card sorter with onboard camera recognition, multi-format (penny-sleeve/JP/raw/toploaded), USA-built, 11 units live. This is a **robotics product**: mechanical design, card-feed/transport, sensors, firmware, manufacturing, support. | 🔴 | 12–36 months, $500K–$2M+ R&D; meaningful per-unit BOM + assembly |

---

## 5. Technology Stack Recommendation (for a clean rebuild)

- **Backend:** TypeScript (NestJS) or Python (FastAPI) or Go. Postgres as system-of-record (multi-tenant, partition large tables). Redis for queues/caching. A job runner (Temporal / BullMQ / Sidekiq-equivalent) for repricing batches and sync.
- **Catalog/search:** Postgres + OpenSearch/Elasticsearch for fast card autocomplete over millions of variants.
- **Recognition service:** Python ML service. Approach: per-card image **embeddings** (e.g. a fine-tuned vision backbone) → ANN vector search (FAISS / pgvector / a managed vector DB) against a reference set of every card's official art; OCR (collector number + set symbol) as a strong disambiguator. Foil/language as auxiliary classifiers. Run on GPU inference (serverless GPU or a small always-on pool).
- **Frontend:** Next.js/React. **Mobile:** React Native (camera + on-device pre-crop, server-side recognition).
- **Payments/shipping:** Stripe (+ Terminal), EasyPost/Shippo for labels.
- **Infra:** A single cloud (AWS/GCP). Object storage for images. Scheduled batch + webhook ingress behind a queue.

---

## 6. Cost to Build

### 6.1 One-time engineering (build)

Summing §4 effort, **deduplicated** and assuming a competent senior team (parallelizable):

| Phase | Scope | Calendar | Team | Loaded cost* |
|---|---|---|---|---|
| **MVP** | Recognition (1–3 games, ~95% not 99.9%) + catalog/pricing data ingest + autopricing (core steps) + inventory + POS + Shopify & eBay sync + mobile scan app + labels/CSV | 6–9 mo | 3–4 eng + design | **$350K–$600K** |
| **V1 (sellable to real shops)** | + Buylist, Square/CardTrader/ManaPool sync, TCGPlayer semi-sync, shipping, reporting, kiosk, store credit, 10+ games | +6–9 mo | 5–7 eng | **+$700K–$1.2M** |
| **Full parity** | + Events, Warehouse, Purchasing, Loyalty, Consignment, AI assistant, hosted storefront, graded pricing, 50+ games, 26+ games recognized @ near-99.9% | +6–12 mo | 7–10 eng | **+$1.2M–$2.5M** |
| **Hardware (optional)** | Simple Sifter (cheap) + Super Sorter robotics program | 12–36 mo parallel | dedicated HW team | **+$0.5M–$2M+** |

\* Loaded cost ≈ $200K–$260K/eng-yr fully burdened (US senior). Offshore/blended can cut software figures 40–60%.

**Headline:** credible **MVP ≈ $0.35–0.6M**; **software parity ≈ $2.5–4.5M**; **+ hardware → $3–7M+**.

### 6.2 Recurring / operating cost (run)

| Cost item | Estimate (early, <100 shops) | At scale (600+ shops) |
|---|---|---|
| Cloud infra (compute/DB/storage/queues) | $1.5K–$5K/mo | $15K–$60K/mo |
| GPU inference for recognition | $0.5K–$3K/mo (or per-scan serverless) | $5K–$30K/mo |
| Price-data licensing / API access (5–7 sources) | **highly variable — $0 to $10K+/mo**; some sources require revenue-share or paid tiers | larger; may need contracts |
| Payments (Stripe) | pass-through ~2.9%+$0.30 | same (pass-through) |
| Shipping (EasyPost/Shippo) | per-label fee | per-label |
| Email/SMS, maps, error monitoring, etc. | $200–$1K/mo | $2K–$8K/mo |
| Support/ops staff | 1–2 people | growing team |

> **The dominant *recurring* risk is not infra — it's data licensing.** Pricing/catalog data from TCGPlayer/Cardmarket/etc. underpins the whole product, and terms can change or be revoked. Budget legal + relationship management here.

### 6.3 What's cheap vs. expensive (TL;DR for prioritization)

- **Cheap & high-value:** autopricing rules engine, CSV suite, labels, inventory model, Shopify sync, store locator, collection tracker. Build these first.
- **Expensive but unavoidable for the value prop:** card recognition ML + catalog data, eBay + TCGPlayer sync, unified multi-channel ledger.
- **Expensive & deferrable:** Events, Warehouse, Purchasing, Loyalty, Consignment, AI assistant, hosted storefront. (SortSwift itself has these in alpha/beta.)
- **A different company entirely:** the Super Sorter hardware. Only pursue if hardware is a deliberate strategic moat; otherwise partner/skip.

---

## 7. Hardest Problems / Moats (where a clone wins or dies)

1. **Recognition accuracy at breadth.** "99.9% across 26+ games" is the claim that sells the product. Getting from 95% → 99.5% across foils, languages, and lookalike reprints is most of the ML effort and requires a large labeled image corpus per game/set, refreshed every new set release (continuous, never "done").
2. **Catalog + price data rights.** Without reliable daily data for 5+ sources you have no autopricing and no recognition ground truth. This is a business-development problem as much as engineering.
3. **TCGPlayer write access.** No full API → fragile Chrome-extension automation that breaks when their site changes. Perpetual maintenance.
4. **Multi-channel oversell prevention.** One physical card listed on 6 marketplaces + POS; when it sells anywhere, pull it everywhere fast enough to avoid double-sells. Race conditions at scale.
5. **Scale of repricing.** 250K+ items every 12h per the platform, across many tenants, without melting costs.

---

## 8. Recommended Build Roadmap (if rebuilding)

1. **Foundation (weeks 0–8):** multi-tenant auth, variant inventory data model, catalog import (start with MTG + Pokémon), price-data ingestion for 1–2 sources, CSV import/export.
2. **Pricing + intake (8–20):** autopricing rules engine + dry-run simulator; Swift-Add manual entry; mobile scan app against a v1 recognizer (MTG/Pokémon).
3. **Sell + sync (20–36):** POS w/ Stripe Terminal; Shopify sync; eBay sync; unified ledger; labels.
4. **Buy + breadth (36–52):** buylist portal; Square/CardTrader/ManaPool; TCGPlayer semi-sync; shipping; reporting; expand recognized games.
5. **Differentiate (52+):** kiosk, consumer mobile (trading/collections), events, loyalty, AI assistant, hardware (only if strategic).

---

## 9. Key Risks

- **Data dependency / licensing revocation** (TCGPlayer et al.) — existential.
- **Recognition arms race** — every new set is new labeled data forever.
- **Integration maintenance treadmill** — N marketplaces × breaking changes.
- **Entrenched incumbents** (BinderPOS, CrystalCommerce, TCGplayer) and SortSwift's first-mover 0%-commission position.
- **Hardware capital sink** — the Super Sorter can consume the whole budget for slim returns at 11 units in field.

---

## 10. Sources

- https://sortswift.com/ — homepage / positioning
- https://sortswift.com/overview — full platform feature inventory
- https://sortswift.com/features/autopricing — pricing engine detail
- https://sortswift.com/features/mobile-scanning — recognition/scan detail
- https://sortswift.com/features/mobile-collections — trading/collections
- https://sortswift.com/features/inventory , /features/orders , /features/mobile-app
- https://sortswift.com/pricing , https://www.sortswift.com/about , https://www.sortswift.com/docs

*Note: figures (600+ shops, $100M sales, 257K reprices, 99.9% accuracy, 86M SKUs) are SortSwift's own marketing claims, used here for sizing, not independently verified.*
