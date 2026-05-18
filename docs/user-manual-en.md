# OrderTracker — User Manual (English)

## 1. Logging in

Run **OrderTracker** from the Start menu. On the login dialog:

* Enter your username and password.
* Click **Login**.

Failing 5 attempts in a row locks the account for 5 minutes. If you've
forgotten your password, ask the Admin to reset it from the **Partners**
screen.

## 2. The main window

The sidebar lets you switch between screens. Highlights:

* **Dashboard** — daily KPIs (orders, deliveries, profit).
* **Orders** — the main work surface; supports barcode scanning and Excel
  import.
* **Production / Importing Companies** — CRUD for partners on either side
  of the supply chain.
* **Partners** — admin-only; creates partner accounts.
* **Daily Shares** — record each partner's capital contribution for the day.
* **End-of-Day** — closes the day after every order is resolved.
* **Settings** — admin-only; DB credentials, language, updates.

The language menu (top bar) switches between **English** and **العربية**
instantly. Arabic flips the layout right-to-left.

## 3. Importing orders

1. Choose **Orders → Import Excel**.
2. Pick the Production Company (PC) the orders belong to.
3. The app validates required columns (`name`, `address`, `price`). If any
   row is invalid the entire file is rejected and the row numbers are shown.
4. Confirm the preview. Orders are saved atomically and a barcode is
   generated for each.

Each order key looks like `ORD-PC01-MMDD-NNN`.

## 4. Daily flow

1. Excel import → orders are `NEW`.
2. Pick an order and click **Assign IC** → it becomes `ON_HOLD`.
3. At end of day, the scanner is used:
   * Scan returned orders → mark as `RETURNED`.
   * Scan postponed orders → mark as `POSTPONED`.
   * Click **Delivered** to bulk-mark the rest.
4. On **End-of-Day**, the Admin clicks **Close Day**. The day cannot close
   while any orders are still `NEW` or `ON_HOLD`.

After close, only `POSTPONED → ON_HOLD` is allowed; everything else is
locked.

## 5. Reprints

Selecting an order and clicking **Reprint Slip** reprints the barcode and
adds a watermark (`REPRINT`). Every print is logged.

## 6. Partner shares

Open **Daily Shares**, pick the date, and enter the capital contributed by
each partner. Percentages update live. Click **Save**.

## 7. Settings

Admins can:

* Update the database connection (test before saving).
* Switch the default language.
* Check for application updates.

## 8. Backups and archive

Once a month run the **archive CLI** on the main PC:

```
ordertracker-archive --usb-target E:\OrderTracker
```

The tool exports old data to a local SQLite file, verifies a SHA-256 on the
USB drive, and only then deletes the rows from the cloud database.

## 9. Troubleshooting

| Problem | Fix |
| --- | --- |
| Account locked | Wait 5 minutes or ask the Admin |
| "Order was modified by another user" | Click refresh; another PC saved first |
| Cannot close the day | Resolve any `NEW` / `ON HOLD` orders first |
| Update fails | The updater restores the previous version automatically |
