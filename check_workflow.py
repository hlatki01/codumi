"""Native v0.3 integration; uses fictional sessions and temporary preferences only."""
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

from app import App
from companion import project_id,TONES
from i18n import LANGUAGE_NAMES
import desktop


def pump(app,seconds=.06):
    until=time.monotonic()+seconds
    while time.monotonic()<until and not app.closed:
        app.check_update_results()
        if app.closed: break
        app.root.update()
        time.sleep(.005)


def texts(widget):
    result=[]
    for child in widget.winfo_children():
        try: result.append(str(child.cget('text')))
        except tk.TclError: pass
        result.extend(texts(child))
    return '\n'.join(result)


with tempfile.TemporaryDirectory() as folder,patch('updater.check_latest') as check:
    preferences=Path(folder)/'preferences.json'
    app=App(demo=True,preferences_path=preferences)
    app.root.after_cancel(app.hover_id)
    try:
        check.assert_not_called()
        app.reduced=True
        a,b=app.sessions[:2]
        a.state='waiting';a.updated=time.time();a.prompt='PRIVATE-PROMPT'
        b.state='error';b.updated=time.time()
        app.refresh_now()
        app.dismiss_notice()
        app.toast_queue.clear()
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.open_workspace('attention')
            pump(app)
            assert app.tray.workspace.frame.winfo_ismapped()
            assert 'session:'+a.key in app.tray.workspace.buttons
            assert 'session:'+b.key in app.tray.workspace.buttons
            app.tray.workspace.buttons['session:'+a.key].invoke()
            assert app.selected==a.key and app.tray.details
            app.open_workspace('attention')
            with patch.object(app,'focus_selected_terminal') as focus:
                app.tray.workspace.buttons['window:'+b.key].invoke()
                assert app.selected==b.key
                focus.assert_called_once()
            app.open_workspace('project')
            assert 'pet' in app.tray.workspace.combos and 'alert.error' in app.tray.workspace.combos
            app.open_workspace('updates')
            assert app.tray.workspace.buttons['check'].cget('state')=='normal'
        app.select_language('en')
        app.select_session(a.key)
        app.open_workspace('project')
        app.tray.workspace.combos['pet'].current(10)
        app.tray.workspace.combos['pet'].event_generate('<<ComboboxSelected>>')
        pump(app)
        assert app.pet.pet_id=='dragon' and app.default_pet=='notchi'
        held=app.tray.workspace.combos['pet']
        app.tray.filter_active=True
        app.refresh_now()
        assert app.selected==a.key and app.tray.workspace.combos['pet'] is held
        app.open_workspace_session(a.key)
        app.tray.filter_active=True
        a.state='idle';a.updated=time.time()-600
        app.open_workspace_session(a.key)
        assert app.selected==a.key and not app.tray.filter_active
        app.select_session(b.key)
        assert app.pet.pet_id=='notchi'
        app.select_pet('cat')
        app.select_session(a.key)
        assert app.pet.pet_id=='dragon' and app.default_pet=='cat'
        a.state='working';a.updated=time.time()
        app.activity.update(app.sessions)
        app.toggle_history()
        a.state='idle';a.completed=time.time();a.updated=a.completed
        app.refresh_now();app.dismiss_notice()
        assert len(app.history.records)==1 and 'PRIVATE-PROMPT' not in json.dumps(app.history.records)
        app.open_workspace('history')
        assert a.project in texts(app.tray.workspace.content)
        app.toggle_presentation()
        assert app.presentation and app.toast is None
        assert a.project not in texts(app.tray.workspace.content)
        app.close_menu();app.tray.details=True;app.position_tray();app.show_tray();pump(app)
        assert app.tray.prompt_label.cget('text')==app.t('presentation_hidden')
        assert a.project not in app.root.title()
        assert all(a.project not in row[0].cget('text') for row in app.tray.rows.values())
        app.toast_queue=[('complete',a.key,a.project)]
        app.show_next_notice()
        assert app.toast is None and not app.toast_queue
        app.open_terminal_picker()
        assert not app.terminal_picker_open
        app.toggle_presentation()
        app.toggle_history()
        assert not app.history.enabled and app.history.records==[]
        app.projects.set(a,'muted',None)
        app.projects.set(a,'alert.error',False)
        assert not app.notice_enabled('error',a.key)
        app.projects.set(a,'alert.error',None)
        app.focus_until=0
        app.select_session(a.key)
        app.open_companion_settings()
        app.close_menu();app.hide_tray(immediate=True)
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.close_menu();app.hide_tray(immediate=True)
            for tone in TONES:
                app.tone=tone
                app.toast_queue=[('complete',a.key,a.project)]
                app.show_next_notice();pump(app)
                key='speech_complete' if tone=='friendly' else 'speech_'+tone+'_complete'
                body=next(w for w in app.toast.winfo_children() if isinstance(w,tk.Button) and w.cget('text')!='×')
                assert body.cget('text')==app.t(key,project=a.project)
                actions=next(w for w in app.toast.winfo_children() if isinstance(w,tk.Frame))
                assert len(actions.winfo_children())==3
                assert all(w.winfo_height()>=w.winfo_reqheight() for w in actions.winfo_children()),language
                if tone=='direct':
                    with patch.object(app,'focus_selected_terminal') as focus:
                        actions.winfo_children()[1].invoke()
                        focus.assert_called_once()
                else: app.dismiss_notice()
        app.toast_queue=[('complete',a.key,a.project)]
        app.show_next_notice();pump(app)
        actions=next(w for w in app.toast.winfo_children() if isinstance(w,tk.Frame))
        actions.winfo_children()[2].invoke()
        assert app.projects.get(a)['muted'] and not app.notice_enabled('complete',a.key)
        app.set_project_option('muted',None)
        app.close_menu();app.hide_tray(immediate=True)
        app.edge_mode=True
        app.pet_x,app.pet_y=936,350
        desktop.place(app.root,936,350,64,64)
        with patch.object(app,'work_area',return_value=(0,0,1024,768)):
            app.update_edge(-10000,-10000,20)
            app.update_edge(-10000,-10000,21.1)
            pump(app)
            assert app.edge_hidden and app.pet_x==936
            actual_x=app.root.winfo_x()
            assert desktop.contains(app.root,actual_x+16,app.pet_y+32)
            assert not desktop.contains(app.root,actual_x+40,app.pet_y+32)
            app.save_preferences()
            assert json.loads(preferences.read_text())['pet']==[936,350]
            app.update_hover(actual_x+16,app.pet_y+32,21.2)
            assert not app.edge_hidden and app.tray_visible
        app.edge_mode=False
        app.open_workspace('updates')
        with patch.object(app,'work_area',return_value=(0,0,640,480)):
            app.position_tray();pump(app)
            app.tray.workspace.canvas.yview_moveto(1);pump(app)
            assert app.tray.workspace.canvas.yview()[1]>=.99
        info={'version':'v0.3.1','notes':'Fictional changes','url':'https://github.com/hlatki01/codumi/releases/tag/v0.3.1'}
        check.return_value=info
        app.check_updates();pump(app,.2)
        assert app.update_status=='available' and app.update_info==info
        staged={'root':Path(folder)/'updates/stage/codumi-Windows','archive':Path(folder)/'package.zip','digest':'0'*64,'version':'v0.3.1'}
        with patch('updater.stage_release',return_value=staged):
            app.download_update();pump(app,.2)
            assert app.update_status=='ready' and app.staged_update==staged
        with patch('updater.verify_stage',side_effect=ValueError('changed')),patch('app.logging.exception') as log:
            app.install_update();pump(app,.2)
            assert app.update_status=='failed' and not app.closed
            log.assert_called_once()
        app.staged_update=staged
        with patch('updater.verify_stage',return_value=staged['root']),patch('terminal.process_start',return_value=123),patch('app.subprocess.Popen') as launch:
            app.install_update();pump(app,.2)
            assert app.closed
            command=launch.call_args.args[0]
            assert '--apply' in command and '--language' in command
    finally: app.close(immediate=True)
    reloaded=App(demo=True,preferences_path=preferences)
    reloaded.root.after_cancel(reloaded.hover_id)
    try:
        assert reloaded.default_pet=='cat'
        assert reloaded.projects.get(reloaded.sessions[0])['pet']=='dragon'
        assert not reloaded.history.enabled
        assert not reloaded.presentation
        assert reloaded.update_status=='not_checked'
        assert check.call_count==1
    finally: reloaded.close(immediate=True)
print('Workflow UI OK: attention, optional history, per-project pets, privacy, actionable voices, edge clipping/reveal, small-screen scrolling and mocked update lifecycle.')
