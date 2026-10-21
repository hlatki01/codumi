# codumi v0.2.0 — A companion with a memory

Your little coding companion now remembers its favorite projects and brings Cursor into the session tray.

## New

- Read-only discovery of local Cursor JSONL transcripts, plus workspace metadata matching when available.
- Pin projects and keep them at the top; remember the selected session after restarting codumi.
- Configurable, clickable notices for task completion, errors, and requests for attention.
- A temporary completion star that opens the finished session, and a small indicator for other busy sessions.
- Session token breakdowns and daily increments observed while codumi runs.
- A 25-minute concentration mode that silences notices and sound and stills the pet.
- A native global shortcut: Ctrl+Alt+N, with alternative combinations, an Off option, and conflict reporting.
- Persistent project window associations validated against the original live window and process identity. Cursor asks you to choose its original window on first use.
- Distinct species gestures and a scrollable companion settings panel in all six languages.

Open Settings → Companion & activity for notice controls, concentration, shortcuts, and usage summaries. Pin a project from session details or by right-clicking its row.

## Download and update

Extract the entire Windows x64 ZIP to a writable folder and open codumi.exe. Python is bundled; no account or API key is required for monitoring.

To preserve settings when moving to a fresh folder, close the previous codumi instance and copy its preferences.json into the new extracted folder before opening the app. Keep the full runtime folder with the executable. Existing pet, position, language, sound, and topmost settings remain compatible.

Application code and sprites are MIT-licensed. Everyone is welcome to contribute fixes, translations, pets, accessibility improvements, and Windows testing.

## Limits

- Cursor formats vary. Completion, permission, timestamp, and usage fields may be absent. Missing tokens or completion events are never invented; legacy text-only and remote cloud transcripts are not monitored.
- Daily totals include new usage observed with codumi open, excluding historical discovery and backfill. They do not reconstruct usage while codumi was closed.
- Saved window associations are valid only while the original window and process identity remain valid. Windows may refuse foreground activation; exact terminal tab/pane selection is not automated.
- The executable is unsigned. Real key presses, physical mixed-DPI monitors, screen readers, clean installations, and prolonged resource use need broader user-desktop testing.

## Validation

49 unit tests plus native checks cover the session readers, settings in six languages, favorites, notices, concentration, usage, hotkey message delivery and cleanup, window identity validation, hover, dragging, token labels, all ten pets, and animated exit. The companion panel is also exercised on a 640×480 work area. See VALIDATION.md for environmental limitations.
