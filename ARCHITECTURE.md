# Lemon Do — Architecture & Project Context

> **Purpose:** Quick technical orientation for contributors and AI agents.
> **Last updated:** 2026-02-18

---

## Project Summary

Lemon Do is a single-window PyQt6 desktop widget featuring a pill mask, inline task editing, a dynamic color clock, animated dual-zone completion stacking, SQLite-backed day history, and a hibernate mode for minimal desktop persistence.

---

## Directory Map

```
Lemon Do/
├── lemon_do.pyw          # Application entry point
├── lemon_do_history.db   # SQLite task history (auto-created at runtime)
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
   - Drag handling via mouse events
   - Pill clipping/mask in `resizeEvent` + `paintEvent`
   - Owns layout, animation state, history/DB connection, idle timer

2. **Task stripes (`TaskStripe`)**
   - Inline editable text area (`StripeTextEdit`)
   - State machine: `EMPTY`, `ACTIVE`, `COMPLETED`
   - Hover buttons: check-mark (`✓`) and trash (`✕`)
   - Emits: `completed`, `height_changed`, `state_changed`, `focus_move_requested`, `completed_clicked`, `delete_requested`

3. **Controls**
   - `+` task add button (toggle via `A`)
   - Back/forward navigation buttons (toggle via `P`)
   - Date label (visible when viewing past days)
   - Debug time label (bottom, toggle via `H`)

4. **Particle overlay (`ParticleOverlay`)**
   - Top-most transparent widget
   - Renders confetti particles above all stripe/button content
   - Clipped by pill path

5. **Focus layer**
   - Long-press task interaction enters focus mode
   - Applies blur/tint backdrop to non-focused UI
   - Uses per-stripe dim overlays (instead of blur effects on stripes) for safer effect lifecycle
   - Focused task renders a spinner indicator

### Time Engine

- Uses simulated app time: `datetime.now() + time_offset`
- Minute-to-keyframe interpolation drives:
  - window background color
  - stripe base color
  - derived contrast text colors
- Threshold crossings animate via `QVariantAnimation` (1s)

### Persistence Layer

- SQLite database (`lemon_do_history.db`) with WAL journaling
- Schema: `tasks(day TEXT, task_id INT, status TEXT, text TEXT, completion_rank INT)`
- Primary key: `(day, task_id)`
- Index: `(day, status)` for fast retrieval
- Auto-save on: task state change, completion, deletion, day navigation, app close
- New-day detection: saves current day, clears new day's slate, reloads

---

## Layout Engine — Floating Zones

### Zone Architecture

| Zone | Anchor | Contents |
|------|--------|----------|
| Completed Archive | 25% of window height | Stacked completed tasks (tight ribbon pile or accordion-expanded) |
| Active Zone | 40% of window height | Uncompleted tasks, adapts slightly upward as list grows |
| Floating Buffer | 150px minimum | Guaranteed separation between archive bottom and active top |

### Accordion

- Closed: completed tasks overlap by `completed_step` (12px)
- Open: completed tasks spread to full height + gap
- Active zone shifts downward in real-time to maintain the 150px buffer

### Wrapper Height

- `_compute_animation_bounds()` ensures wrapper covers both current and target geometries during animation
- Prevents clipping/truncation during any transition

---

## Animation System

### Spam-Safe Architecture

- All action flows (add/delete/complete) follow Immediate Phase → Settling Phase pattern
- `_interrupt_and_snap_animations()` stops all running animations and snaps widgets to final positions
- Animation epoch counter invalidates stale callbacks
- `recenter_ui()` provides unified settling

### Completion (staged)

1. Layout freeze + geometry snapshot (global→local coordinates)
2. Grey-out fade + fireworks (no movement)
3. Completed stripe slides to archive pile
4. `recenter_ui()` settles remaining stripes

### Add Task (staged)

1. `+` button drops down with `OutBack` easing
2. New stripe slides in from right with cubic-bezier(0.22, 1, 0.36, 1)
3. `recenter_ui()` settling

### Deletion (meltdown)

1. Red color shift (120ms)
2. Gravity drop + opacity dissolve (360ms, parallel)
3. Widget removal + `recenter_ui()` settling

### Hibernate

- Entry: shrink + fade to slim 38×30 pill at screen edge (280ms `OutCubic`)
- Exit: pop back to saved geometry (240ms `OutBack`)
- Hover: 5% scale-up + opacity bump (100ms animated)

### Focus Mode

- Entry: 500ms long-press on an uncompleted task
- Focused task animates to vertical center
- Header/nav/add controls receive blur; non-focused stripes use local dim overlay
- A tint overlay follows current background color
- Exit: single click anywhere restores baseline UI state and layout

---

## Key Data / State

| State | Owner | Meaning |
|-------|-------|---------|
| `buttons` | `LemonDoWidget` | Ordered task stripe widgets |
| `completion_rank` | `TaskStripe` | Ordering index in completed pile |
| `completion_fade` | `TaskStripe` | Progress value for grey transition |
| `is_deleting` | `TaskStripe` | Whether meltdown animation is active |
| `time_offset` | `LemonDoWidget` | Debug time shift |
| `sleep_mode` / `pending_sleep_mode` | `LemonDoWidget` | Mode + transition state |
| `add_button_visible` | `LemonDoWidget` | Whether `+` is currently shown |
| `nav_controls_visible` | `LemonDoWidget` | Whether back/forward buttons shown |
| `_accordion_open` | `LemonDoWidget` | Whether completed pile is expanded |
| `_animation_epoch` | `LemonDoWidget` | Counter to invalidate stale animation callbacks |
| `_completion_in_progress` | `LemonDoWidget` | Guard to suppress relayout during completion |
| `is_hibernated` | `LemonDoWidget` | Whether in hibernate state |
| `_focus_mode_active` | `LemonDoWidget` | Whether focus mode is active |
| `_focused_stripe` | `LemonDoWidget` | Task currently centered in focus mode |
| `view_date` / `today_date` | `LemonDoWidget` | History navigation state |
| `db` | `LemonDoWidget` | SQLite connection for task persistence |

---

## Interaction Map

| Action | Result |
|--------|--------|
| Click stripe | Enter/continue inline editing |
| Hover active stripe | Show `✓` and `✕` buttons |
| Click `✓` | Completion sequence + confetti |
| Click `✕` | Meltdown deletion sequence |
| Right-click stripe | Reset stripe to empty |
| Click completed pile | Accordion open |
| Click completed task (accordion open) | Un-check → move to active list |
| Press `Tab` | Create task (if none/at bottom) or focus next |
| Press `Shift+Tab` | Focus previous active stripe |
| Press `A` | Toggle `+` button visibility |
| Press `P` | Toggle history navigation controls |
| Press `N` | Nuke all task data |
| Press arrows / `R` | Time-travel debug |
| Press `H` | Toggle debug time label |
| Press `Esc` | Close app |
| Right-click window background | Enter hibernate mode |
| Left-click while hibernated | Exit hibernate mode |
| 10 min idle | Auto-hibernate |

---

## Known Technical Risks

- Complex nested animation groups can race if widget geometry/layout is mutated mid-sequence.
- `stripe_wrapper` height must always cover both current and target positions during movement to avoid clipping.
- Mask behavior differs by platform; code uses polygon mask fallback for compatibility.
- `QGraphicsOpacityEffect` used during deletion can conflict with `QGraphicsDropShadowEffect` on the same widget; handled by using a separate effect instance.
- Replacing task-level graphics effects can invalidate shadow effect objects; focus mode now avoids applying blur directly to task stripes.
- Frequent iteration in animation logic means regressions can reappear unless run-time tested after each tweak.
- Hibernate mode uses `screen.geometry()` for positioning; multi-monitor setups may need primary-screen detection.

---

## Conventions

| Area | Convention |
|------|-----------|
| Naming | `snake_case` funcs/vars, `PascalCase` classes |
| Entry file | `lemon_do.pyw` |
| Font loading | `QFontDatabase.addApplicationFont` scanning `fonts/` |
| Persistence | SQLite WAL mode, auto-save on state change |
| Markdown docs | Keep PRD/architecture/bug log synchronized after behavior changes |
