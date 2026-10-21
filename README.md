# codumi ●

**Your little coding companion.**

A small animated desktop pet that keeps you company while Claude Code and Codex work. Built for Windows, with a floating avatar, a hover tray, and local session monitoring.

**Open source under the MIT license. Everyone is welcome to contribute.**

[Download](https://github.com/hlatki01/codumi/releases/latest) · [Report a bug](https://github.com/hlatki01/codumi/issues) · [Contribute](CONTRIBUTING.md)

## Get started

1. Download the Windows x64 ZIP from [Releases](https://github.com/hlatki01/codumi/releases).
2. Extract the **entire folder** to a writable location.
3. Open **codumi.exe**. Python does not need to be installed.
4. Find the circular pet on the right side of your screen. Hover over it to reveal your sessions.

Keep the executable, source files, and runtime folder together. The portable build includes Python and Tcl/Tk. It needs no account, API key, or internet connection to monitor local sessions.

The initial release targets Windows x64. The executable is currently unsigned.

## Meet your companion

- **Ten pets:** codumi, cat, dog, fox, rabbit, panda, frog, owl, robot, and dragon.
- **Live states:** working, thinking, waiting, ready, resting, error, and context compaction, with brief completion celebrations.
- **A little personality:** a hover jump, eyes that follow your cursor while working, and a fall-and-cry reaction after four clicks within 1.2 seconds.
- **An animated goodbye:** the pet jumps out of its bubble, lands inside, and shrinks away when you quit.
- **A compact hover tray:** recent sessions, provider, status, prompt, elapsed time, available token totals, and recent events.
- **Windows integration:** drag to reposition, saved preferences, optional always-on-top behavior, screen-edge handling, and transparent corners that do not block other apps.
- **Reduced motion:** follows the Windows setting and disables movement effects.

The pet represents the selected session. Its animations never change the agent's actual state.

## Using codumi

| Action | How |
| --- | --- |
| Show sessions | Hover over the pet |
| Hide the tray | Leave the pet and tray for 250 ms |
| Move the pet | Drag the avatar |
| Open settings | Click **···** or right-click the pet |
| Change pets | Open settings and choose **Pet** |
| Change language | Open settings and choose **Language** |
| Inspect a session | Click it to show details; click it again to collapse |
| Focus its terminal | Select the session, then click **Focus terminal** |
| Choose a terminal manually | **Activity → Choose terminal window… → Use this window** |
| Quit | Click **×**, choose **Quit codumi**, or press **Ctrl+Q** in the panel |

For keyboard navigation, choose **Keyboard navigation** in settings. Use Tab to move between controls, Space to activate them, and Escape to dismiss the tray.

If the app is unresponsive, `Fechar.cmd` closes only the Python process belonging to this distribution's runtime. Other Python processes are left alone.

## Languages

English, Portuguese, Spanish, French, German, and Italian are included.

By default, codumi uses your Windows **display language**, with English as the fallback. Settings let you select a language manually or return to **Automatic (Windows)**. Changes apply immediately and are saved. The subtitle is translated too.

Project names, prompts, provider names, and tool identifiers retain their original text. To pick up a changed Windows display language in automatic mode, restart codumi.

## Focusing the original terminal

codumi tries to find the terminal where the selected session is already running. It does not open another shell or send commands to your session.

It uses Claude's session registry or the process holding Codex's writer file, checks process creation times, and looks for the visible console or its terminal-host ancestor. If the association is ambiguous, choose the window yourself from **Activity → Choose terminal window…**. That association lasts while codumi is open.

Closed sessions and editor-integrated sessions may not expose a usable terminal window. Windows can also refuse foreground activation. The app reports these cases instead of guessing a window.

**Selecting a specific tab or pane inside a terminal window is not automated.** Foreground activation still needs broader validation on regular user desktops.

## Local data and privacy

codumi reads local JSONL session files from:

- `%USERPROFILE%\.claude\projects`, or `CLAUDE_CONFIG_DIR\projects`.
- `%USERPROFILE%\.codex\sessions`, or `CODEX_HOME\sessions`.

The reader runs in a background thread. It discovers up to 48 recently updated sessions, reads bounded transcript tails, and follows complete appended lines.

It does not install agent hooks, modify conversations, read authentication files, or send session data over the network. Prompts are displayed locally. Preferences are saved beside the app in `preferences.json`; diagnostic errors go to `codumi.log`. Neither belongs in Git or release archives.

States depend on the events the agent records. Missing permission or reasoning events cannot be inferred reliably. Five minutes without new records makes a session appear resting; that does not prove its process has exited. Token usage appears immediately after the session state, for example **Working · 128K tokens**. Codex uses the transcript's cumulative total. Claude sums input, output, cache-creation, and cache-read usage once per message, merging repeated streaming records.

Large Claude histories are counted in bounded background chunks without replacing live session state. A **≥** prefix means older records are still being counted. Click the session for the unabridged number; click it again to collapse its details. If no usage was recorded, the app does not invent a token count. Totals reflect available valid records; oversized or malformed records are skipped by the reader.

Claude's input/cache fields follow the [documented usage breakdown](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). These are processed-token totals across requests, not the current context-window size.

## Run from source

Requirements: **Windows x64, Python 3.10+ with Tcl/Tk**. There are no PyPI dependencies.

```powershell
git clone https://github.com/hlatki01/codumi.git
cd codumi
python app.py
```

For fictional sessions, without reading your real agent history:

```powershell
python app.py --demo
```

## Test

```powershell
python -m unittest discover -v
python check_ui.py
python check_locales.py
python check_pet_motion.py
python check_settings_reaction.py
python check_terminal.py
python check_terminal_picker.py
python check_exit.py
python check_tokens.py
python app.py --demo --smoke-test
```

Native UI checks create temporary windows and preferences. Run them on Windows with Tcl/Tk. Foreground and Restart Manager checks may be restricted in sandboxed desktops; see [VALIDATION.md](VALIDATION.md) for the evidence and limits.

No linter is configured. Syntax can be checked with:

```powershell
python -m py_compile app.py desktop.py pet.py sessions.py i18n.py terminal.py build.py
```

## Build a portable release

On Windows x64, use Python with Tcl/Tk and the .NET Framework 4.x C# compiler included with Windows:

```powershell
python build.py
```

This creates `dist/codumi-Windows/codumi.exe` and `dist/codumi-Windows-x64.zip`. Existing output directories are never overwritten. To build elsewhere:

```powershell
python build.py --output dist/v0.1.0/codumi-Windows
```

The ZIP contains the app's source, licenses, documentation, and a local Python/Tcl/Tk runtime. It excludes preferences, logs, and Python caches.

## Contribute

**Everyone is welcome:** first-time contributors, developers, designers, translators, and Windows testers.

Bug reports, small fixes, accessibility improvements, translations, animation refinements, and testing on different monitors and terminal hosts are all useful. You do not need a large feature to contribute.

Read [CONTRIBUTING.md](CONTRIBUTING.md), open an [issue](https://github.com/hlatki01/codumi/issues), or send a pull request. Please keep discussion respectful and include enough detail to reproduce a bug. Never attach private conversations or credentials.

## Architecture

| File | Responsibility |
| --- | --- |
| `app.py` | Floating windows, hover tray, settings, session selection, and preferences |
| `pet.py` | Ten native sprites and retained-canvas animations |
| `desktop.py` | Win32 window behavior, monitor geometry, regions, and spring motion |
| `sessions.py` | Read-only Claude/Codex transcript adapters |
| `terminal.py` | Original-terminal discovery, identity checks, and focus requests |
| `i18n.py`, `locales.json` | Windows display-language detection and UI translations |
| `Launcher.cs`, `build.py` | Small Windows launcher and portable packaging |

## License and credits

codumi's application code and sprites are licensed under [MIT](LICENSE).

The concept was inspired by [Notchi by sk-ruban](https://github.com/sk-ruban/notchi). This is an independent Windows implementation; no upstream code or sprites are included. It is not an official Notchi distribution.

The bundled runtime keeps its own licenses. See [THIRD_PARTY.md](THIRD_PARTY.md) and `runtime/LICENSE.txt` in the portable distribution.

