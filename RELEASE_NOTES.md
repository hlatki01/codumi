# codumi v0.3.3 - Ready for the update test

This release integrates the companion workflow and periodic update reminders into main. It has the same behavior as v0.3.2, with a new visible version so the full update flow can be tested.

## Test the update from v0.3.2

After the automatic check (30 seconds after startup, then every six hours), open the pet tray and click the update button. Download and verify the package, then choose Install and restart. The header should show v0.3.3 and your preferences should remain intact. You can also check immediately from the Updates page. The previous application folder is kept for rollback.

Downloads and installation still require your click.

## New

- Attention queue for sessions whose last recorded state is waiting or error.
- Optional local completion history: up to 100 entries over 30 days, without prompts or transcript paths.
- Open session, focus window, and mute project actions inside speech bubbles.
- Per-project pets, voice, notice overrides, muting, and edge behavior.
- Edge tucking with hover reveal and preserved saved position.
- Presentation mode, including Ctrl+Alt+P, that masks private fields and suppresses notices inside codumi.
- Direct, friendly, and playful local speech templates in six languages.
- Manual update checks, release notes, verified downloads, and preference-preserving restart into a new portable folder.

Open Settings → Companion & activity → Attention, history & projects to explore the four new pages. History is off by default. Project settings follow the selected provider/project; defaults remain available for inheritance.

## Updating and rollback

Checks run automatically 30 seconds after startup and every six hours, and can also be requested manually. Downloads and installation happen only when requested. The updater uses the public hlatki01/codumi GitHub release endpoints over HTTPS, verifies SHA-256, validates ZIP paths and size limits, and checks staged contents again before restarting. No session data or credentials are sent.

The updater waits for the current process to exit, copies its latest preferences, and opens the new build from a versioned folder in the local updates area. The previous build is preserved. Existing shortcuts remain unchanged; Open app folder locates the new launcher. Keep the updates area with the application. Repeated updates reuse the same area.

The executable is unsigned. Integrity checks are not a code signature. Clearing history affects the current preferences file; backup and rollback copies keep their own settings. Presentation mode does not redact other applications.

## Validation

72 unit tests and native checks passed, including six-language workflow pages, privacy masking, voice and bubble actions, edge clipping/reveal, persistence, and a mocked update lifecycle. A live v0.2.2 download, checksum verification, extraction, staged-file verification, and transfer of fictional preferences also passed in a temporary installation.

An actual upgrade of the running stable app was not performed for this PR. Foreground activation, physical hotkey behavior, mixed-DPI monitors, screen readers, and prolonged resource use still need broader user-desktop validation. Cursor state and token availability depend on its recorded events.
