# Profit calculation

The math is intentionally simple. Per Importing Company (IC), per business day:

```
gross_profit         = profit_per_order × num_delivered
day_net_profit       = gross_profit − day_cost              (only if num_delivered > 0)
total_net_profit     = Σ day_net_profit  across all ICs

total_capital        = Σ daily_share  across all partners
partner_pct          = partner.daily_share / total_capital
partner_final_profit = total_net_profit × partner_pct
```

Important rules:

* Only `DELIVERED` orders contribute to `num_delivered`.
* `shipping_cost` on Production Companies is **tracked but never deducted**.
* `day_cost` is the only deduction from gross profit.
* If `num_delivered = 0` for an IC, no `day_cost` is charged for that IC.
* Once a day is closed, the partner allocation is frozen in
  `daily_ic_snapshots` + `daily_partner_snapshots` and is never recomputed.

## Worked example

```
profit_per_order = 50 EGP
num_delivered    = 20
gross_profit     = 50 × 20 = 1,000 EGP
day_cost         = 100 EGP
net_profit       = 1,000 − 100 = 900 EGP

total_capital = 1,000 EGP
Ahmed share   = 300 EGP → 30%
Bilal share   = 700 EGP → 70%

Ahmed_final = 900 × 0.30 = 270 EGP
Bilal_final = 900 × 0.70 = 630 EGP
```

## Rounding

The service stores monetary numbers with two decimal places using
`Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. The partner
percentage uses six decimal places (`NUMERIC(8,6)`) to avoid drift when many
partners are present. Sums of rounded values may differ from
`gross − day_cost` by a single cent in rare cases; this is acceptable and
matches the agreed-upon spec.

## Multi-IC days

For each IC the snapshot stores its own `gross_profit`, `day_cost`, and
`net_profit`. The partner snapshot then breaks each IC's net profit down by
the same partner percentages:

```
DAILY_IC_SNAPSHOT:
  (date, IC=X)  net_profit = 500
  (date, IC=Y)  net_profit = 400

DAILY_PARTNER_SNAPSHOT (partner pct = 30%):
  (date, partner, IC=X)  final_profit = 150
  (date, partner, IC=Y)  final_profit = 120
```

This gives the user the ability to reconcile a single partner's earnings
per IC after the fact, even if profit ratios per IC change later.
