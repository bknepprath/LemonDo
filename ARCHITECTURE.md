# Lemon Do Architecture (Agent-Oriented)

Last updated: 2026-02-19

## Entry Point

- Main file: `lemon_do.pyw`
- Main class: `LemonDoWidget`

## Primary Components

### `LemonDoWidget` (orchestrator)
- Window shell, global state, timers, hotkeys.
- DB loading/saving.
- Mode switching (normal/focus/hibernate/overlays).
- Animation queue coordination (add/complete/delete/day-swipe).

### `TaskStripe`
- One task row with inline editor + state machine.
- Emits events to parent widget:
  - complete,
  - state changed,
  - delete requested,
  - focus interactions.

### Overlay Widgets
- `ParticleOverlay`: confetti rendering.
- `FocusOverlay`: focus-mode blackout interaction surface.
- `BirdsEyeGridWidget`: yearly grid render + hover/click hit-testing.
- `LemonLogoWidget`: minimal brand glyph.

## High-Value State Flags

- `_focus_mode_active`
- `is_hibernated`
- `_completion_in_progress`
- `_delete_in_progress`
- `_overlay_mode` (`hotkeys`, `clock`, `stats`, `birds`, `None`)
- `_pending_adds`, `_pending_completions`, `_pending_deletes` (queued hold flows)

## Critical Flows

### Task Completion
1. Stripe enters `COMPLETED`.
2. Completion is queued with 1.5s hold.
3. Completion animation runs and settles layout.

### Task Deletion
1. Stripe turns red immediately.
2. Deletion queued with 1.5s hold.
3. Delete animation executes, stripe removed, layout settles.

### Task Creation
1. Stripe created.
2. Add animation queued with 1.5s hold.
3. Add animation executes and layout settles.

### Day Navigation
1. Save current day.
2. Swipe-out current layout.
3. Load target day.
4. Swipe-in target layout.

### Bird's Eye Jump
1. Hover shows date label.
2. Click emits selected date.
3. Overlay closes and target day is loaded.

## Rendering Notes

- Window shape: pill path + mask.
- Background: dynamic color from time engine.
- Avoid fragile paint-time logic that can break startup.
- Keep overlays explicitly hidden/shown to prevent mode bleed-through.

## Persistence Notes

- SQLite WAL enabled.
- `tasks` table = per-day task history.
- `app_stats` table = lifetime counters.

## Hotkey Handling Strategy

- Main routing in `keyPressEvent`.
- Special handling via global `eventFilter` for keys that can be swallowed by focused editors.

## Safe Edit Guidance for Agents

- Prefer adding behavior via dedicated helper methods, not deeply nested lambdas.
- When changing animation flow, update queue/interrupt paths together.
- If introducing new mode flags, verify:
  - hibernate entry/exit,
  - focus entry/exit,
  - overlay transitions,
  - day navigation.
- After substantial edits, run lint checks on `lemon_do.pyw`.

