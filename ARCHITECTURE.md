# Lemon Do — Architecture & Project Context

> **Purpose:** Quick technical orientation for contributors and AI agents.
> **Last updated:** 2026-02-18

---

## Project Summary

Lemon Do is a single-window PyQt6 desktop widget using a pill mask, inline task editing, a dynamic color clock, and animated completion stacking behavior.

---

## Directory Map

```
Lemon Do/
├── lemon_do.pyw
├── fonts/
│   ├── Lexend/
│   └── Quicksand/
├── PRD.md
├── ARCHITECTURE.md
└── BUG_SQUASH.md
```

---

## Runtime Model

### Core UI Layers

1. **Window shell (`LemonDoWidget`)**
   - Frameless, translucent, always-on-top
   - Drag handling
   - Pill clipping/mask in `resizeEvent` + `paintEvent`

2. **Task stripes (`TaskStripe`)**
   - Inline editable text area (`StripeTextEdit`)
   - State machine: `EMPTY`, `ACTIVE`, `COMPLETED`
   - Hover complete button (`✓`)
   - Emits completion/height/state/focus events

3. **Controls**
   - `+` task add button
   - Debug time label (bottom, toggle via `H`)

### Time Engine

- Uses simulated app time: `datetime.now() + time_offset`
- Minute-to-keyframe interpolation sets:
  - window background color
  - stripe base color
  - derived contrast text colors
- Threshold crossings animate via `QVariantAnimation` (1s)

---

## Animation System

### Completion (staged)

Current sequence in code:
1. Grey-out fade + fireworks (no movement)
2. Completed stripe slides to pile
3. Remaining stripes + `+` reposition

### Add task (staged)

Current sequence in code:
1. `+` button drops
2. New stripe slides in from right
3. Final settle/layout sync

---

## Key Data / State

| State | Owner | Meaning |
|------|-------|---------|
| `buttons` | `LemonDoWidget` | Ordered task stripe widgets |
| `completion_rank` | `TaskStripe` | Ordering index in completed pile |
| `completion_fade` | `TaskStripe` | Progress value for grey transition |
| `time_offset` | `LemonDoWidget` | Debug time shift |
| `sleep_mode` / `pending_sleep_mode` | `LemonDoWidget` | Mode + transition state |
| `add_button_visible` | `LemonDoWidget` | Whether `+` is currently shown |

---

## Interaction Map

| Action | Result |
|--------|--------|
| Click stripe | Enter/continue inline editing |
| Hover active stripe | Show `✓` complete button |
| Click `✓` | Completion sequence + confetti |
| Right-click stripe | Reset stripe to empty |
| Press `Tab` / `Shift+Tab` | Move focus between active stripes |
| Press `A` | Toggle `+` button visibility |
| Press arrows / `R` | Time-travel debug |
| Press `H` | Toggle debug time label |

---

## Known Technical Risks

- Complex nested animation groups can race if widget geometry/layout is mutated mid-sequence.
- `stripe_wrapper` height must always cover both current and target positions during movement to avoid clipping.
- Mask behavior differs by platform; code currently uses polygon mask fallback for compatibility.
- Frequent iteration in animation logic means regressions can reappear unless run-time tested after each tweak.

---

## Conventions

| Area | Convention |
|------|-----------|
| Naming | `snake_case` funcs/vars, `PascalCase` classes |
| Entry file | `lemon_do.pyw` |
| Font loading | `QFontDatabase.addApplicationFont` scanning `fonts/` |
| Markdown docs | Keep PRD/architecture/bug log synchronized after behavior changes |
