"""Window picker and explicit terminal binding, including asynchronous races."""
from pathlib import Path
import tempfile
from unittest.mock import patch
import tkinter.font as tkfont

from app import App
from i18n import LANGUAGE_NAMES


with tempfile.TemporaryDirectory() as folder:
    app=App(demo=True,preferences_path=Path(folder)/"prefs.json")
    app.root.after_cancel(app.hover_id)
    try:
        app.reduced=True
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.close_menu()
            app.tray.details=True
            app.terminal_status="terminal_missing"
            app.position_tray()
            app.show_tray()
            app.tray.refresh()
            app.root.update()
            assert app.tray.detail_frame.winfo_reqheight()<=app.tray.detail_frame.winfo_height(),language
            button=app.tray.choose_terminal_button
            assert tkfont.Font(font=button.cget("font")).measure(button.cget("text"))+18<=app.tray.detail_frame.winfo_width(),language
            choices=[("PowerShell — project A",(111,222,333)),("PowerShell — project B",(444,555,666))]
            app.terminal_pending=app.current_session().key
            with patch("terminal.available_terminals",return_value=choices):
                button.invoke()
            assert app.terminal_pending is None
            app.terminal_results.put((app.current_session().key,choices[0][1]))
            app.check_terminal_result()
            assert app.terminal_picker_open
            app.root.update()
            assert app.terminal_picker_open and app.tray.terminal_frame.winfo_ismapped()
            assert app.tray.terminal_list.size()==2
            app.tray.terminal_list.selection_clear(0,"end")
            app.tray.terminal_list.selection_set(1)
            session=app.current_session()
            app.terminal_pending=session.key
            with patch("terminal.valid_target",return_value=True),patch("terminal.focus_terminal",return_value=True) as focus,\
                 patch("terminal.find_terminal") as lookup:
                app.tray.bind_terminal_button.invoke()
                assert app.terminal_bindings[session.key]==choices[1][1]
                assert not app.tray_visible and app.terminal_pending is None
                focus.assert_called_once_with(choices[1][1])
                lookup.assert_not_called()
                app.terminal_results.put((session.key,choices[0][1]))
                app.check_terminal_result()
                assert app.terminal_bindings[session.key]==choices[1][1],"late lookup replaced user's explicit choice"
                app.focus_selected_terminal()
                assert focus.call_count==2
                lookup.assert_not_called()
            with patch("terminal.available_terminals",return_value=[]):
                app.open_terminal_picker()
            app.root.update()
            assert app.tray.bind_terminal_button.cget("state")=="disabled"
            app.close_menu()
        # Windows refusing activation must keep the selected binding and display a retry.
        selected=app.current_session().key
        with patch("terminal.valid_target",return_value=True),patch("terminal.focus_terminal",return_value=False),\
             patch("terminal.find_terminal") as lookup:
            app.focus_selected_terminal()
            assert app.terminal_status=="terminal_denied"
            assert app.terminal_bindings[selected]==choices[1][1]
            lookup.assert_not_called()
    finally:
        app.close(immediate=True)
print("Terminal picker OK: six locales fit, manual window binding, synchronous retry, no replacement shells, stale background result ignored")
