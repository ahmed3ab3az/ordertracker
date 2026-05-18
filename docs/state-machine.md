# Order & day state machines

## Order status (open day)

```mermaid
stateDiagram-v2
    [*] --> NEW: Excel import
    NEW --> ON_HOLD: Assign IC
    ON_HOLD --> DELIVERED: End-of-day scan
    ON_HOLD --> RETURNED: End-of-day scan
    ON_HOLD --> POSTPONED: End-of-day scan
    POSTPONED --> ON_HOLD: next day re-assignment

    note right of NEW
        No IC yet → no profit
    end note
    note right of DELIVERED
        Counts toward profit
    end note
```

## Order status (closed day)

```mermaid
stateDiagram-v2
    DELIVERED --> DELIVERED: locked forever
    RETURNED --> RETURNED: locked forever
    POSTPONED --> ON_HOLD: still editable, can move forward
```

## Day state

```mermaid
stateDiagram-v2
    [*] --> OPEN
    OPEN --> CLOSED: Admin clicks "Close Day"\n+ no NEW/ON_HOLD remain
    CLOSED --> REOPENED: Admin reopens\n(audit-logged)
    REOPENED --> CLOSED: Admin closes again
```

## Transition matrix (machine-readable)

These are the same maps used at runtime by
[`services.orders.OrderService.transition`](../src/ordertracker/services/orders.py):

```python
ALLOWED_TRANSITIONS_OPEN_DAY = {
    NEW:        {ON_HOLD},
    ON_HOLD:    {DELIVERED, RETURNED, POSTPONED},
    POSTPONED:  {ON_HOLD},
    DELIVERED:  {RETURNED, ON_HOLD, POSTPONED},
    RETURNED:   {DELIVERED, ON_HOLD, POSTPONED},
}

ALLOWED_TRANSITIONS_CLOSED_DAY = {
    POSTPONED:  {ON_HOLD},
}
```

## Invariants

| Invariant | Enforced by |
| --- | --- |
| `num_orders == delivered + returned + postponed + on_hold` (per company per day) | `CompanyDailyStats.assert_balanced` |
| Cannot close a day with `NEW`/`ON_HOLD` orders | `DayService.close` |
| Closed-day `DELIVERED`/`RETURNED` orders cannot be edited | `services.orders` + transition matrix |
| Concurrent edits raise an error rather than overwrite | `services.orders._load_for_update` |
| Snapshots are append-only | UNIQUE indexes + service code never UPDATEs |
| Audit log is append-only | DB role lacks DELETE permission |
