"""Actual canvas and Win32 exit checks without leaving a blocking overlay."""
import ctypes
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

from app import App
import desktop
from pet import PETS


with tempfile.TemporaryDirectory() as folder:
    prefs=Path(folder)/"prefs.json"
    app=App(demo=True,preferences_path=prefs)
    app.root.after_cancel(app.hover_id)
    try:
        c=app.canvas
        for pet_id in PETS:
            app.pet.pet_id=pet_id
            app.pet.prepare_exit("Claude")
            ids=c.find_all()
            app.pet.draw_exit(0)
            original=c.coords(app.pet.outer)
            app.pet.draw_exit(.325)
            assert c.bbox("sprite")[3]<c.coords(app.pet.outer)[1],pet_id
            app.pet.draw_exit(.65)
            assert c.coords(app.pet.outer)==original
            landed=c.bbox("sprite")
            assert landed[0]>=88 and landed[2]<=152
            app.pet.draw_exit(.85)
            assert c.coords(app.pet.outer)[2]-c.coords(app.pet.outer)[0]<31.01
            app.pet.draw_exit(1)
            assert c.coords(app.pet.outer)==[120,120,120,120]
            assert c.find_all()==ids,"exit must retain canvas items"
        underlay=tk.Toplevel(app.root)
        underlay.title("codumi exit click-through fixture")
        underlay.update()
        desktop.place(underlay,app.pet_x-100,app.pet_y-100,300,300)
        desktop.prepare(app.root,True)
        app.reduced=False
        app.pet.pet_id="dragon"
        app.show_tray()
        app.root.update()
        pet_position=(app.pet_x,app.pet_y)
        app.tray.close_button.invoke()
        assert app.closed and app.stopping.is_set() and not app.exit_finished
        app.root.update_idletasks()
        assert not app.tray_visible
        assert (app.root.winfo_width(),app.root.winfo_height())==(240,176)
        assert (app.root.winfo_x(),app.root.winfo_y())==(pet_position[0]-88,pet_position[1]-88)
        if desktop.WINDOWS:
            assert desktop.user.GetWindowLongPtrW(desktop.handle(app.root),-20)&0x20
            desktop.user.WindowFromPoint.argtypes=[desktop.w.POINT]
            desktop.user.WindowFromPoint.restype=desktop.w.HWND
            hit=desktop.user.GetAncestor(desktop.user.WindowFromPoint(
                desktop.w.POINT(pet_position[0]+32,pet_position[1]+32)),2)
            assert hit!=desktop.handle(app.root),"exit overlay blocked clicks"
        saved=json.loads(prefs.read_text())
        assert saved["pet"]==list(pet_position),"animation must not save its expanded window position"
        started=app.exit_started
        app.close()
        assert app.exit_started==started
        deadline=time.monotonic()+2
        while not app.exit_finished and time.monotonic()<deadline:
            app.root.update()
            time.sleep(.006)
        assert app.exit_finished
        assert json.loads(prefs.read_text())["pet"]==list(pet_position)
    finally:
        app.close(immediate=True)

    reduced=App(demo=True,preferences_path=prefs)
    try:
        reduced.reduced=True
        reduced.open_menu()
        reduced.tray.settings_buttons["quit"].invoke()
        assert reduced.closed and reduced.exit_finished
    finally:
        reduced.close(immediate=True)

    edge=App(demo=True,preferences_path=Path(folder)/"edge.json")
    try:
        area=edge.work_area()
        edge.pet_x,edge.pet_y=area[0]+12,area[1]+12
        edge.reduced=False
        edge.close()
        assert edge.exit_sideways==64 and edge.exit_height==24
        edge.pet.draw_exit(.325,edge.exit_height,edge.exit_sideways)
        left,top,right,bottom=edge.canvas.bbox("sprite")
        assert left+edge.root.winfo_x()>=area[0]
        assert top+edge.root.winfo_y()>=area[1]
    finally:
        edge.close(immediate=True)

    failed=App(demo=True,preferences_path=prefs)
    try:
        failed.reduced=False
        with patch.object(failed.pet,"draw_exit",side_effect=tk.TclError("fixture")),patch("app.logging.exception") as logged:
            failed.close()
            logged.assert_called_once()
        assert failed.exit_finished,"animation failures must still close the app"
    finally:
        failed.close(immediate=True)
print("Exit native OK: all ten sprites jump outside, land, shrink, click through; real close finishes; position preserved, reduced motion and failure fallback")
