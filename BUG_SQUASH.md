# Lemon Do Bug Log (Active + Recent)

Last updated: 2026-03-03 00:54:00 (Antigravity Maintenance)

## Active Bugs

None currently tracked.

## Recently Resolved

### BUG-021: Startup failure after shadow render change
- Severity: critical
- Status: resolved
- Fix: removed brittle inner-shadow paint path; simplified startup render flow.

### BUG-022: Bird's Eye not interactive
- Severity: high
- Status: resolved
- Fix: added hover/click hit testing and day-selected signal pipeline.

### BUG-023: Date label leak into Bird's Eye/restore
- Severity: medium
- Status: resolved
- Fix: hide date label on Bird's Eye entry; only show during cell hover.

### BUG-024: Clock font size overridden
- Severity: medium
- Status: resolved
- Fix: removed conflicting stylesheet font-size override on overlay body.

### BUG-025: Day swipe could leave tasks visually missing
- Severity: high
- Status: resolved
- Fix: added graphics-effect cleanup and stricter animation interrupt/snap handling.

### BUG-026: Right-click erased task text
- Severity: high
- Status: resolved
- Fix: removed right-click reset behavior from task stripes.

## Regression Watchlist

- Queue timing interactions between add/complete/delete.
- Mode transitions involving focus + hibernate + overlay restore.
- Bird's Eye hover/click behavior near grid edges.

## Summary

- Open: 0
- Recently resolved listed here: 6

