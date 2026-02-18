# Lemon Do — Product Requirements Document

> **Status:** Implemented (active polish)
> **Last updated:** 2026-02-18

---

## 1. Overview

**Product name:** Lemon Do  
**One-liner:** A compact desktop productivity widget with living color transitions and tactile task stacking.

### Vision

Lemon Do is a tiny, always-visible task surface designed for low-friction daily execution.  
It emphasizes visual rhythm (time-based palette shifts), direct inline editing, and a satisfying “file-away” completion stack.

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

---

## 3. Functional Requirements

### 3.1 Core Features

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| F-001 | Frameless, always-on-top translucent widget | P0 | Implemented |
| F-002 | Pill-shaped clip-mask shell | P0 | Implemented |
| F-003 | Inline editable task stripes | P0 | Implemented |
| F-004 | Time keyframe color engine | P0 | Implemented |
| F-005 | 1-second threshold transition animation | P0 | Implemented |
| F-006 | Sleep lockout (22:00–04:00) | P0 | Implemented |
| F-007 | Stacking completion system | P0 | Implemented |
| F-008 | Dynamic “+” task creation button | P1 | Implemented |
| F-009 | Keyboard task traversal (Tab / Shift+Tab) | P1 | Implemented |
| F-010 | Debug time controls + overlay toggle | P2 | Implemented |
| F-011 | Custom fonts (Lexend + Quicksand) | P1 | Implemented |

### 3.2 Feature Details

#### F-001: Window Shell

- Frameless window with translucent background and always-on-top behavior.
- Dragging supported via mouse press/move/release events.

#### F-002: Pill Geometry + Clipping

- Pill outline is defined with `QPainterPath`.
- Resize mask is applied from the pill polygon to prevent overhang.
- Paint pass also clips by pill path before drawing.

#### F-003: Task Stripe Interaction

- Task stripes are full-width and inline-editable (`QTextEdit`).
- Empty stripes use italic text, active stripes use regular text.
- Completed stripes become read-only and visually greyed.
- Right-click resets a stripe to empty (dev helper).

#### F-004: Task Completion Flow

- Completion trigger via hover check-mark button (`✓`).
- Completion animation sequence:
  1. grey-out fade + fireworks,
  2. completed stripe slides to pile,
  3. remaining stripes and `+` settle to new spacing.

#### F-005: Dynamic Task Addition

- Small `+` button creates a new stripe.
- `+` visibility toggled by `A` key.
- New stripe enters from the right with staged slide timing.

#### F-006: Keyboard Navigation

- `Tab` moves focus to next active stripe.
- `Shift+Tab` moves focus to previous active stripe.

#### F-007: Time-Based Color Engine

- Current minute drives interpolation between keyframes:
  - 04:00 → 15:59: yellow/orange background progression
  - 16:00 → 21:59: flipped blue/purple background + warm stripes
  - 22:00 → 04:00: black lockout mode
- Palette threshold changes animate with `QVariantAnimation` over 1 second.

#### F-008: Sleep Mode

- Background fades to black and text to white.
- Task stripes hidden; “Go to bed, come back tomorrow.” label shown.

---

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Platform | Python + PyQt6 desktop app |
| Min window size | At least `300 x 820` |
| Responsiveness | Dragging, typing, and hover interactions feel immediate |
| Rendering safety | Clip mask must prevent stripe overhang outside pill |
| Stability | Completion/add animations should not clip or hide tasks unexpectedly |

---

## 5. Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | PyQt6 |
| Language | Python 3.x |
| Entry point | `lemon_do.pyw` |
| Typography | Lexend (tasks), Quicksand Bold (title) |
| Rendering | `QPainter`, `QPainterPath`, `QRegion`, dynamic widget styles |
| Animation | `QPropertyAnimation`, `QVariantAnimation`, easing curves |

---

## 6. Milestones

| Milestone | Status | Deliverables |
|-----------|--------|--------------|
| M1 — Core widget shell | Done | Frameless pill, dragging, top-level structure |
| M2 — Living color engine | Done | Keyframe interpolation + threshold fades |
| M3 — Interaction polish | Done | Inline edit, hover complete, fireworks |
| M4 — Stack behavior | Done | Completed pile + staged relayout |
| M5 — Dynamic tasks | Done | `+` button task creation + keyboard toggle/focus travel |
| M6 — Stability hardening | In progress | Ongoing animation glitch/crash fixes |

---

## 7. Open Questions

- [ ] Persist tasks across app restarts?
- [ ] Persist widget location between launches?
- [ ] Expose stack spacing/animation timing as user settings?
- [ ] Keep dev reset behavior in production build?

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-02-18 | AI | Converted template PRD into concrete product doc. |
| 2026-02-18 | AI | Updated PRD to match stack engine, `+` flow, keyboard traversal, and active animation/stability work. |
# Lemon Do — Product Requirements Document

> **Status:** Implemented
> **Last updated:** 2026-02-18

---

## 1. Overview

**Product name:** Lemon Do
**One-liner:** A minimal desktop productivity widget with time-driven living colors.

### Vision

Lemon Do helps users focus on a tiny, constrained to-do surface: exactly three task slots.
The widget stays present but non-intrusive, using gradual color shifts across the day to signal pace and energy without requiring user setup.

### Target Users

| Persona | Description |
|---------|-------------|
| Focused solo worker | Wants a simple, always-visible reminder widget without a full task manager. |
| Student or maker | Needs light structure and visual momentum through the day. |
| Minimalist desktop user | Prefers low-friction tools with no complex navigation. |

---

## 2. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Preserve simplicity | Number of visible task slots | Fixed at exactly 3 |
| Keep interaction delightful | Task completion interaction quality | Hover check-mark + bounce + confetti |
| Communicate daily rhythm | Color transition behavior | Smooth minute-level keyframe interpolation |
| Enforce rest boundary | Night behavior | Hard stop from 22:00 to 04:00 with sleep message |

---

## 3. Functional Requirements

### 3.1 Core Features

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| F-001 | Frameless always-on-top translucent widget | P0 | Implemented |
| F-002 | Vertical pill-shaped window with clip mask | P0 | Implemented |
| F-003 | Exactly three inline-editable task stripes | P0 | Implemented |
| F-004 | Keyframe color interpolation (4-segment schedule) | P0 | Implemented |
| F-005 | Hard-stop sleep mode (22:00-04:00) | P0 | Implemented |
| F-006 | Window dragging for frameless shell | P0 | Implemented |
| F-007 | Hover check-mark completion button | P0 | Implemented |
| F-008 | Completion bounce animation | P1 | Implemented |
| F-009 | Confetti particle system (25 particles) | P1 | Implemented |
| F-010 | Time-travel debug controls (arrow keys) | P2 | Implemented |
| F-011 | Toggleable debug time overlay (H key) | P2 | Implemented |
| F-012 | Luminance-based contrast text colors | P1 | Implemented |
| F-013 | Custom font loading (Lexend + Quicksand) | P1 | Implemented |

### 3.2 Feature Details

#### F-001: Widget Shell and Window Behavior

- **Description:** Desktop widget uses `FramelessWindowHint`, `WA_TranslucentBackground`, and always-on-top.
- **Acceptance criteria:**
  - [x] Window has no native frame chrome.
  - [x] Window is translucent and visually custom-painted.
  - [x] Window remains above normal app windows.

#### F-002: Vertical Pill Shape

- **Description:** Window mask and background are pill-shaped via `QPainterPath` rounded rectangle.
- **Acceptance criteria:**
  - [x] Top and bottom have rounded caps.
  - [x] Clipping mask trims child widgets (stripes) to fit pill silhouette.
  - [x] Shape and paint use `QRectF` for PyQt6 compatibility.

#### F-003: Inline-Editable Task Stripes

- **Description:** Three edge-to-edge "stripe" widgets containing inline `QTextEdit` fields.
- **Acceptance criteria:**
  - [x] Tasks are always editable (no Enter-to-lock gate).
  - [x] Empty stripes show italic font; active stripes show regular font.
  - [x] No placeholder text; hover highlight indicates interactivity.
  - [x] Text wraps and stripe height auto-expands.
  - [x] Right-click force-resets any slot (dev tool).

#### F-004: Keyframe Color Schedule

- **Description:** Minute-accurate linear interpolation across a 4-segment 24-hour schedule.
- **Acceptance criteria:**
  - [x] `lerp_color` drives smooth transitions between keyframe pairs.
  - [x] Background painted directly using interpolated `QColor`.
  - [x] Stripe stylesheets regenerated dynamically with interpolated RGB.

##### Daytime (04:00-15:59)

- Start (04:00): Background `#FAEE69` (Morning Yellow), Stripes `#1A237E` (Dark Blue)
- End (15:59): Background `#FF9933` (Deep Orange), Stripes `#0D47A1` (Navy Blue)

##### Dark-Mode Flip (16:00-21:59)

- Start (16:00): Background `#3C98E8` (Sky Blue), Stripes `#FF9933` (Orange)
- End (21:59): Background `#442F72` (Deep Purple), Stripes `#FCFCDE` (Cream)

##### Hard Stop (22:00-04:00)

- Background: `#000000`
- Text: White
- UI: Hide all task stripes and show: "Go to bed, come back tomorrow."

#### F-005: Hover Check-Mark Completion

- **Description:** A `✓` button appears on the right side of a stripe when hovered over an active task.
- **Acceptance criteria:**
  - [x] Check button only visible when stripe is hovered and task is active.
  - [x] Clicking check triggers bounce animation + confetti.
  - [x] Completed task becomes read-only with strikethrough text.
  - [x] No accidental completions while editing.

#### F-006: Dragging

- **Description:** Frameless window can be dragged by mouse.
- **Acceptance criteria:**
  - [x] `mousePressEvent` records drag offset.
  - [x] `mouseMoveEvent` moves window while left button held.
  - [x] `mouseReleaseEvent` clears drag state.

#### F-007: Time-Travel Debug Mode

- **Description:** Keyboard shortcuts offset simulated time for QA testing.
- **Acceptance criteria:**
  - [x] Right/Left arrow: +/- 1 hour.
  - [x] Up/Down arrow: +/- 10 minutes.
  - [x] R key: reset to real time.
  - [x] Esc key: close app.
  - [x] H key: toggle debug time overlay visibility.
  - [x] Debug overlay hidden by default.

#### F-008: Luminance-Based Contrast

- **Description:** `get_contrast_color()` returns black or white text based on perceived luminance.
- **Acceptance criteria:**
  - [x] Applied to stripe task text.
  - [x] Applied to debug overlay text.
  - [x] Applied to title label.

#### F-009: Custom Typography

- **Description:** Loads Lexend and Quicksand `.ttf` files from the local `fonts/` directory.
- **Acceptance criteria:**
  - [x] Lexend set as app-wide default font.
  - [x] Quicksand Bold used for the title label.
  - [x] Graceful fallback to system fonts if files are missing.

---

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Platform | Desktop application built with PyQt6 (Python 3.x). |
| Visual smoothness | Color updates every 60 seconds; transitions appear gradual. |
| Responsiveness | Dragging and click feedback feel immediate. |
| Stability | `lerp_color` clamps interpolation to `0.0..1.0`. |
| Maintainability | Color keyframes and constants centralized in widget class. |
| Minimum window size | 300px wide x 820px tall in all modes. |

---

## 5. Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | PyQt6 |
| Language | Python 3.x |
| Entry point | `lemon_do.pyw` |
| Rendering | `QPainter`, `QPainterPath`, `QColor`, dynamic QSS |
| Runtime Scheduling | `QTimer` (1-min color + 16ms particle + 80ms ambient) |
| Typography | Lexend (tasks), Quicksand Bold (title) via `QFontDatabase` |
| Persistence | None (tasks reset on restart) |

---

## 6. Milestones

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| M1 - Core Shell | Done | Frameless widget, pill rendering, dragging |
| M2 - Living Color MVP | Done | 3-phase interpolation + hard-stop sleep mode |
| M3 - Delight Layer | Done | Bounce animation + confetti particles |
| M4 - Debug Tools | Done | Time-travel keyboard controls + debug overlay |
| M5 - Task Lifecycle | Done | EMPTY/ACTIVE/COMPLETED one-shot states |
| M6 - Inline Editing | Done | Always-editable stripes, hover check-mark completion |
| M7 - Visual Polish | Done | Keyframe color engine, contrast text, custom fonts, stripe layout |
| M8 - Next Iteration | TBD | Local persistence, startup position memory |

---

## 7. Open Questions

- [x] Should task text be editable inline or through a settings dialog? **Resolved: inline always-editable.**
- [ ] Should task labels persist between launches (JSON file)?
- [ ] Should startup position be remembered across sessions?
- [ ] Should users be allowed to configure phase times/colors, or stay fixed by design?

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-02-18 | AI | Initial PRD template created. |
| 2026-02-18 | AI | Replaced template with concrete PRD aligned to implemented behavior. |
| 2026-02-18 | AI | Full rewrite reflecting inline editing, keyframe color engine, hover check-mark, custom fonts, and stripe layout. |
