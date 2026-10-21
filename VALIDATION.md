# Validation

Validation environment: Windows x64, Python 3.12 with Tcl/Tk and the bundled portable runtime.

## Automated checks

34 unit tests cover:

- Incremental Claude/Codex reading, malformed records, truncation, replacement, incomplete UTF-8, and bounded discovery.
- Real transcript events for thinking and completion.
- Spring stability, reduced motion, hit geometry, monitor edges, and negative coordinates.
- Ten distinct pet silhouettes and valid palettes.
- Six translation catalogs, matching placeholders, regional variants, display-language selection, and English fallback.
- Original-terminal session IDs, Claude registry matching, Codex lock paths, Restart Manager buffer handling and cleanup, stale PIDs, parent-process discovery, and ambiguous windows.
- Exit trajectories, landing before shrink, and bounded motion near the screen edge.

No linter is configured. Python syntax is checked with py_compile.

## Native UI checks

The native checks passed on an isolated desktop using temporary preferences and fictional sessions:

| Script | Coverage |
| --- | --- |
| check_ui.py | 64 px avatar, shaped regions, transparent corners, hover delay, spring transitions, foreground preservation, session selection and filtering, scrolling, settings, drag, preferences, closing, and completion deduplication |
| check_locales.py | Actual labels, menus, pets, details, and subtitle width in all six languages |
| check_pet_motion.py | One jump per hover, drag cancellation, eye tracking on both axes for all pets, retained items, and reduced motion |
| check_settings_reaction.py | Immediate language switching, persistence, four-click reactions, returning to the current session state, and terminal action routing |
| check_terminal.py | A real test console, exact registry/process identity, console handle discovery, restoration, window-list inclusion, and stale-PID rejection |
| check_terminal_picker.py | Manual window association, synchronous retries, six-language layouts, empty lists, and rejection of late automatic results |
| check_exit.py | All pets jump outside the circle, land, shrink, and close; click-through behavior, preserved position, screen-edge handling, reduced motion, and failure fallback |

WindowFromPoint checks confirm that transparent corners reach the underlying test window and the exit overlay does not intercept input.

The portable launcher passed its demo smoke test. Release archives are checked against the source and exclude preferences, logs, caches, and personal session data.

## Important limits

- This isolated desktop has no usable foreground window. Actual activation on the user's desktop could not be confirmed; the app reports refusal instead of claiming success.
- Restart Manager returns Windows error 29 in this sandbox. Codex file-owner lookup was tested with mocks and needs testing on regular user desktops.
- Windows Terminal parent-process fallback was tested for ownership, creation times, and ambiguity; broader testing with real terminal hosts is welcome.
- Choosing the exact tab or pane within a terminal window is not automated.
- Physical mixed-DPI monitor configurations, clean Windows installations, ARM64, screen readers, and prolonged resource use are not fully validated.
- The executable is unsigned.

## Timing and resource behavior

Tray transitions use a 16 ms timer while moving. Working pets update approximately every 33 ms, resting pets every 120 ms, and reduced-motion rendering every 250 ms. The exit animation lasts about 1.25 seconds and uses retained canvas objects.

The transcript reader runs separately from the UI. New sessions are discovered roughly every ten seconds; known sessions are polled every second. Resource use needs longer measurements on regular desktops.

## Reproduce

See the source, test, and build commands in README.md. Run native scripts on Windows with Tcl/Tk. Use demo sessions for screenshots and remove private paths or conversation content before submitting reports.
