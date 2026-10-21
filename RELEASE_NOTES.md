# codumi v0.2.1 — A little voice

Your companion now speaks through a chat bubble.

- Rounded dark bubbles with a tail pointing toward the pet.
- First-person completion, error, and attention messages in all six languages.
- The bubble moves above the pet when space below is limited.
- Click its message to open the session, or × to dismiss it. Transparent corners pass clicks through to the application underneath.
- Moving the pet dismisses its current bubble.

All v0.2 features remain available. Existing preferences stay compatible. To update into a fresh folder, close codumi and copy your preferences.json into the new extracted folder before launching codumi.exe.

49 unit tests passed. Native speech checks cover six languages, three message types, text fit, both tail directions, screen edges, shaped hit regions, session actions, and dismissal.

The executable remains unsigned. Cursor's available states and usage depend on its local transcripts, and original-window activation remains subject to Windows foreground rules.
