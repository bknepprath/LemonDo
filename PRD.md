# Lemon Do — Product Requirements Document

> **Status:** Implemented (active polish)
> **Last updated:** 2026-02-18

---

## 1. Overview

**Product name:** Lemon Do
**One-liner:** A compact desktop productivity widget with living color transitions, tactile task stacking, persistent history, and a minimalist hibernate mode.

### Vision

Lemon Do is a tiny, always-visible task surface designed for low-friction daily execution.
It emphasizes visual rhythm (time-based palette shifts), direct inline editing, satisfying completion animations, and day-to-day task history — all in a delightfully small footprint.

### Target Users

| Persona | Description |
|---------|-------------|
| Focused solo worker | Wants minimal overhead and quick keyboard/mouse interactions. |
| Student or maker | Needs a persistent, lightweight prompt for a few key tasks. |
| Visual flow user | Prefers ambient color cues and motion feedback over heavy controls. |

---

## 2. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Keep workflow friction low | Steps to add/edit/complete a task | Inline edit + one-click complete |
| Preserve visual delight | Completion interaction quality | Fireworks + staged stack animation |
| Communicate daily phase | Color behavior | Minute-based interpolation + threshold fades |
| Enforce shutdown boundary | Night lockout behavior | Hard stop 22:00–04:00 |
| Persist task history | Day-over-day retrieval | SQLite DB with back/forward navigation |
| Minimize desktop footprint | Idle behavior | Auto-hibernate to tiny pill after 10 min idle |

---

## 3. Functional Requirements

### 3.1 Core Features

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| F-001 | Frameless, always-on-top translucent widget | P0 | Implemented |
| F-002 | Pill-shaped clip-mask shell | P0 | Implemented |
| F-003 | Inline editable task stripes | P0 | Implemented |
| F-004 | Time keyframe color engine (4-segment) | P0 | Implemented |
| F-005 | 1-second threshold transition animation | P0 | Implemented |
| F-006 | Sleep lockout (22:00–04:00) | P0 | Implemented |
| F-007 | Stacking completion system (dual-zone) | P0 | Implemented |
| F-008 | Dynamic "+" task creation button (A key) | P1 | Implemented |
| F-009 | Keyboard task traversal (Tab / Shift+Tab) | P1 | Implemented |
| F-010 | Debug time controls + overlay toggle (H key) | P2 | Implemented |
| F-011 | Custom fonts (Lexend + Quicksand) | P1 | Implemented |
| F-012 | SQLite task persistence + daily reset | P0 | Implemented |
| F-013 | History navigation (back/forward via P toggle) | P1 | Implemented |
| F-014 | Accordion completed-pile interaction | P1 | Implemented |
| F-015 | Un-check completed tasks (click while accordion open) | P1 | Implemented |
| F-016 | Trash delete button per task (meltdown animation) | P1 | Implemented |
| F-017 | Hibernate mode (idle + right-click) | P1 | Implemented |
| F-018 | Nuke reset (N key) | P2 | Implemented |
| F-019 | Confetti particle overlay (top-layer) | P1 | Implemented |
| F-020 | Tab creates task when none exist or cursor at bottom | P1 | Implemented |
| F-021 | Focus mode via long-press (task centering + backdrop effects) | P2 | Implemented |

### 3.2 Feature Details

#### F-001: Window Shell

- Frameless window with translucent background and always-on-top behavior.
- Dragging supported via mouse press/move/release events.

#### F-002: Pill Geometry + Clipping

- Pill outline defined with `QPainterPath`.
- Resize mask applied from pill polygon to prevent overhang.
- Paint pass clips by pill path before drawing.

#### F-003: Task Stripe Interaction

- Task stripes are full-width and inline-editable (`QTextEdit`).
- Empty stripes use italic text, active stripes use regular text.
- Completed stripes become read-only with solid hard-gray background + drop shadow.
- Hover shows check-mark (`✓`) and trash (`✕`) buttons.
- Right-click resets a stripe to empty (dev helper).

#### F-007: Dual-Zone Layout

- **Completed Archive (25% zone):** Completed tasks slide to a stacked pile anchored at the 25% vertical mark. Solid gray with `QGraphicsDropShadowEffect`.
- **Active Zone (40% zone):** Uncompleted tasks anchor at the 40% vertical mark with adaptive vertical filling.
- **150px floating buffer:** Active zone is always >= 150px below the completed pile bottom, including when the accordion is open.

#### F-012: Persistence & History

- SQLite database (`lemon_do_history.db`) stores tasks keyed by `(day, task_id)`.
- Auto-saves on task change, completion, deletion, and close.
- New-day detection triggers save + fresh slate.
- Back/forward navigation buttons (toggled via `P`) with spam-safe animation interruption.
- Date label shows viewed date when browsing past days.

#### F-014: Accordion Interaction

- Clicking the completed pile opens an accordion: stacked ribbons slide apart with `OutCubic` easing.
- Clicking a completed task while accordion is open un-checks it: moves it to the bottom of the active list, restores time-based color, removes gray/shadow.

#### F-016: Deletion Meltdown

- 3-stage animated delete: red color shift → gravity drop → opacity dissolve.
- Widget removed from memory after dissolve completes.
- Remaining tasks settle via `recenter_ui()`.

#### F-017: Hibernate Mode

- **Entry:** Right-click context menu or 10-minute idle timer.
- **Hibernated state:** Window shrinks to a slim 38×30px pill, positioned relative to screen edges, at 20% opacity.
- **Hover:** 5% scale-up with a 100ms animation, then 100ms return on leave.
- **Exit:** Left-click restores original geometry and full opacity with an `OutBack` pop animation.

#### F-021: Focus Mode

- **Entry:** 500ms long-press on an uncompleted task.
- **Behavior:** Selected task animates to vertical center.
- **Backdrop effects:** Everything behind the focused task is blacked out (pure black overlay).
- **Text presentation:** Focused task text is centered both horizontally and vertically.
- **Editing behavior:** No cursor and no inline editing while in focus mode.
- **Exit:** Single click anywhere exits focus mode and restores normal layout.

#### F-018: Nuke Reset

- `N` key deletes all task data from the database and reloads a fresh state.

#### F-019: Top-Layer Fireworks

- Confetti particles render in a dedicated `ParticleOverlay` widget that sits above all other content.
- Pill-path clipping still applies.

#### F-020: Tab Hotkey

- Global `eventFilter` intercepts `Tab` before Qt's focus traversal can consume it.
- Creates a new task if no uncompleted tasks exist or cursor is in the bottom task.
- Otherwise moves focus to the next active stripe.

---

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Platform | Python + PyQt6 desktop app |
| Min window size | At least `300 x 820` |
| Responsiveness | Dragging, typing, and hover interactions feel immediate |
| Rendering safety | Clip mask must prevent stripe overhang outside pill |
| Animation stability | Completion/add/delete animations use epoch-guarded callbacks and wrapper-height bounds |
| Persistence | SQLite WAL mode for crash-safe writes |
| Idle behavior | Auto-hibernate after 10 minutes of no input |

---

## 5. Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | PyQt6 |
| Language | Python 3.x |
| Entry point | `lemon_do.pyw` |
| Typography | Lexend (tasks), Quicksand Bold (title) |
| Rendering | `QPainter`, `QPainterPath`, `QRegion`, dynamic widget styles |
| Animation | `QPropertyAnimation`, `QVariantAnimation`, easing curves, animation epoch guards |
| Persistence | SQLite via `sqlite3` (WAL mode) |
| Particles | Dedicated `ParticleOverlay` widget (top-layer) |

---

## 6. Milestones

| Milestone | Status | Deliverables |
|-----------|--------|--------------|
| M1 — Core widget shell | Done | Frameless pill, dragging, top-level structure |
| M2 — Living color engine | Done | Keyframe interpolation + threshold fades |
| M3 — Interaction polish | Done | Inline edit, hover complete, fireworks |
| M4 — Stack behavior | Done | Completed pile + staged relayout |
| M5 — Dynamic tasks | Done | `+` button task creation + keyboard toggle/focus travel |
| M6 — Stability hardening | Done | Animation epoch guards, wrapper-height bounds, interrupt-and-snap |
| M7 — Persistence & history | Done | SQLite DB, daily reset, back/forward navigation |
| M8 — Dual-zone layout | Done | 25%/40% floating zones, 150px buffer, accordion interaction |
| M9 — Deletion & controls | Done | Meltdown delete, trash button, nuke reset |
| M10 — Hibernate mode | Done | Right-click / idle entry, click-to-restore, screen-edge positioning |

---

## 7. Open Questions

- [ ] Should startup position be remembered across sessions?
- [ ] Should users be allowed to configure phase times/colors, or stay fixed by design?
- [ ] Keep dev reset (right-click) behavior in production build?

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-02-18 | AI | Initial PRD template created. |
| 2026-02-18 | AI | Replaced template with concrete PRD aligned to implemented behavior. |
| 2026-02-18 | AI | Full rewrite: persistence, history nav, dual-zone layout, accordion, deletion, hibernate, Tab hotkey, top-layer fireworks. |
| 2026-02-18 | AI | Added focus mode spec and updated hibernate geometry/hover animation behavior. |
| 2026-02-18 | AI | Focus mode redesign: pure black backdrop, centered task text, no cursor/editing in focus state, long-press/click separation hardening. |
