# Agent Guide (Quick Start)

Purpose: fastest path for a coding agent to make safe changes.

## Where to Work

- Code: `lemon_do.pyw`
- Product intent: `PRD.md`
- Technical map: `ARCHITECTURE.md`
- Bug status: `BUG_SQUASH.md`

## First Checks Before Editing

1. Identify impacted flow:
   - task add/complete/delete,
   - day navigation,
   - focus/hibernate,
   - overlays (hotkeys/clock/stats/birds).
2. Search for related state flags in `LemonDoWidget`.
3. Confirm whether queues/timers must be updated too.

## High-Risk Areas

- Animation interruption and snap logic.
- Cross-mode transitions (focus <-> hibernate <-> overlays).
- Paint/render code in startup path.
- Any behavior that touches `_pending_*` action queues.

## Required Validation After Edits

- Lint `lemon_do.pyw`.
- Manual smoke checks:
  - app launches,
  - task edit/complete/delete works,
  - day nav left/right works,
  - Bird's Eye hover + click jump works,
  - focus and hibernate transitions still restore correctly.

## Hotkeys (Current)

- Left/Right: day navigation
- Tab/Shift+Tab: task traversal
- B: Bird's Eye
- Space: Hotkeys
- C: Clock
- S: Stats
- Q: return to today/default view
- Up/Down: debug time +/-10m
- R: reset debug time
- H: toggle debug chip
- N: nuke data
- Esc: close

