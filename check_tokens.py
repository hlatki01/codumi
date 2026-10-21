"""Token labels stay next to status; exact totals remain in the clicked details."""
from pathlib import Path
import tempfile

from app import App
from i18n import LANGUAGE_NAMES


with tempfile.TemporaryDirectory() as folder:
    app=App(demo=True,preferences_path=Path(folder)/"prefs.json")
    app.root.after_cancel(app.hover_id)
    try:
        app.reduced=True
        claude,codex=app.sessions[:2]
        claude.apply({"type":"assistant","message":{"id":"fixture","content":[],
                      "usage":{"input_tokens":100_000,"output_tokens":250_000,
                               "cache_creation_input_tokens":150_000,"cache_read_input_tokens":2_000_000}}},claude.updated)
        codex.tokens=128_000
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.close_menu()
            app.tray.details=False
            app.position_tray()
            app.show_tray()
            app.refresh_now()
            app.root.update()
            text=app.tray.rows[claude.key][0].cget("text")
            label=app.t("tokens_short",count="2.5M")
            assert text.endswith(app.t.state("working")+"  ·  "+label),(language,text)
            assert app.tray.rows[codex.key][0].cget("text").endswith(app.t("tokens_short",count="128K"))
            app.select_session(claude.key)
            app.root.update()
            assert app.tray.details and app.tray.detail_frame.winfo_ismapped()
            assert app.t("tokens",count=2_500_000) in app.tray.meta.cget("text")
            assert app.terminal_pending is None
            app.select_session(claude.key)
            app.root.update()
            assert not app.tray.details and not app.tray.detail_frame.winfo_ismapped()
            claude.tokens_partial=True
            app.tray.refresh()
            assert "≥2.5M" in app.tray.rows[claude.key][0].cget("text")
            claude.tokens_partial=False
            for state in ("working","thinking","waiting","compacting","error"):
                claude.state=state
                app.tray.refresh()
                app.root.update()
                button=app.tray.rows[claude.key][0]
                assert button.winfo_height()>=button.winfo_reqheight(),(language,state)
                assert app.t("tokens_short",count="2.5M") in button.cget("text")
            claude.state="working"
    finally:
        app.close(immediate=True)
print("Token UI OK: Claude and Codex totals after status, exact details, partial marker, six languages, wrapping, click-to-expand and click-to-collapse")
