# SortSwift Clone — Feature Map & Build Plan

> Companion to `SORTSWIFT_REVERSE_ENGINEERING.md`. This document is the **execution blueprint**: a complete feature map, the data model, epic/task breakdown, and a phased delivery plan with milestones. Intended to seed a new repository.

---

## Part A — Complete Feature Map

Hierarchy: **Domain → Module → Feature**. Each feature tagged: priority **[P0/P1/P2/P3]** (P0 = MVP-critical), and difficulty 🟢/🟡/🟠/🔴.

### 1. Identity & Tenancy
- 1.1 Multi-tenant accounts (store = tenant) **[P0]** 🟡
- 1.2 Users, roles & permissions (owner/manager/clerk) **[P0]** 🟡
- 1.3 Per-store settings & branding **[P0]** 🟢
- 1.4 Billing & subscription (plans, à-la-carte modules, usage metering for scans) **[P1]** 🟡

### 2. Catalog & Market Data (foundation)
- 2.1 Canonical multi-game card catalog (game→set→card→variant) **[P0]** 🟠
- 2.2 Variant model (condition × language × printing/foil × grade) **[P0]** 🟡
- 2.3 Sealed product as first-class type **[P1]** 🟢
- 2.4 Price-source ingestion adapters (TCGPlayer, Cardmarket, CardTrader, ManaPool, Card Kingdom) **[P0]** 🟠
- 2.5 Daily price refresh pipeline **[P0]** 🟡
- 2.6 Catalog refresh on new set releases **[P1]** 🟡
- 2.7 Graded pricing comparables **[P3]** 🟠

### 3. Card Recognition & Intake
- 3.1 Image recognition service (embeddings + ANN + OCR disambiguation) **[P0]** 🔴
- 3.2 Foil/printing detection **[P1]** 🔴
- 3.3 Language detection / non-English flagging **[P1]** 🟠
- 3.4 Mobile scan UX (auto-capture, viewfinder, flash, pinch-zoom, overlay confirm) **[P0]** 🟡
- 3.5 Swift-Add keyboard rapid entry (autocomplete, hotkeys, queue) **[P0]** 🟢
- 3.6 Document-scanner batch upload + card segmentation **[P2]** 🟠
- 3.7 UPC/barcode scan for sealed & supplies **[P1]** 🟢
- 3.8 CSV import with column mapper + fuzzy match **[P0]** 🟡
- 3.9 Chaos-sort workflow (scan-then-bin, no pre-sort) **[P1]** 🟡
- 3.10 Scan quota metering (free 500/mo + plan tiers) **[P1]** 🟢

### 4. Inventory Management
- 4.1 Variant stock tracking **[P0]** 🟡
- 4.2 Staging inventory + approval gates **[P1]** 🟡
- 4.3 Bulk approve / reprice / edit **[P0]** 🟡
- 4.4 Bin locations, capacity warnings, bin tags **[P1]** 🟡
- 4.5 Inter-store transfers **[P2]** 🟡
- 4.6 Pre-order / release-date flagging **[P2]** 🟢
- 4.7 Per-item timeline (event-sourced history) **[P1]** 🟡
- 4.8 Bulk lots w/ auto-regenerating templates **[P2]** 🟡
- 4.9 Master-set SKUs / set-completion tracking **[P3]** 🟡

### 5. Autopricing Engine
- 5.1 Rules pipeline (ordered steps: source→modifier→offset→guard→round) **[P0]** 🟡
- 5.2 Baseline selection + 4-slot fallback chains **[P0]** 🟢
- 5.3 Attribute multipliers (condition/rarity/printing/lang/age) **[P0]** 🟢
- 5.4 Offsets incl. time-limited flash sales **[P1]** 🟡
- 5.5 Guards/floors (cost-plus, buylist floor, max-move cap, ceiling, override lock) **[P0]** 🟡
- 5.6 Rounding modes (9, incl. psychological) **[P0]** 🟢
- 5.7 Config hierarchy (platform × set-group × card-list × price-range) **[P1]** 🟠
- 5.8 Source-aggregation modes (follow/highest/lowest/average) **[P1]** 🟢
- 5.9 Dry-run simulator + per-card investigator **[P1]** 🟡
- 5.10 Scheduled batch reprice (12h) + on-demand bulk **[P0]** 🟡

### 6. Point of Sale
- 6.1 Registers + cart + checkout **[P1]** 🟡
- 6.2 Multi-till variance tracking **[P2]** 🟡
- 6.3 Stripe Terminal card-present **[P1]** 🟢
- 6.4 Store credit (bi-dir Shopify), gift cards **[P1]** 🟡
- 6.5 Table-time billing **[P3]** 🟢
- 6.6 Random receipt coupons **[P3]** 🟢

### 7. Buylist (buying from customers)
- 7.1 Branded buylist portal **[P1]** 🟡
- 7.2 Buylist price math (cash/credit, per-condition) **[P1]** 🟡
- 7.3 Hotlist / darklist **[P2]** 🟢
- 7.4 Queue board, order chat, URL source tracking **[P2]** 🟡
- 7.5 Custom domain **[P3]** 🟡

### 8. Marketplace Sync
- 8.1 Shopify (orders/fulfillment/metafields/store-credit) **[P0]** 🟡
- 8.2 eBay (listings/orders/refunds) **[P0]** 🟠
- 8.3 CardTrader **[P1]** 🟡
- 8.4 ManaPool **[P1]** 🟡
- 8.5 Square **[P2]** 🟡
- 8.6 Misprint **[P2]** 🟡
- 8.7 TCGPlayer semi-sync (Chrome extension) **[P1]** 🔴
- 8.8 Unified ledger / oversell prevention **[P0]** 🟠
- 8.9 Order-deduction automation **[P0]** 🟡
- 8.10 Roadmap: WooCommerce/LGS Market/Temu/Walmart/Mercari **[P3]** 🟡

### 9. Orders & Shipping
- 9.1 Label purchase (USPS/UPS/FedEx via EasyPost/Shippo) **[P1]** 🟢
- 9.2 Prepaid shipping wallet **[P2]** 🟢
- 9.3 PWE + IMB tracking, packaging templates, auto weights **[P2]** 🟢
- 9.4 Pick/pack/fulfillment across channels **[P1]** 🟡

### 10. Labels, Export & Reporting
- 10.1 Label designer (drag-drop, barcodes, QR→listing, undo) **[P1]** 🟡
- 10.2 CSV Suite (import/merge/reprice/export, XLSX, per-bin ZIP) **[P0]** 🟡
- 10.3 Reporting (templates: P&L/ABC/dead-stock/sell-through/margin) **[P1]** 🟡
- 10.4 Custom report builder + schedule/email/share **[P2]** 🟡

### 11. Customer-Facing Tools
- 11.1 Kiosk (self-serve buy/sell, codes, POS handoff) **[P2]** 🟡
- 11.2 Consumer mobile app (collections, share pages) **[P2]** 🟡
- 11.3 In-person trading (code/QR pairing, compare, confirm) **[P2]** 🟡
- 11.4 Collection management (lists, live value, sync) **[P2]** 🟢
- 11.5 Store locator (directory + map) **[P3]** 🟢
- 11.6 Community decks **[P3]** 🟢

### 12. Advanced Modules
- 12.1 Events (tournaments/leagues, formats, registration, payouts) **[P3]** 🟠
- 12.2 Warehouse (cycle counts, receiving, pick/pack queues) **[P3]** 🟠
- 12.3 Purchasing (PO lifecycle, suppliers, reorder) **[P3]** 🟡
- 12.4 Loyalty (tiers, earn/redeem, referrals) **[P3]** 🟡
- 12.5 Consignment (portal, approval, commission, payouts) **[P3]** 🟠
- 12.6 Swift AI assistant (Discord/web, RAG over store data) **[P3]** 🟡
- 12.7 Hosted storefront **[P3]** 🟠

### 13. Hardware (optional / strategic)
- 13.1 Simple Sifter (Pi + scanners appliance) **[P3]** 🟡
- 13.2 Super Sorter (29-bin sorting robot) **[P3]** 🔴

---

## Part B — Core Data Model (sketch)

```
Store (tenant) ─┬─ User ── Role
                ├─ ChannelConnection (shopify|ebay|square|...)  → credentials, sync state
                ├─ PricingStrategy ── PricingRule[] (ordered, scoped by platform/set/list/range)
                ├─ Register / Till
                └─ Settings, Branding, Subscription

CatalogCard (global)  ── game, set, name, number, rarity, image_ref
   └─ CatalogVariant   ── condition, language, printing, (grade)
        └─ PriceSnapshot ── source, market/low/mid/direct, captured_at

InventoryItem (per store) ── catalog_variant_id, qty, cost, bin_id, status(staged|live),
                             computed_price_by_channel{}, lot_id?
   └─ InventoryEvent ── type(import|deduct|adjust|reprice), delta, source, at  (event-sourced timeline)

Listing ── inventory_item_id, channel, external_id, state(active|sold|error), last_pushed_at
Order ── channel, external_id, lines[], status, shipment?     (inbound via webhook)
Shipment ── carrier, label_url, tracking, weight
BuylistSubmission ── customer, lines[], offer(cash|credit), status, chat[]
ScanJob ── images[], candidates[], confirmed_variant_id, confidence
```

Key invariants: one **physical stock pool** per InventoryItem feeds N Listings; a sale on any channel must atomically decrement the pool and trigger delist-everywhere (the **unified ledger**, §8.8).

---

## Part C — Phased Build Plan

Assumes a senior team scaling from 3→7 engineers. Durations are calendar estimates.

### Phase 0 — Foundations (Weeks 1–8) · 3 eng
**Goal:** an empty but solid multi-tenant skeleton with catalog + data ingest.
- Repo, CI/CD, infra-as-code, observability, auth, tenancy (1.1–1.3)
- Catalog schema + import MTG + Pokémon (2.1–2.2)
- One price source (TCGPlayer) ingest + daily refresh (2.4–2.5)
- CSV import/export skeleton (3.8, 10.2)
- **Milestone M0:** can import a card list, see catalog + daily prices.

### Phase 1 — Price & Intake (Weeks 9–20) · 4 eng
**Goal:** the pricing brain + first intake paths.
- Autopricing rules engine + fallback + multipliers + guards + rounding (5.1–5.6, 5.10)
- Dry-run simulator (5.9)
- Swift-Add manual entry (3.5)
- Inventory model + bulk ops + timeline (4.1, 4.3, 4.7)
- Recognition service v1: MTG + Pokémon, mobile scan app (3.1, 3.4, 3.10)
- **Milestone M1:** scan a card → recognized → priced → in inventory. *This is the demoable core.*

### Phase 2 — Sell & Sync (Weeks 21–36) · 5–6 eng
**Goal:** make money flow — POS + two marketplaces + the ledger.
- POS: cart/checkout + Stripe Terminal + store credit (6.1, 6.3, 6.4)
- Shopify sync full (8.1)
- eBay sync (8.2)
- Unified ledger + oversell prevention + order deduction (8.8–8.9)
- Label designer + shipping labels (10.1, 9.1, 9.4)
- **Milestone M2 (first sellable):** a real shop can run inventory, sell in-store + on Shopify/eBay without overselling.

### Phase 3 — Buy & Breadth (Weeks 37–56) · 6–7 eng
**Goal:** complete the buy/sell loop and broaden coverage.
- Buylist portal + price math (7.1–7.4)
- CardTrader + ManaPool + Square sync (8.3–8.5)
- TCGPlayer semi-sync extension (8.7)
- Reporting templates + custom builder (10.3–10.4)
- Staging/approval, bins, transfers (4.2, 4.4–4.5)
- Expand recognition to 10+ games; foil/language detection (3.2–3.3)
- Config hierarchy for pricing (5.7)
- **Milestone M3 (V1 GA):** competitive with incumbents on core LGS workflows.

### Phase 4 — Differentiate (Weeks 57+) · 7+ eng, parallel squads
**Goal:** consumer side + advanced modules; pick by demand.
- Kiosk (11.1); consumer mobile: collections + trading (11.2–11.4)
- Events (12.1); Loyalty (12.4); Purchasing (12.3)
- Consignment (12.5); AI assistant (12.6); hosted storefront (12.7)
- Recognition to 26+ games near-99.9%; graded pricing (2.7)
- **Hardware track (separate squad, only if strategic):** Simple Sifter then Super Sorter (13.1–13.2)

---

## Part D — Sequencing Rationale & Dependencies

- **Catalog/data (Phase 0) blocks everything** — recognition needs it as ground truth, pricing needs it as input. Build first.
- **Recognition (Phase 1) and Sync (Phase 2)** are the two moats; tackle the easier-to-validate one (pricing/recognition) before the maintenance-heavy one (sync).
- **Unified ledger (8.8) must land with the 2nd marketplace**, not after — oversells erode trust instantly.
- **Defer all P3 modules** (Events/Warehouse/Purchasing/Loyalty/Consignment/AI/storefront) — SortSwift itself ships these in alpha/beta, so they are not table stakes.
- **Hardware is optional and isolated** — never let it block software milestones.

---

## Part E — Definition of Done per Milestone

| Milestone | Done when… |
|---|---|
| M0 | Import list → catalog + daily prices visible; CI green; one tenant live. |
| M1 | Phone scan of MTG/Pokémon → correct variant ≥95% → auto-priced → inventory row with timeline. |
| M2 | Pilot shop sells same card in-store + Shopify + eBay; sale anywhere delists everywhere within target SLA; ships a label. |
| M3 | Buylist intake works; 5+ channels sync; reporting usable; 10+ games recognized; onboard a shop unaided. |
| M4 | Selected consumer/advanced modules GA per demand; recognition breadth at parity. |

---

## Part F — Team & Cost Snapshot (from analysis)

- **MVP through M2:** ~6–9 months, 3–6 eng, **$0.35M–$0.6M**.
- **Through M3 (V1 GA):** ~12–14 months, **$1M–$1.8M** cumulative.
- **Full parity (M4, software):** 18–30 months, **$2.5M–$4.5M**.
- **Hardware:** +$0.5M–$2M+, separate team.
- **Run cost:** $3K–$15K/mo early; dominant *risk* is price-data licensing, not infra.

---

## Part G — Open Decisions (need product calls before/early in build)

1. **Data licensing** — which price sources can we legally use, and at what cost? (Gates Phase 0.)
2. **Recognition build vs. buy** — train in-house vs. license a card-ID API (e.g. existing scan vendors)? Changes Phase 1 cost dramatically.
3. **Mobile stack** — React Native (shared) vs. native (best camera perf).
4. **Target launch games** — confirm MTG + Pokémon first (largest markets) vs. a niche wedge.
5. **Hardware** — pursue at all, or partner/skip and compete on software + 0% commission only?
6. **Commission model** — match SortSwift's 0% (monetize via subscription) or take rate?
