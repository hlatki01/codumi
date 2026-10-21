# Changelog

## v0.2.0 — A companion with a memory

- Read-only Cursor JSONL transcript support and workspace metadata matching.
- Persistent project favorites, selected session, and validated window associations.
- Configurable completion, error, and attention notices without focus stealing.
- A temporary clickable completion star and a counter for other busy sessions.
- Session and observed daily token summaries, including recorded input/output/cache fields.
- A 25-minute focus mode that silences notices and sound and stills the pet.
- A configurable native global shortcut with conflict reporting and cleanup.
- Distinct species gestures, localized settings, and a scrollable companion panel.
- Portable package includes the new module and README images.

### Limits

Cursor records can omit completion, timestamps, and token usage. Legacy text-only and remote cloud transcripts are not monitored. Daily usage is observed while codumi runs, not a reconstruction of all usage for the day. Window restoration requires the original live window and process identity, and Windows may still refuse foreground activation.

## v0.1.0 — Initial release

- Floating 64 px pet with a connected hover tray.
- Ten selectable pets, persistent position, and optional always-on-top behavior.
- Local Claude Code and Codex session monitoring.
- State animations, hover jumps, cursor-tracking eyes, repeated-click reactions, and an animated goodbye.
- English, Portuguese, Spanish, French, German, and Italian, with automatic Windows display-language detection and manual selection.
- Session activity, filtering, click-to-expand details, and original-terminal focus attempts.
- Claude and Codex token totals beside session status, with deduplicated Claude cache usage and bounded historical backfill.
- A translated explanation that the pet follows the selected session.
- Terminal-host ancestor discovery and manual window association for ambiguous cases.
- Keyboard navigation, transparent hit regions, and Windows reduced-motion support.
- Portable Windows x64 build with bundled Python/Tcl/Tk.
- MIT-licensed application code and an open invitation to contribute.

### Known limitations

- The executable is unsigned; Windows x64 is the initial target.
- Terminal tab/pane selection is not automated. Windows may refuse foreground activation.
- Codex process discovery depends on Restart Manager availability.
- Clean-machine installation, ARM64, screen readers, prolonged resource use, and physical mixed-DPI monitor setups need broader testing.
