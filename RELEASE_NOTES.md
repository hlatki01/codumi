# codumi v0.1.0

Your little coding companion — now on Windows.

This first public release includes ten animated pets, a connected hover tray, local Claude Code and Codex session monitoring, six languages, saved preferences, and reduced-motion support.

Hover to see sessions, drag to reposition your pet, and open settings to choose its appearance and language. While working, it follows your cursor with its eyes. Four quick clicks trigger a brief fall-and-cry reaction; quitting plays an animated goodbye.

## Download

Download **codumi-v0.1.0-windows-x64.zip**, extract the entire folder, and open **codumi.exe**. No Python installation, account, or API key is required.

The archive contains source code and runtime licenses. **SHA256SUMS.txt** contains its SHA-256 checksum.

## Open source

The application code and sprites are MIT-licensed. Everyone is welcome to contribute fixes, translations, design feedback, accessibility improvements, and Windows testing. See CONTRIBUTING.md.

Inspired by sk-ruban/notchi; this is an independent Windows implementation.

## Known limitations

The executable is unsigned. Terminal focus is best-effort, and tab/pane selection is not automated. If automatic discovery fails, use **Activity → Choose terminal window…** to associate the original window.

Foreground activation and Codex's Restart Manager lookup still need broader validation on regular user desktops. Physical mixed-DPI monitor setups, screen readers, clean Windows installations, ARM64, and prolonged resource use have not been fully validated.

## Validation

34 unit tests passed. Native checks cover hover, dragging, transparent hit regions, session controls, six-language layouts, all ten pets, click reactions, window selection, and animated exit. The portable launcher passed its smoke test.
