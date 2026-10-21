"""Native proof for the 0.2 companion features without touching real sessions."""
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from app import App
from companion import project_id
from i18n import LANGUAGE_NAMES
from sessions import Session
import desktop


def pump(app,seconds=.05):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.root.update()
        time.sleep(.005)


with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'preferences.json'
    path.write_text(json.dumps({'language':'pt','pet_kind':'fox','sound':False,'topmost':False,'pet':[600,320]}))
    app=App(demo=True,preferences_path=path)
    assert app.language=='pt' and app.pet.pet_id=='fox' and not app.sound and not app.topmost
    app.root.after_cancel(app.hover_id)
    try:
        app.reduced=True
        app.select_language('en')
        app.close_menu()
        app.selected=app.sessions[1].key
        app.toggle_favorite()
        assert app.tray.filtered_sessions()[0].key==app.selected
        assert project_id(app.current_session()) in app.favorites
        app.select_session(app.selected)
        assert app.tray.details
        app.select_session(app.selected)
        assert not app.tray.details
        app.save_preferences()
        saved=json.loads(path.read_text())
        assert saved['selected']==app.selected and saved['favorites']
        assert 'language' in saved and 'pet_kind' in saved and 'pet' in saved
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.open_companion_settings()
            pump(app)
            frame=app.tray.companion_frame
            assert frame.winfo_ismapped()
            assert frame.winfo_reqheight()<=frame.winfo_height(),(language,frame.winfo_reqheight(),frame.winfo_height())
            for kind in ('complete','error','waiting'):
                before=app.alerts[kind]
                app.tray.companion_buttons[kind].invoke()
                assert app.alerts[kind]!=before
                app.tray.companion_buttons[kind].invoke()
        with patch.object(app,'work_area',return_value=(0,0,640,480)):
            app.open_companion_settings()
            pump(app)
            assert app.tray.companion_content.winfo_height()>app.tray.companion_frame.winfo_height()
            app.tray.companion_frame.yview_moveto(1)
            pump(app)
            assert app.tray.companion_frame.yview()[1]>=.99
        app.position_tray()
        app.toggle_focus()
        assert app.focus_until>time.time()
        app.toast_queue=[('complete',app.selected,'fictional')]
        app.show_next_notice()
        assert app.toast is None and not app.toast_queue
        app.toggle_focus()
        assert app.focus_until==0
        s=app.sessions[0]
        app.activity.update(app.sessions)
        s.state='idle';s.completed=time.time();s.updated=s.completed
        app.refresh_now();pump(app)
        assert app.toast and app.activity.badge[0]==s.key
        app.refresh_now()
        assert not app.toast_queue
        app.dismiss_notice()
        app.select_session(s.key)
        assert app.activity.badge is None
        app.selected=app.sessions[1].key
        s.state='working';s.updated=time.time()
        pump(app,.3)
        assert app.canvas.itemcget(app.other_dot,'state')=='normal'
        app.refresh_now()
        assert app.t('other_working',count=1) in app.pet_tooltip.text
        app.select_session(s.key)
        s.tokens+=500;s.usage=(400,100,0,0)
        app.refresh_now()
        assert app.activity.today()[0]==500
        assert app.t('summary_today',count='500') in app.usage_summary()
        with patch.object(app.hotkey,'set',return_value=False):
            app.cycle_hotkey()
            assert app.hotkey_failed
        cursor=Session('cursor-demo','Cursor',cwd='D:/Projects/orbit')
        app.sessions.append(cursor)
        app.select_session(cursor.key)
        assert app.tray.terminal_button.cget('text')==app.t('focus_cursor')
        profile={'title':'orbit - Cursor','class':'Chrome_WidgetWin_1','exe':'cursor.exe','target':[111,222,333]}
        with patch('terminal.available_terminals',return_value=[('orbit - Cursor',(111,222,333))]):
            app.focus_selected_terminal()
            assert app.terminal_picker_open
        with patch('terminal.valid_target',return_value=True),patch('terminal.window_profile',return_value=profile),patch('terminal.focus_terminal',return_value=True):
            app.bind_terminal()
        assert app.window_profiles[project_id(cursor)]==profile
        app.select_session(app.sessions[1].key)
        app.save_preferences()
        selected=app.selected
    finally: app.close(immediate=True)
    restarted=App(demo=True,preferences_path=path)
    restarted.root.after_cancel(restarted.hover_id)
    try:
        restarted.sessions.append(cursor)
        restarted.refresh_now()
        assert restarted.selected==selected
        assert restarted.favorites
        assert restarted.activity.today()[0]==500
        assert restarted.window_profiles[project_id(cursor)]==profile
        restarted.select_session(cursor.key)
        with patch('terminal.valid_target',return_value=True),patch('terminal.window_profile',return_value=profile),patch('terminal.focus_terminal',return_value=True) as focus:
            restarted.focus_selected_terminal()
            focus.assert_called_once_with((111,222,333))
    finally: restarted.close(immediate=True)
print('Companion UI OK: favorites, selection persistence, six-language settings, focus, notices, badge, activity indicator, usage and Cursor action.')
