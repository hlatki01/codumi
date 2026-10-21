"""Render each supported language through the real native controls."""
from pathlib import Path
import tempfile
import tkinter.font as tkfont
from unittest.mock import patch

from app import App
from i18n import APP_NAME, CATALOGS


with tempfile.TemporaryDirectory() as folder:
    for language in CATALOGS:
        with patch("i18n.windows_language",return_value=language):
            app=App(demo=True,preferences_path=Path(folder)/(language+".json"))
        try:
            app.root.after_cancel(app.hover_id)
            app.reduced=True
            app.show_tray()
            app.root.update()
            tray=app.tray
            texts=[tray.canvas.itemcget(item,"text") for item in tray.canvas.find_all()
                   if tray.canvas.type(item)=="text"]
            assert APP_NAME in texts and app.t("tagline") in texts
            tagline=next(item for item in tray.canvas.find_all()
                         if tray.canvas.type(item)=="text" and tray.canvas.itemcget(item,"text")==app.t("tagline"))
            assert tray.canvas.bbox(tagline)[2]<=tray.placement["width"]-32,language
            note=next(item for item in tray.canvas.find_all()
                      if tray.canvas.type(item)=="text" and tray.canvas.itemcget(item,"text")==app.t("pet_session_note"))
            assert tray.canvas.bbox(note)[2]<=tray.placement["width"]-32,language
            assert tray.canvas.bbox(note)[3]<tray.session_canvas.winfo_y(),language
            counts=next(item for item in tray.canvas.find_all()
                        if tray.canvas.type(item)=="text" and "\n" in tray.canvas.itemcget(item,"text"))
            assert tray.canvas.bbox(counts)[2]<tray.activity_button.winfo_x(),language
            app.open_menu()
            app.root.update()
            for key,button in tray.settings_buttons.items():
                assert button.winfo_ismapped(),(language,key)
                assert tkfont.Font(font=button.cget("font")).measure(button.cget("text"))+20<=button.winfo_width(),(language,key)
            app.open_pet_picker()
            app.root.update()
            for pet_id,button in tray.pet_buttons.items():
                assert button.cget("text").strip()==app.t.pet_name(pet_id)
                assert button.winfo_ismapped()
                assert tkfont.Font(font=button.cget("font")).measure(button.cget("text"))+52<=button.winfo_width(),(language,pet_id)
            app.select_pet("dragon")
            assert app.pet.pet_id=="dragon"
            app.close_menu()
            app.toggle_details()
            app.root.update()
            assert tray.prompt_label.cget("text")==app.current_session().prompt[:120]
            tray.close_button.invoke()
            assert app.closed
        finally:
            app.close(immediate=True)
print("Native locale UI OK: en, pt, es, fr, de, it; branding, layout, menus, pet selection, details and close")
