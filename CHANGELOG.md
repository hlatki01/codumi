# Changelog

## v0.1.0 — Initial release

- Floating 64 px pet with a connected hover tray.
- Ten selectable pets, persistent position, and optional always-on-top behavior.
- Local Claude Code and Codex session monitoring.
- State animations, hover jumps, cursor-tracking eyes, repeated-click reactions, and an animated goodbye.
- English, Portuguese, Spanish, French, German, and Italian, with automatic Windows display-language detection and manual selection.
- Session activity, filtering, available token totals, and original-terminal focus attempts.
- Terminal-host ancestor discovery and manual window association for ambiguous cases.
- Keyboard navigation, transparent hit regions, and Windows reduced-motion support.
- Portable Windows x64 build with bundled Python/Tcl/Tk.
- MIT-licensed application code and an open invitation to contribute.

### Known limitations

- The executable is unsigned; Windows x64 is the initial target.
- Terminal tab/pane selection is not automated. Windows may refuse foreground activation.
- Codex process discovery depends on Restart Manager availability.
- Clean-machine installation, ARM64, screen readers, prolonged resource use, and physical mixed-DPI monitor setups need broader testing.
