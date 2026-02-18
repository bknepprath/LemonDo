# Lemon Do — Bug Squash Log

> Track every bug found, investigated, and resolved.
> **Last updated:** 2026-02-18

---

## How to Use This Log

Each bug gets an entry when discovered. Update the entry as you investigate and fix.

**Severity levels:** `critical` | `high` | `medium` | `low` | `cosmetic`
**Statuses:** `open` | `investigating` | `fix-in-progress` | `resolved` | `won't-fix`

---

## Active Bugs

_No active bugs._

---

## Resolved Bugs

### BUG-001: `addRoundedRect` TypeError on launch

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`resizeEvent`, `paintEvent`)
- **Symptoms:** App crashes immediately on launch with `TypeError: addRoundedRect(...): argument 1 has unexpected type 'QRect'`.
- **Root cause:** PyQt6's `QPainterPath.addRoundedRect` requires `QRectF`, but `self.rect()` returns `QRect`.
- **Fix:** Wrapped all `self.rect()` calls in `QRectF()` before passing to `addRoundedRect`. Added `QRectF` import from `PyQt6.QtCore`.

### BUG-002: Tiny circle in sleep mode

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`__init__`, `on_stripe_height_changed`)
- **Symptoms:** During night/sleep mode the window collapsed to a small circle because all content was hidden and no minimum size was enforced.
- **Root cause:** `setFixedSize` was used instead of `setMinimumSize`, and layout constraint allowed the widget to shrink freely when stripes were hidden.
- **Fix:** Changed to `setMinimumSize(300, 820)` and added a floor check in `on_stripe_height_changed` to prevent shrinking below the minimum.

### BUG-003: Git commit accidentally deleted `lemon_do.py`

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** Repository
- **Symptoms:** Commit `0f988f0` showed `lemon_do.py` as deleted; the file had been renamed to `lemon_do.pyw` outside of git tracking.
- **Root cause:** The file was renamed to `.pyw` (to suppress the console window on Windows) but the old `.py` was still tracked by git. The commit staged the deletion of the old file without adding the new one.
- **Fix:** Added `lemon_do.pyw` as a new tracked file in the subsequent commit `63e2db9`.

---

## Stats

| Total | Open | Resolved | Won't Fix |
|-------|------|----------|-----------|
| 3 | 0 | 3 | 0 |
