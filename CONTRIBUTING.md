# Contributing to codumi

Everyone is welcome here. You can contribute code, translations, design feedback, documentation, bug reports, or Windows testing.

## Before you start

For a bug fix or documentation improvement, feel free to send a small pull request directly. For a larger feature, open an issue first so we can agree on the problem and scope.

Please be kind, respect other contributors, and focus feedback on the work.

## Development

Use Windows x64 and Python 3.10+ with Tcl/Tk. No third-party Python packages are required.

    python app.py --demo
    python -m unittest discover -v

The demo uses fictional sessions and does not read your agent history.

Keep session monitoring separate from rendering. Prefer the standard library and native Windows APIs over new dependencies. Preserve reduced-motion behavior, click-through transparency, saved preferences, and existing session-reader limits.

## Test your changes

Run the unit tests, then the native checks relevant to your change:

- Session parsing: test_sessions.py, test_usage.py, test_companion.py.
- Companion settings, favorites, notices, and usage: test_companion.py, check_companion.py, check_speech.py.
- Overlay geometry and spring motion: test_overlay.py.
- Pets and animations: test_pet_catalog.py, test_exit.py, check_pet_motion.py, check_exit.py.
- Languages and settings: test_i18n.py, check_locales.py, check_settings_reaction.py.
- Terminal discovery and selection: test_terminal.py, check_terminal.py, check_terminal_picker.py.
- General desktop interactions: check_ui.py.

Run tests with python -m unittest discover -v; run each native check script separately. Explain any environment restriction instead of marking an untested behavior as verified.

There is no configured linter. Use python -m py_compile on changed Python files.

## Translations

UI strings live in locales.json. Keep the same keys and formatting placeholders in every language. Add the native language name to LANGUAGE_NAMES in i18n.py when adding a language, and update the launcher messages in Launcher.cs.

Do not translate project names, user prompts, provider names, or tool identifiers. Check that longer strings fit inside the tray.

## Pull requests

Describe the problem, the resulting behavior, and how you tested it. Include screenshots or recordings for visual changes using demo sessions.

Keep unrelated changes in separate pull requests. Do not commit runtime builds, personal preferences, logs, credentials, or real conversations.

## Bug reports

Include the codumi version, Windows version, terminal host, steps to reproduce, and expected versus actual behavior. For display issues, include monitor scaling and reduced-motion settings.

Remove private paths and conversations before sharing logs or screenshots.

## License

By contributing, you agree that your application-code contribution can be distributed under the project's MIT license. Preserve existing notices and document any third-party assets or dependencies.
