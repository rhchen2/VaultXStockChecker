// Hard-coded VaultX order snapshots for the Orders page.
//
// PII IS INTENTIONALLY EXCLUDED. Do NOT add customer name, email, company,
// shipping/billing address, or payment details to this file - the page is
// meant to show *what was ordered* and the totals, without personal info.
//
// `itemsComplete: false` means the line items are a partial capture (e.g. from
// a scrolled screenshot); the page will show "X of N items" and reconcile
// against the authoritative `summary` totals.

const ORDERS = [
  {
    number: "WUS3355",
    status: "On its way",
    // RULE: "Shipped" requires a tracking number. None captured for this order
    // yet, so the page shows it as Confirmed / awaiting tracking. Fill this in
    // (e.g. { number: "1Z...", carrier: "UPS", url: "https://..." }) to flip it
    // to Shipped.
    tracking: null,
    timeline: [
      { label: "On its way", date: "Jun 3" },
      { label: "Confirmed", date: "Jun 1" },
    ],
    paid: "Jun 1",
    shippingMethod: "Standard Shipping",
    items: [
      // A "...Metallic Green @ $17.49/ea" line (and possibly others) were above
      // the screenshot scroll and are not captured below.
      { product: "4-Pocket Exo-Tec® Zip Binder", color: "Signature Black", qty: 15, ea: 10.93, total: 163.95 },
      { product: "9-Pocket Exo-Tec® Zip Binder", color: "Signature Black", qty: 10, ea: 18.55, total: 185.50 },
      { product: "9-Pocket Exo-Tec® Zip Binder", color: "Sunrise Yellow", qty: 20, ea: 16.69, total: 333.80 },
      { product: "9-Pocket Exo-Tec® Zip Binder", color: "Ocean Blue", qty: 20, ea: 16.69, total: 333.80 },
      { product: "9-Pocket Exo-Tec® Zip Binder", color: "Fire Red", qty: 20, ea: 16.69, total: 333.80 },
    ],
    itemsComplete: false,
    summary: { itemCount: 125, subtotal: 2050.45, shipping: 0, taxes: 148.71, total: 2199.16 },
  },
];
