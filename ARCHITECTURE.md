# Lemon Do — Architecture & Project Context

> **Purpose:** Living shorthand so the AI (and any contributor) can quickly re-orient on the project without re-reading the entire codebase.
> **Last updated:** 2026-02-18

---

## Project Summary

**Lemon Do** is a frameless, always-on-top desktop productivity widget built with PyQt6. It provides exactly three inline-editable task slots inside a pill-shaped window whose colors shift smoothly throughout the day using minute-level keyframe interpolation.

---

## Directory Map

```
Lemon Do/
├── lemon_do.pyw          # Main application entry point (PyQt6 widget)
├── fonts/
│   ├── Lexend/           # Lexend font family (.ttf, OFL license)
│   │   ├── static/       # Static weight variants
│   │   └── Lexend-VariableFont_wght.ttf
│   └── Quicksand/        # Quicksand font family (.ttf, OFL license)
│       ├── static/       # Static weight variants
│       └── Quicksand-VariableFont_wght.ttf
├── PRD.md                # Product requirements document
├── ARCHITECTURE.md       # This file — project context & shorthand
├── BUG_SQUASH.md         # Bug tracking log
└── .cursor/rules/        # Cursor AI rules
```

---

## Key Decisions

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | Single-file app (`lemon_do.pyw`) | Keeps deployment trivial; no build step needed. | 2026-02-18 |
| 2 | `.pyw` extension | Suppresses console window on Windows launch. | 2026-02-18 |
| 3 | Inline editing (no popup dialogs) | Lower friction; tasks are always editable in-place. | 2026-02-18 |
| 4 | Hover check-mark for completion | Prevents accidental task completion while editing. | 2026-02-18 |
| 5 | Bundled fonts in `fonts/` directory | Ensures consistent typography without system font dependencies. | 2026-02-18 |
| 6 | Keyframe-based color schedule | Provides precise control over color transitions including the 16:00 dark-mode flip. | 2026-02-18 |
| 7 | No persistence layer | Tasks intentionally reset on restart (daily fresh start philosophy). | 2026-02-18 |

---

## Conventions

| Area | Convention |
|------|-----------|
| Naming | `snake_case` for functions/variables, `PascalCase` for classes |
| Branching | `main` only (single contributor) |
| Entry point | `lemon_do.pyw` |
| Font loading | `QFontDatabase.addApplicationFont` from `fonts/` directory |

---

## Module Overview

The entire app lives in a single file. Logical sections:

| Section | Classes / Functions | Purpose |
|---------|-------------------|---------|
| Utilities | `lerp_color()`, `get_contrast_color()`, `minute_of_day()` | Color math, luminance contrast, time helpers |
| Particle system | `Particle` dataclass | Confetti physics data |
| Inline editor | `StripeTextEdit` | Custom `QTextEdit` with click/double-click signals |
| Task stripe | `TaskStripe` | EMPTY/ACTIVE/COMPLETED lifecycle, inline editing, hover check-mark, bounce animation |
| Main widget | `LemonDoWidget` | Window shell, color engine, debug controls, layout, particle rendering |
| Bootstrap | `main()` | Font loading, app initialization |

---

## Data Flow

```
System Clock (+ optional time offset)
        │
        ▼
  minute_of_day() ──► Keyframe lookup ──► lerp_color()
        │                                      │
        ▼                                      ▼
  update_color_state()              background_color / button_color
        │                                      │
        ├──► apply_dynamic_styles() ◄──────────┘
        │         │
        │         ├──► Title label color (contrast-based)
        │         ├──► Sleep label color
        │         └──► TaskStripe.apply_theme() per stripe
        │
        ├──► update_debug_overlay()
        │
        └──► widget.update() ──► paintEvent()
                                    │
                                    ├──► Pill background fill
                                    ├──► Border stroke
                                    └──► Confetti particle rendering
```

### Task Interaction Flow

```
Empty stripe (italic, editable)
        │
        ▼  (user types text)
Active stripe (regular font, editable)
        │
        ▼  (hover reveals ✓ button → click)
Completed stripe (strikethrough, read-only, frozen)
        │
        ▼  (right-click: dev force-reset)
Empty stripe
```

---

## Known Constraints & Gotchas

- **`QRectF` requirement:** PyQt6's `QPainterPath.addRoundedRect` requires `QRectF`, not `QRect`. All rect conversions must wrap in `QRectF()`.
- **PowerShell `&&`:** The Windows shell does not support `&&` chaining. Use `;` to sequence git commands.
- **Minimum window size:** Hard floor of 300x820 prevents the pill from collapsing to a circle in sleep mode.
- **No persistence:** All task state is in-memory. Restarting the app clears everything.
- **Font fallback:** If `fonts/` directory is missing or empty, the app falls back to system default fonts silently.

---

## Glossary

| Term | Meaning |
|------|---------|
| Stripe | A full-width task slot widget inside the pill window |
| Keyframe | A (minute, bg_color, button_color) tuple in the color schedule |
| Dark-mode flip | At 16:00 the background/button color roles invert |
| Hard stop | 22:00-04:00 sleep mode with black background and hidden stripes |
| Time offset | Debug feature: `timedelta` added to `datetime.now()` for QA testing |
| Check-mark | The `✓` button that appears on hover to complete an active task |
