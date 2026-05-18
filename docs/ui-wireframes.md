# UI wireframes

> ASCII wireframes — see `src/ordertracker/ui/styles/app.qss` for the final
> typography & spacing. The app uses a sidebar + content layout; on Arabic
> the entire window flips RTL via `QApplication.setLayoutDirection`.

## Login

```
┌──────────────────────────────────────────┐
│                OrderTracker              │
│              ─────────────────           │
│   Username   [ ____________________ ]    │
│   Password   [ ●●●●●●●●●●●●●●●●●●●● ]    │
│                                          │
│              [   Login   ]               │
└──────────────────────────────────────────┘
```

## Main window

```
┌──────────────────┬──────────────────────────────────────┐
│ Dashboard        │ Dashboard                Date [____] │
│ Orders           │                                      │
│ Production Cos.  │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│ Importing Cos.   │ │Total │ │Deli- │ │Retu- │ │Post- │  │
│ Partners         │ │Orders│ │vered │ │rned  │ │poned │  │
│ Daily Shares     │ └──────┘ └──────┘ └──────┘ └──────┘  │
│ End-of-Day       │                                      │
│ Settings (admin) │ Per-IC table (name | D | R | P | net)│
│ ────────         │ ───────────────────────────────────  │
│ Language: EN/AR  │                                      │
└──────────────────┴──────────────────────────────────────┘
```

## Orders screen

```
┌────────────────────────────────────────────────────────────────────────┐
│ Orders                              Date [   ] [Scan ___] [Import Excel]│
├────────────────────────────────────────────────────────────────────────┤
│ Order Key       | Customer | Address  | Price | Status | PC | IC | Pr │
│ ORD-PC01-0517-1 | Aly      | ...      | 150   | ON HOLD| #1 | A  | 0  │
│ ORD-PC01-0517-2 | Sara     | ...      | 200   | NEW    | #1 | -  | 1  │
│ ...                                                                    │
├────────────────────────────────────────────────────────────────────────┤
│ [IC dropdown ▼] [Assign IC]   [Delivered]  [Returned]  [Postponed] [⟳]│
└────────────────────────────────────────────────────────────────────────┘
```

Hotkeys / scanner behavior:

* Scanner is in **keyboard wedge mode** — it types the barcode + Enter.
* When the cursor is in the "Scan" box, Enter triggers
  `OrdersView._handle_scan` which jumps to the order's date and selects it.

## Excel import wizard

```
┌─────────────────────────────────────────────┐
│ Import Orders from Excel                    │
│ ─────────────────────────────               │
│ 1. Drag and drop or pick an .xlsx file.     │
│ 2. Choose the Production Company.           │
│ 3. Review the parsed preview.               │
│ 4. Confirm — all rows are imported atomically.│
└─────────────────────────────────────────────┘
```

Validation:

* Missing required column → reject the whole file.
* Negative or non-numeric price → reject the whole file with row numbers.
* Empty name / address → reject the whole file with row numbers.
* Maximum 5,000 data rows per file.

## Day close wizard

```
┌────────────────────────────────────────────────────┐
│ End-of-Day                Date [   ]               │
│ • Scan all RETURNED orders                          │
│ • Any POSTPONED orders?                             │
│ • Mark the rest as DELIVERED                        │
│ • Close the day                                     │
│                                                    │
│ Status counts                                       │
│  NEW      | 0                                       │
│  ON HOLD  | 0                                       │
│  DELIVERED| 24                                      │
│  POSTPONED| 2                                       │
│  RETURNED | 3                                       │
│                                                    │
│ Day state: OPEN                                     │
│                              [Reopen] [Close Day]   │
└────────────────────────────────────────────────────┘
```

## Settings (admin only)

```
┌────────────────────────────────────────────────────┐
│ Settings                                            │
│                                                    │
│ Database                                            │
│  Connection URL [ ●●●●●●●●●●● ]    [Test] [Save]    │
│                                                    │
│ Language                                            │
│  [ English ▼ ]                                      │
│                                                    │
│ Auto-Update                                         │
│  Current version: 0.1.0           [Check Now]       │
└────────────────────────────────────────────────────┘
```

## Right-to-left (Arabic)

When language is switched to `ar`:

* `QApplication.setLayoutDirection(Qt.RightToLeft)` flips the whole window.
* The sidebar moves from left to right.
* Tables read right-to-left; numbers still display LTR thanks to Unicode
  bidi handling.
* All keys come from `i18n/ar.json`; only the strings change at runtime —
  the widget tree is not rebuilt.
