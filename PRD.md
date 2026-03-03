# Lemon Do PRD (Current Build)

Last updated: 2026-03-03 00:54:00 (Antigravity Maintenance)

## Product Goal

Lemon Do is a compact always-on-top PyQt6 task widget for daily execution with:
- very low interaction friction,
- strong visual feedback,
- day-based persistence/history,
- minimalist overlays (Hotkeys, Clock, Stats, Bird's Eye).

## Core UX Principles

- Inline-first editing (no modal forms).
- Fast keyboard + mouse control.
- Animations should feel smooth but never block normal interaction.
- Visual minimalism over dense controls.

## Active Feature Set

### Tasks
- Inline editable task stripes (`EMPTY`, `ACTIVE`, `COMPLETED`).
- Hover affordances: complete (`✓`) and delete (`✕`).
- Completion moves tasks into the completed archive stack.
- Completed stack can accordion open; completed tasks can be reopened.
- Deletion uses delayed queue behavior:
  - immediate red state,
  - 1.5s hold,
  - queued delete animation/removal.
- Add/completion actions also use 1.5s queued hold before animation execution.

### Layout + Visuals
- Frameless, translucent, always-on-top window.
- Pill-shaped clipping/mask.
- Dynamic time-based color engine (minute-driven interpolation).
- Bottom-center minimalist lemon logo (30% opacity).
- Past-day label appears when viewing previous dates.

### Time + History
- SQLite persistence by day (`tasks` table).
- Real calendar day navigation with left/right keys.
- Swipe transition on day changes.
- Daily reset behavior when app time crosses day boundary.

### Focus + Hibernate
- Focus mode enters on long-press task.
- Focus mode shows black backdrop; focused task centered.
- Hibernate enters by right-click window or idle timeout.
- Hibernate restore preserves overlay/focus context.

### Overlay Views
- `Space`: Hotkeys
- `C`: Clock
- `S`: Stats
- `B`: Bird's Eye yearly grid
- `Q`: Return to today/default view

Bird's Eye specifics:
- 365-day grid.
- Filled black square means day has >= 3 completed tasks.
- Hover shows that day at top.
- Click jumps directly to selected day.

## Keyboard Map (Canonical)

- `Left` / `Right`: navigate day history
- `Tab` / `Shift+Tab`: task traversal/creation flow
- `B`: Bird's Eye overlay
- `Space`: Hotkeys overlay
- `C`: Clock overlay
- `S`: Stats overlay
- `Q`: return to today/default task view
- `Up` / `Down`: debug time offset (+/-10m)
- `R`: reset debug time offset
- `H`: toggle debug time chip
- `N`: nuke all task data
- `Esc`: close app

## Explicitly Removed/Deprecated

- `A` toggle for plus button (removed).
- `P` toggle for nav arrows (removed).
- Visible nav arrow controls (removed from UX).
- Right-click task reset behavior (removed).

## Data Model (Required)

### `tasks`
- `day TEXT`
- `task_id INTEGER`
- `status TEXT` (`EMPTY` | `ACTIVE` | `COMPLETED`)
- `text TEXT`
- `completion_rank INTEGER`
- primary key: `(day, task_id)`

### `app_stats`
- `key TEXT PRIMARY KEY`
- `value INTEGER`
- stores lifetime counters (clicks, created, deleted, completed)

## Non-Goals

- Multi-user sync/cloud.
- Rich categorization/tags/projects.
- Complex settings UI.

