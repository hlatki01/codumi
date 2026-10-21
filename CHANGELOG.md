# Changelog

## v0.3.0 — Attention when it matters (unreleased)

- Live attention queue with explicit session and window actions.
- Optional local completion history, limited to 100 entries and 30 days, excluding prompts and transcript paths.
- Session, window, and project-mute actions inside speech bubbles.
- Per-project pets, voice, individual notice overrides, muting, and edge behavior.
- Edge tucking with shaped hit regions, hover reveal, and preserved logical position.
- Persistent presentation mode and a Ctrl+Alt+P shortcut; private fields and notices are hidden inside codumi.
- Direct, friendly, and playful local message templates in all six languages.
- Manual HTTPS release checks, notes, SHA-256 validation, safe ZIP staging, and preference-preserving restart into a separate build.
- A shared updates area across repeated upgrades and retention of the previous build for rollback.
- Scrollable attention/history/project/update pages, with controls stable while unrelated sessions change.

## v0.2.2 ? A better place to talk

- Speech bubbles prefer a position above and to the left of the pet.
- The tail slopes gently up-left from the pet toward the bubble.
- Near the screen's top edge, bubbles fall back below without clipping.

## v0.2.1 — A little voice

- Notifications are rounded speech bubbles with a tail pointing toward the pet.
- Completion, error, and attention messages speak in the first person in all six languages.
- Bubbles appear above the pet when needed, preserve transparent click-through corners, and keep session and close actions.
- Dragging the pet dismisses its bubble so the tail cannot become detached.

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
