# Validation

Validation environment: Windows x64, Python 3.12 with Tcl/Tk and the bundled portable runtime.

## Automated checks

68 unit tests cover:

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

## Session interaction and usage

- A session click opens its details; a second click on the same session collapses them. Switching sessions keeps details open and updates their content.
- Session selection cancels pending terminal activation; only the explicit Focus terminal action opens that workflow.
- Claude totals include input, output, cache creation, and cache reads, deduplicated by message ID with per-field streaming maxima. Codex totals remain cumulative.
- Six usage regression tests cover repeated records, malformed counters, UUID fallback, history/tail overlap, truncation, snapshot isolation, and compact labels.
- check_tokens.py verifies status-then-token order, exact detail totals, partial-count markers, six-language wrapping, and session click toggling.
- Historical token backfill reads at most one additional bounded chunk per Claude session per poll; it never replaces the live prompt, status, or event stream.

## v0.2 companion checks

- Nine new unit tests cover Cursor role records and stream events, read-only discovery and workspace matching, usage baselines and backfill, notifications without replay, saved counters, project identity, original window profiles and stale identity rejection, hotkey registration and its dedicated message queue, and species gesture bounds.
- `check_companion.py` covers pinning and ordering, saved selection, six-language companion settings, scrolling on a 640×480 work area, focus suppression, non-repeating notices, completion stars, other-session indicators, usage, and the Cursor action label.
- Cursor's role/message record shape was inspected locally without printing message contents. Its live editor activation and absent completion/token fields cannot be proven by transcript parsing.
- Global hotkey delivery is exercised with a message posted to its own Win32 thread; actual key presses on the normal user desktop need user testing.
- Daily counters intentionally exclude initial discovery, history backfill, and usage while the app is closed. Old preferences retain pet, position, language, sound, and topmost settings.

## v0.2.1 speech bubbles

`check_speech.py` verifies all three first-person messages in all six languages, text fit, above-left placement with a slanted tail, fallback at the top edge, negative monitor coordinates, edge clamping, transparent hit regions, the tail region, session activation, and dismissal. The full 49-test unit suite also passes.

## v0.3 workflow and update checks

- Nineteen additional unit tests cover attention ordering, override validation and inheritance, opt-in history privacy, deduplication and retention, presentation shortcut registration, edge coordinates, release parsing, response bounds, checksums, archive traversal/symlinks/case aliases/personal files, staging tampering, preference transfer, repeated-update layout, failed parent waits, and HTTPS redirect restrictions.
- `check_workflow.py` exercises all four workspace pages in six languages; project pets and global inheritance; stable project controls during unrelated updates; opening an otherwise-filtered session; history and presentation masking; all three voices and speech actions; edge clipping/reveal with saved position; small-screen scrolling; persistence; and a mocked check/download/verification/restart lifecycle.
- A live public GitHub check and download of v0.2.2 passed in a temporary test installation. Its real checksum, archive, staged contents, and transfer of fictional preferences were verified. The installed stable app was not modified.
- The actual restart helper's wait/failure and launch routing are covered with mocks; a real upgrade that closes a user's running instance was not performed for this PR.
- Presentation mode masks data inside codumi only. Screens in terminals, editors, or other applications are not changed. Existing shortcuts continue pointing to their original build after an assisted update.

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
