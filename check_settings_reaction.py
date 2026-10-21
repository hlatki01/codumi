"""Native checks for live language switching, persistence, and click reactions."""
import json
from pathlib import Path
import tempfile
import time
import tkinter.font as tkfont
from unittest.mock import patch

from app import App
from i18n import LANGUAGE_NAMES
from pet import PETS


with tempfile.TemporaryDirectory() as folder:
    preferences=Path(folder)/"preferences.json"
    app=App(demo=True,preferences_path=preferences)
    app.root.after_cancel(app.hover_id)
    try:
        app.reduced=True
        app.open_menu()
        app.root.update()
        app.tray.settings_buttons["language"].invoke()
        app.root.update()
        assert app.language_picker_open and app.tray.language_frame.winfo_ismapped()
        for code in LANGUAGE_NAMES:
            selected,position=app.selected,(app.pet_x,app.pet_y)
            app.tray.language_buttons[code].invoke()
            app.root.update()
            assert app.t.language==code and app.language==code
            assert app.tray.language_frame.winfo_ismapped()
            assert app.tray.language_frame.winfo_reqheight()<=app.tray.language_frame.winfo_height()
            for button in app.tray.language_buttons.values():
                assert tkfont.Font(font=button.cget("font")).measure(button.cget("text"))+20<=button.winfo_width()
            app.tray.language_buttons["back"].invoke()
            app.root.update()
            assert app.tray.settings_frame.winfo_reqheight()<=app.tray.settings_frame.winfo_height()
            for button in app.tray.settings_buttons.values():
                assert tkfont.Font(font=button.cget("font")).measure(button.cget("text"))+20<=button.winfo_width(),code
            app.tray.settings_buttons["language"].invoke()
            assert app.selected==selected and (app.pet_x,app.pet_y)==position
            assert json.loads(preferences.read_text())["language"]==code
            assert app.tray.language_buttons[code].cget("fg")=="#4ef0b5" or app.tray.language_buttons[code].cget("fg")=="#4EF0B5"
        with patch("i18n.windows_language",return_value="pt-BR"):
            app.tray.language_buttons["auto"].invoke()
        assert app.language=="auto" and app.t.language=="pt"
        app.tray.language_buttons["back"].invoke()
        app.root.update()
        assert app.menu_open and not app.language_picker_open
        assert app.tray.settings_frame.winfo_ismapped()
        assert app.tray.settings_frame.winfo_reqheight()<=app.tray.settings_frame.winfo_height()
        app.tray.settings_buttons["language"].invoke()
        app.tray.language_buttons["de"].invoke()
        assert not app.select_language(["bad"])
        assert not app.select_language("ja")
        assert app.language=="de"

        pet=app.pet
        app.close_menu()
        for pet_id in PETS:
            for state in ("working","sleeping"):
                pet.pet_id=pet_id
                pet.reaction_started=None
                pet.clicks=[]
                pet.completed_until=0
                pet.update(state,100)
                for now in (100,100.2,100.4):
                    pet.click(now)
                assert not pet.reacting(100.4)
                pet.click(100.6)
                assert pet.reacting(100.6) and pet.state==state
                start=pet.reaction_started
                pet.draw(101.1)
                assert abs(pet.angle-1.57079632679)<1e-6 and pet.bob==8
                pet.click(101.2)
                assert pet.reaction_started==start
                pet.draw(101.6)
                assert 0<pet.angle<1.5708
                pet.draw(102.2)
                assert pet.angle==0
                assert all(app.canvas.itemcget(tear,"state")=="normal" for tear in pet.tears)
                pet.draw(102.3,reduced=True)
                static={item:app.canvas.coords(item) for item in app.canvas.find_all()}
                pet.draw(102.4,reduced=True)
                assert static=={item:app.canvas.coords(item) for item in app.canvas.find_all()}
                pet.draw(104,reduced=True)
                assert not pet.reacting(104) and pet.state==state and pet.angle==0
                assert all(app.canvas.itemcget(tear,"state")=="hidden" for tear in pet.tears)
                assert pet.sprite_key[0]==state
                pet.reaction_started=None
                pet.clicks=[]
                for now in (110,112,114,116):
                    pet.click(now)
                assert not pet.reacting(116)

        pet.reaction_started=None
        pet.clicks=[]
        pet.update("working",200)
        for now in (200,200.2,200.4,200.6):
            pet.click(now)
        pet.update("sleeping",202)
        pet.draw(204,reduced=True)
        assert pet.sprite_key[0]=="sleeping"

        # The explicit terminal action stays asynchronous and focuses only the selected session.
        first,second=app.sessions[0].key,app.sessions[1].key
        with patch("terminal.find_terminal",return_value=(100,200,300)),\
             patch("terminal.focus_terminal",return_value=True) as focus:
            app.select_session(first)
            app.focus_selected_terminal()
            end=time.monotonic()+2
            while app.terminal_results.empty() and time.monotonic()<end:
                time.sleep(.01)
            app.check_terminal_result()
            focus.assert_called_once_with((100,200,300))
            assert not app.tray_visible and not app.terminal_status
        with patch("terminal.find_terminal",return_value=None),\
             patch("terminal.focus_terminal") as focus:
            app.select_session(second)
            app.focus_selected_terminal()
            end=time.monotonic()+2
            while app.terminal_results.empty() and time.monotonic()<end:
                time.sleep(.01)
            app.check_terminal_result()
            assert app.terminal_status=="terminal_missing" and app.tray.details
            focus.assert_not_called()
    finally:
        app.close(immediate=True)
    restored=App(demo=True,preferences_path=preferences)
    try:
        assert restored.language=="de" and restored.t.language=="de"
    finally:
        restored.close(immediate=True)
print("New features OK: language settings, live switching and persistence; ten pet reactions return to real states; original-terminal click routing")
