"""Native integration checks: hover, focus, shaped input regions, drag and preferences."""
import ctypes
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import tkinter as tk

import desktop
from app import App, load_preferences
from sessions import Session
from pet import PETS


def pump(app, seconds=.1):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        app.root.update()
        time.sleep(.006)


with tempfile.TemporaryDirectory() as folder:
    preferences = Path(folder)/"preferences.json"
    preferences.write_text('invalid',encoding='utf-8')
    assert load_preferences(preferences)=={}
    app = App(demo=True,preferences_path=preferences)
    app.root.after_cancel(app.hover_id)
    try:
        pump(app)
        assert (app.root.winfo_width(),app.root.winfo_height())==(64,64)
        assert not app.tray_visible and not app.tray.window.winfo_ismapped()
        assert not desktop.contains(app.root,app.pet_x,app.pet_y)
        assert desktop.contains(app.root,app.pet_x+32,app.pet_y+32)
        assert len(app.tray.rows)==3
        old_x,old_y = app.pet_x,app.pet_y

        # A focused editor proxy must keep its foreground HWND through hover.
        editor = tk.Toplevel(app.root)
        editor.title("Notchi focus regression fixture")
        entry = tk.Entry(editor)
        entry.pack()
        editor.update()
        desktop.place(editor,app.pet_x-500,app.pet_y-250,600,540)
        entry.focus_force()
        pump(app)
        foreground = None
        if desktop.WINDOWS:
            desktop.user.GetForegroundWindow.restype=ctypes.c_void_p
            foreground = desktop.user.GetForegroundWindow()
            desktop.user.WindowFromPoint.argtypes = [desktop.w.POINT]
            desktop.user.WindowFromPoint.restype = desktop.w.HWND
            def hit(x,y):
                return desktop.user.GetAncestor(desktop.user.WindowFromPoint(desktop.w.POINT(x,y)),2)
            assert hit(app.pet_x,app.pet_y)==desktop.handle(editor), "transparent pet corners blocked input"
            assert hit(app.pet_x+32,app.pet_y+32)==desktop.handle(app.root)
            assert desktop.user.GetWindowLongPtrW(desktop.handle(app.root),-20)&0x08000000

        now = time.monotonic()
        app.update_hover(app.pet_x+32,app.pet_y+32,now)
        pump(app,.65)
        assert app.tray_visible and app.spring.target==1
        p = app.tray.placement
        assert p["side"]=="left"
        assert app.tray.window.winfo_x()+p["width"]==app.pet_x
        assert (app.pet_x,app.pet_y)==(old_x,old_y)
        assert not desktop.contains(app.tray.window,p["x"],p["y"])
        assert desktop.contains(app.tray.window,p["x"]+25,p["y"]+25)
        assert desktop.contains(app.tray.window,p["x"]+p["width"]-3,p["y"]+p["connector"])
        if foreground is not None:
            assert desktop.user.GetForegroundWindow()==foreground, "hover stole editor focus"
            assert desktop.user.GetWindowLongPtrW(desktop.handle(app.tray.window),-20)&0x08000000
            assert hit(p["x"],p["y"])==desktop.handle(editor), "tray corners blocked input"
            assert hit(p["x"]+25,p["y"]+25)==desktop.handle(app.tray.window)

        outside = (-10000,-10000)
        now = time.monotonic()
        app.update_hover(*outside,now)
        app.update_hover(*outside,now+.249)
        assert app.spring.target==1, "tray closed before 250 ms"
        app.update_hover(p["x"]+50,p["y"]+100,now+.249)
        assert app.leave_at is None, "moving from avatar into tray must cancel close"
        app.update_hover(*outside,now+.3)
        app.update_hover(*outside,now+.551)
        assert app.spring.target==0
        pump(app,.65)
        assert not app.tray_visible and not app.tray.window.winfo_ismapped()

        app.reduced=True
        app.show_tray()
        pump(app,.15)
        assert app.spring.value==1
        app.tray.rows["demo-codex"][0].invoke()
        assert app.selected=="demo-codex" and app.tray.details
        app.terminal_pending = app.selected
        app.terminal_requested = app.selected
        app.tray.rows["demo-codex"][0].invoke()
        assert not app.tray.details and app.selected=="demo-codex"
        app.terminal_results.put(("demo-codex",(100,200,300)))
        app.check_terminal_result()
        assert not app.tray.details, "old terminal lookup reopened collapsed details"
        assert app.terminal_pending is None and app.terminal_requested is None
        app.tray.rows["demo-claude"][0].invoke()
        assert app.selected=="demo-claude" and app.tray.details
        app.tray.rows["demo-codex"][0].invoke()
        assert app.selected=="demo-codex" and app.tray.details
        assert app.tray_visible
        app.tray.toggle_filter()
        assert len(app.tray.rows)==1
        app.tray.toggle_filter()
        assert len(app.tray.rows)==3
        app.select_session("demo-claude")
        assert not app.tray.details
        app.select_session("demo-claude")
        pump(app)
        assert app.tray.details and app.tray.detail_frame.winfo_ismapped()
        assert app.tray.window.winfo_x()+app.tray.placement["width"]==app.pet_x
        assert app.tray.prompt_label.cget("text")

        # A real completion signal celebrates once and does not celebrate old history.
        assert app.pet.completed_until==0
        app.sessions[0].completed=time.time()
        app.refresh_now()
        assert app.pet.completed_until>time.monotonic()
        completion = app.pet.completed_until
        app.refresh_now()
        assert app.pet.completed_until==completion

        # Reuse sprite items between frames; reduced motion must freeze geometry.
        app.pet.completed_until=0
        app.pet.update("working",1)
        app.pet.draw(2,"Claude")
        ids=app.canvas.find_all()
        for i in range(20):
            app.pet.draw(2+i*.01,"Claude")
        assert app.canvas.find_all()==ids
        app.pet.draw(2,"Claude",reduced=True)
        frozen=[app.canvas.coords(item) for item in app.canvas.find_all()]
        app.pet.draw(3,"Claude",reduced=True)
        assert frozen==[app.canvas.coords(item) for item in app.canvas.find_all()]
        app.pet.update("error",4)
        app.pet.celebrate(4)
        app.pet.draw(4,"Claude")
        assert app.pet.sprite_key[0]=="error"

        # Keep the entire session list scrollable and preserve keyboard access.
        original=list(app.sessions)
        app.sessions.extend(Session(f"extra-{i}","Codex",f"D:/project-{i}") for i in range(45))
        app.refresh_now()
        pump(app)
        assert len(app.tray.rows)==48
        app.tray.session_canvas.yview_moveto(1)
        pump(app)
        assert app.tray.session_canvas.yview()[0]>0
        app.show_tray(focus=True)
        pump(app)
        if desktop.WINDOWS:
            assert not desktop.user.GetWindowLongPtrW(desktop.handle(app.tray.window),-20)&0x08000000
        app.keyboard_mode=False
        desktop.prepare(app.tray.window,app.topmost)
        app.sessions=original
        app.refresh_now()
        app.tray.session_canvas.yview_moveto(0)

        # Drag dismisses immediately, persists and cannot trigger hover on release.
        x,y = app.pet_x,app.pet_y
        app.press(SimpleNamespace(x_root=x+32,y_root=y+32))
        assert app.tray_visible, "a press without drag must not flash the tray"
        app.move(SimpleNamespace(x_root=x+12,y_root=y+52))
        assert not app.tray_visible
        app.release()
        pump(app)
        assert (app.pet_x,app.pet_y)==(x-20,y+20)
        app.update_hover(app.pet_x+32,app.pet_y+32,time.monotonic()+1)
        assert app.spring.target==0
        app.update_hover(*outside,time.monotonic()+1)
        app.update_hover(app.pet_x+32,app.pet_y+32,time.monotonic()+1)
        assert app.spring.target==1
        app.toggle_sound()
        app.toggle_topmost()
        saved=json.loads(preferences.read_text())
        assert saved["sound"] and saved["topmost"] is False
        assert saved["pet"]==[app.pet_x,app.pet_y]
        assert not (desktop.user.GetWindowLongPtrW(desktop.handle(app.root),-20)&8) if desktop.WINDOWS else True

        # Settings use ordinary buttons; test the actions, not only showing a popup.
        app.open_menu()
        pump(app)
        assert app.menu_open and app.tray.settings_frame.winfo_ismapped()
        assert app.tray.settings_frame.winfo_reqheight()<=app.tray.settings_frame.winfo_height()
        app.tray.settings_buttons["pets"].invoke()
        pump(app)
        assert app.pet_picker_open and app.tray.pet_frame.winfo_ismapped()
        assert len(app.tray.pet_buttons)==10
        assert app.tray.pet_frame.winfo_reqheight()<=app.tray.pet_frame.winfo_height()
        for pet_id,button in app.tray.pet_buttons.items():
            assert button.winfo_y()+button.winfo_height()<=app.tray.pet_frame.winfo_height()
            button.invoke()
            assert app.pet.pet_id==pet_id
            assert json.loads(preferences.read_text())["pet_kind"]==pet_id
            for state in ("working","thinking","sleeping","waiting","error","compacting","idle"):
                app.pet.completed_until=0
                app.pet.update(state,10)
                app.pet.draw(10.2,"Claude",reduced=True)
                assert app.pet.sprite_key[-1]==pet_id
                assert app.canvas.find_withtag("sprite")
                assert len(app.canvas.find_all())<150
        assert app.pet.pet_id=="dragon"
        saved_bytes=preferences.read_bytes()
        assert not app.select_pet("not-a-pet")
        assert not app.select_pet([])
        assert preferences.read_bytes()==saved_bytes
        app.tray.pet_back.invoke()
        pump(app)
        assert app.menu_open and not app.pet_picker_open and app.tray.settings_frame.winfo_ismapped()
        before_sound=app.sound
        app.tray.settings_buttons["sound"].invoke()
        assert app.sound != before_sound
        assert json.loads(preferences.read_text())["sound"] == app.sound
        app.tray.settings_buttons["sound"].invoke()
        assert app.sound == before_sound
        before_topmost=app.topmost
        app.tray.settings_buttons["topmost"].invoke()
        assert app.topmost != before_topmost
        app.tray.settings_buttons["topmost"].invoke()
        app.tray.settings_buttons["back"].invoke()
        pump(app)
        assert not app.menu_open and not app.tray.settings_frame.winfo_ismapped()
        app.open_menu()
        now=time.monotonic()
        app.update_hover(*outside,now)
        app.update_hover(*outside,now+.251)
        pump(app,.2)
        assert not app.tray_visible and not app.menu_open
        app.show_tray()

        # Dismissal remains dismissed until the cursor leaves the interactive area.
        app.dismiss_tray()
        app.update_hover(app.pet_x+32,app.pet_y+32,time.monotonic()+2)
        assert app.spring.target==0
        editor.destroy()
    finally:
        app.close(immediate=True)

    restored = App(demo=True,preferences_path=preferences)
    restored.root.after_cancel(restored.hover_id)
    try:
        pump(restored)
        assert restored.sound and not restored.topmost
        assert restored.pet.pet_id=="dragon"
        assert [restored.pet_x,restored.pet_y]==saved["pet"]
        assert not restored.tray_visible
        restored.show_tray()
        pump(restored)
        restored.tray.close_button.invoke()
        assert restored.closed and restored.stopping.is_set()
    finally:
        restored.close(immediate=True)
    data=json.loads(preferences.read_text())
    data["pet_kind"]=["invalid"]
    preferences.write_text(json.dumps(data))
    quit_app=App(demo=True,preferences_path=preferences)
    quit_app.root.after_cancel(quit_app.hover_id)
    try:
        assert quit_app.pet.pet_id=="notchi"
        quit_app.open_menu()
        pump(quit_app)
        assert quit_app.tray.settings_buttons["quit"].winfo_ismapped()
        quit_app.tray.settings_buttons["quit"].invoke()
        assert quit_app.closed and quit_app.stopping.is_set()
    finally:
        quit_app.close(immediate=True)
print("Native UI OK: 64px pet, shape hit-tests, 250ms hover, spring, focus, sessions, completion, drag, reduced motion and persistence")
