# Lemon Do — Bug Squash Log

> Track every bug found, investigated, and resolved.
> **Last updated:** 2026-02-18

---

## Active Bugs

### BUG-004: Completion animation clipping / disappearing stripes

- **Severity:** high
- **Status:** investigating
- **Found:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_animate_completion_sequence`, `relayout_stripes`)
- **Symptoms:** During completion flow, lower stripes can appear truncated/disappear, then reappear.
- **Current hypothesis:** Wrapper height and animation target geometry can temporarily diverge during multi-stage transitions.

### BUG-005: Add task animation instability

- **Severity:** high
- **Status:** investigating
- **Found:** 2026-02-18
- **File(s):** `lemon_do.pyw` (`_animate_add_task_sequence`)
- **Symptoms:** Add-task flow can still crash or become unstable depending on timing/order of animations.
- **Current hypothesis:** Parallel animation lifecycle and geometry synchronization around add sequence still need hardening.

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

### BUG-003: Tracked file mismatch during `.py` -> `.pyw` transition

- **Severity:** medium
- **Status:** resolved
- **Found:** 2026-02-18
- **Resolved:** 2026-02-18
- **File(s):** Repository
- **Root cause:** Old tracked file removed while new entry file was initially untracked.
- **Fix:** Added and pushed `lemon_do.pyw` as canonical app entry point.

---

## Stats

| Total | Open | Resolved | Won't Fix |
|-------|------|----------|-----------|
| 5 | 2 | 3 | 0 |
