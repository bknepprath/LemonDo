# Lemon Do — Product Requirements Document

> **Status:** MVP Implemented
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
| Keep interaction delightful | Task completion interaction quality | Button bounce + confetti on click |
| Communicate daily rhythm | Color transition behavior | Smooth minute-level interpolation (no abrupt daytime switches) |
| Enforce rest boundary | Night behavior | Hard stop from 22:00 to 04:00 with sleep message |

---

## 3. Functional Requirements

### 3.1 Core Features

| ID | Feature | Priority | Status |
|----|---------|----------|--------|
| F-001 | Frameless always-on-top translucent widget | P0 | Implemented |
| F-002 | Vertical pill-shaped window rendering | P0 | Implemented |
| F-003 | Exactly three task buttons | P0 | Implemented |
| F-004 | Continuous color interpolation by time | P0 | Implemented |
| F-005 | Hard-stop sleep mode (22:00-04:00) | P0 | Implemented |
| F-006 | Window dragging for frameless shell | P0 | Implemented |
| F-007 | Completion bounce animation | P1 | Implemented |
| F-008 | Confetti particle system (25 particles) | P1 | Implemented |

### 3.2 Feature Details

#### F-001: Widget Shell and Window Behavior

- **Description:** Desktop widget uses `FramelessWindowHint`, `WA_TranslucentBackground`, and always-on-top behavior.
- **Acceptance criteria:**
  - [x] Window has no native frame chrome.
  - [x] Window is translucent and visually custom-painted.
  - [x] Window remains above normal app windows.

#### F-002: Vertical Pill Shape

- **Description:** Window mask and background are pill-shaped via `QPainterPath` rounded rectangle.
- **Acceptance criteria:**
  - [x] Top and bottom have rounded caps.
  - [x] Painting path uses anti-aliasing.
  - [x] Shape and paint use `QRectF` to satisfy PyQt6 overload typing.

#### F-003: Fixed 3-Slot Task Surface

- **Description:** UI shows exactly three large, pill-style task buttons.
- **Acceptance criteria:**
  - [x] Only three task slots are displayed.
  - [x] Buttons have white text and rounded style.
  - [x] No dynamic add/remove task controls are present.

#### F-004: Living Color System (Minute-Level Interpolation)

- **Description:** Color values are computed every minute using linear interpolation (`lerp_color`) from current minute of day.
- **Acceptance criteria:**
  - [x] No static block-switching during active phases.
  - [x] `current_minute` in range `0..1439` drives state.
  - [x] Background is painted directly using interpolated `QColor`.
  - [x] Button stylesheet is regenerated dynamically using interpolated RGB.

##### Phase 1: The Awakening (04:00-16:00)

- Start: Background `#FFF9C4`, Buttons `#1A237E`
- End: Background `#FFB74D`, Buttons `#0D47A1`
- Behavior: Linear interpolation from 04:00 to 16:00.

##### Phase 2: The Twilight Shift (16:00-22:00)

- Start: Background `#FFB74D`, Buttons `#0D47A1`
- End: Background `#311B92`, Buttons `#FFD54F`
- Behavior: Linear interpolation from 16:00 to 22:00.

##### Phase 3: Hard Stop (22:00-04:00)

- Background: `#000000`
- Text: White
- Behavior: No interpolation; hard-state mode.
- UI: Hide all task buttons and show: "Go to bed, come back tomorrow."

#### F-005: Dragging

- **Description:** Frameless window can be dragged by mouse.
- **Acceptance criteria:**
  - [x] `mousePressEvent` records drag offset.
  - [x] `mouseMoveEvent` moves window while left button held.
  - [x] `mouseReleaseEvent` clears drag state.

#### F-006: Completion Interaction

- **Description:** Clicking a task triggers a squash-and-bounce animation plus confetti burst.
- **Acceptance criteria:**
  - [x] Button shrinks to ~90% then returns with bounce easing.
  - [x] 25 particles spawn near click point.
  - [x] Particles move outward, drift downward via gravity, and fade out.

---

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Platform | Desktop application built with PyQt6. |
| Visual smoothness | Color updates occur every 60 seconds; transitions appear gradual over day phases. |
| Responsiveness | Dragging and click feedback feel immediate on standard hardware. |
| Stability | `lerp_color` clamps interpolation factor to `0.0..1.0` to avoid invalid RGB math. |
| Maintainability | Time-phase constants and colors are centralized in widget class constants. |

---

## 5. Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | PyQt6 |
| Language | Python 3.x |
| Rendering | `QPainter`, `QPainterPath`, `QColor`, dynamic QSS |
| Runtime Scheduling | `QTimer` (1-minute color scheduler + frame particle timer) |
| Persistence | None in MVP |

---

## 6. Milestones

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| M1 - Core Shell | Done | Frameless widget, pill rendering, dragging |
| M2 - Living Color MVP | Done | 3-phase interpolation + hard-stop sleep mode |
| M3 - Delight Layer | Done | Bounce animation + confetti particles |
| M4 - Next Iteration | TBD | Editable task labels and local persistence |

---

## 7. Open Questions

- [ ] Should task text be editable inline or through a small settings dialog?
- [ ] Should task labels persist between launches (JSON file)?
- [ ] Should startup position be remembered across sessions?
- [ ] Should users be allowed to configure phase times/colors, or stay fixed by design?

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-02-18 | AI | Replaced template with concrete Lemon Do PRD aligned to implemented PyQt6 widget behavior. |
