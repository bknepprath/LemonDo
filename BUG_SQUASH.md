# Lemon Do — Bug Squash Log

> Track every bug found, investigated, and resolved.
> **Last updated:** 2026-02-18

---

## Active Bugs

No active bugs at this time.

---

## Resolved Bugs

### BUG-001: `addRoundedRect` TypeError on launch

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw`
- **Root cause:** `addRoundedRect` received `QRect` instead of `QRectF`.
- **Fix:** Converted rectangles to `QRectF` for painter path calls.

### BUG-002: Tiny circle in sleep mode

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw`
- **Root cause:** Window lacked a robust minimum size floor in hidden-content states.
- **Fix:** Enforced minimum dimensions and resize floor handling.

### BUG-003: Tracked file mismatch during `.py` → `.pyw` transition

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** Repository
- **Root cause:** Old tracked file removed while new entry file was initially untracked.
- **Fix:** Added and pushed `lemon_do.pyw` as canonical app entry point.

### BUG-004: Completion animation clipping / disappearing stripes

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_animate_completion_sequence`, `relayout_stripes`)
- **Root cause:** Wrapper height could be smaller than the union of current and target geometries during multi-stage animation, causing truncation.
- **Fix:** Added `_compute_animation_bounds()` to dynamically set wrapper height to the max of current bounds, target bounds, and baseline. Added `_completion_in_progress` guard to suppress relayout during animated completion. Snapshot now captures global→local coordinates for accuracy.

### BUG-005: Add task animation instability

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_animate_add_task_sequence`)
- **Root cause:** Parallel animation lifecycle and geometry synchronization around add sequence caused crashes from stale callbacks and competing layout passes.
- **Fix:** Added animation epoch counter to invalidate stale callbacks. `recenter_ui()` now accepts `interrupt` parameter so settling phases don't self-interrupt. Wrapper height prediction covers off-screen start position.

### BUG-006: History navigation freezes after first back press

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`navigate_days`, `_update_nav_buttons`)
- **Root cause:** Navigation clamped to debug-shifted app time (`self.today_date`) instead of real calendar date, so forward button disabled incorrectly after visiting a past day.
- **Fix:** Added `_navigation_today()` using `date.today()` for clamping. Forward button enabled/disabled relative to real today.

### BUG-007: Date label always shows today instead of viewed date

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_update_nav_buttons`)
- **Root cause:** Label text was set to `self.today_date` instead of `self.view_date`.
- **Fix:** Changed label to display `self.view_date.strftime(...)`.

### BUG-008: Tab key swallowed by Qt focus traversal

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`eventFilter`, `keyPressEvent`)
- **Root cause:** Qt's built-in widget focus chain consumed Tab before the app's `keyPressEvent` could handle it.
- **Fix:** Installed a global `eventFilter` on the `QApplication` that intercepts `Tab` and routes it through `_handle_tab_hotkey()`, accepting the event before Qt can process it.

### BUG-009: Nav buttons clipping outside pill at edges

- **Severity:** low
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_position_title`)
- **Root cause:** Nav buttons were positioned at the same Y as the title and too close to pill edges horizontally.
- **Fix:** Moved nav buttons below the title and inward (`x=34` and `x=width-62`).

### BUG-010: Hibernate pill drifts off-screen

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_hibernate_target_geometry`)
- **Root cause:** Used `availableGeometry()` with fixed pixel offsets that didn't account for taskbar/scaling variations.
- **Fix:** Changed to `screen.geometry()` with percentage-based margins (4% right, 8% bottom) and fixed pill size (30×80).

### BUG-011: Long-press on task crashes app

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`StripeTextEdit`, `TaskStripe`)
- **Root cause:** Mouse button enum values were cast with `int(...)` in PyQt6 signal paths, which can raise type errors during press/release callbacks.
- **Fix:** Changed `mouse_pressed`/`mouse_released` signals to emit enum objects directly and compared against `Qt.MouseButton.LeftButton` without integer casting.

### BUG-012: Clicking completed items to un-complete crashes app

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`StripeTextEdit`, `TaskStripe`, completed click flow)
- **Root cause:** Same enum-casting crash path as BUG-011 was triggered when clicking completed-task editors during accordion/un-complete interaction.
- **Fix:** Same signal/enum handling fix as BUG-011; un-complete click path now runs without type-casting exceptions.

### BUG-013: Focus mode leaves completed list blurred after exit

- **Severity:** high
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`enter_focus_mode`, `exit_focus_mode`, `TaskStripe.paintEvent`)
- **Root cause:** Focus mode applied blur effects directly to task stripes, and effect restoration was fragile when task states changed mid-focus.
- **Fix:** Reworked focus visuals so non-focused task stripes use local dim overlays (no blur effect swapping). Blur effects now apply only to header/nav/add controls and are cleanly restored on exit.

### BUG-014: Crash after repeated complete/un-complete in focus-enabled build

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`TaskStripe.apply_theme`, focus/graphics effects)
- **Root cause:** `QGraphicsDropShadowEffect` objects for completed stripes could become invalid after effect replacement, then later be reused, causing runtime crashes.
- **Fix:** Hardened shadow-effect lifecycle with validity checks/recreation in `apply_theme`; separated focused-task shadow from completed-task shadow; reset focus flags/effects during animation interrupts.

### BUG-015: Focus mode blur/effect regressions and delayed crash

- **Severity:** critical
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`TaskStripe`, `enter_focus_mode`, `exit_focus_mode`)
- **Root cause:** Focus mode repeatedly swapped graphics effects on task widgets and mixed with completion/un-completion transitions, causing stale/invalid effect state and intermittent crashes.
- **Fix:** Reworked focus mode visuals to avoid blur/effect swapping on task stripes entirely. New mode uses pure-black global overlay + centered text label on focused task; non-focused tasks simply dim via paint overlay. Also separated long-press from click-to-edit flow to prevent accidental editor activation during focus entry.

---

## Stats

| Total | Open | Resolved | Won't Fix |
|-------|------|----------|-----------|
| 15 | 0 | 15 | 0 |
