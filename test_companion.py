"""New release invariants: observed usage, state transitions and Cursor formats."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from companion import Activity,project_id
from sessions import Session,Tail,Monitor
from pet import personality_motion,PETS
import terminal
import desktop


class CompanionTests(unittest.TestCase):
    def test_usage_baseline_backfill_reset_and_restart(self):
        now=time.time()
        session=Session('one','Claude',tokens=100,usage=(40,10,20,30))
        activity=Activity()
        activity.update([session],now)
        self.assertEqual(activity.today(),[0]*5)
        session.tokens=120; session.usage=(50,15,20,35)
        activity.update([session],now+1)
        self.assertEqual(activity.today(),[20,10,5,0,5])
        session.tokens_partial=True; session.tokens=300
        activity.update([session],now+2)
        session.tokens_partial=False; session.tokens=400
        activity.update([session],now+3)
        self.assertEqual(activity.today()[0],20)
        session.tokens=410
        activity.update([session],now+4)
        self.assertEqual(activity.today()[0],30)
        restarted=Activity(activity.days)
        restarted.update([session],now+5)
        self.assertEqual(restarted.today()[0],30)
        session.tokens=1
        restarted.update([session],now+6)
        self.assertEqual(restarted.today()[0],30)

    def test_notifications_do_not_replay_history_or_repeat(self):
        now=time.time()
        session=Session('one','Claude',state='working',updated=now)
        a=Activity(); a.update([session],now)
        self.assertEqual(a.ready,[])
        session.state='idle';session.completed=now+1;session.updated=now+1
        a.update([session],now+1);a.update([session],now+2)
        self.assertEqual([r[0] for r in a.ready],['complete'])
        self.assertEqual(a.badge[0],'one')
        a.ready.clear()
        session.state='waiting';session.updated=now+3
        a.update([session],now+3);a.update([session],now+4)
        session.state='error';session.updated=now+5
        a.update([session],now+5)
        self.assertEqual([r[0] for r in a.ready],['waiting','error'])
        a.update([session],now+100)
        self.assertIsNone(a.badge)

    def test_project_identity_and_invalid_saved_totals(self):
        self.assertEqual(project_id(Session('one','Claude',cwd='D:/Projects/Orbit/')),
                         project_id(Session('two','Claude',cwd='d:\\projects\\orbit')))
        self.assertNotEqual(project_id(Session('one','Claude',cwd='D:/Orbit')),
                            project_id(Session('one','Cursor',cwd='D:/Orbit')))
        activity=Activity({'badbadbad!':[True,-1,'3',10**99,4]})
        activity.update([])
        self.assertEqual(activity.days,{})

    def test_cursor_real_role_records_and_stream_result(self):
        s=Session('one','Cursor')
        s.apply({'role':'user','message':{'content':[{'type':'text','text':'hello'}]}},10)
        self.assertEqual((s.prompt,s.state),('hello','working'))
        s.apply({'role':'assistant','message':{'content':[{'type':'tool_use','name':'Shell'}]}},11)
        self.assertEqual((s.tool,s.state),('Shell','working'))
        self.assertEqual(s.tokens,0)
        s.apply({'type':'tool_call','tool_call':{'readToolCall':{}}},12)
        self.assertEqual(s.tool,'readToolCall')
        s.apply({'type':'result','subtype':'success','is_error':False},13)
        self.assertEqual((s.state,s.completed),('idle',13))
        s.apply({'type':'result','is_error':True},14)
        self.assertEqual(s.state,'error')

    def test_cursor_discovery_workspace_metadata_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True):
            home=Path(folder)
            workspace=home/'AppData/Roaming/Cursor/User/workspaceStorage/abc/workspace.json'
            workspace.parent.mkdir(parents=True)
            workspace.write_text(json.dumps({'folder':'file:///d%3A/Projects/orbit'}))
            transcript=home/'.cursor/projects/d-Projects-orbit/agent-transcripts/abc/abc.jsonl'
            transcript.parent.mkdir(parents=True)
            contents=json.dumps({'role':'user','message':{'content':'fictional prompt'}})+'\n'
            transcript.write_text(contents)
            ignored=home/'.cursor/projects/private.jsonl';ignored.write_text(contents)
            sessions=Monitor(home).poll()
            self.assertEqual(len(sessions),1)
            self.assertEqual((sessions[0].provider,sessions[0].project),('Cursor','orbit'))
            self.assertEqual(transcript.read_text(),contents)
            collision=workspace.parent.parent/'def/workspace.json'
            collision.parent.mkdir()
            collision.write_text(json.dumps({'folder':'file:///d%3A/Projects-orbit'}))
            ambiguous=Monitor(home).poll()[0]
            self.assertEqual(ambiguous.cwd,'')
            self.assertEqual(ambiguous.project_hint,'d-Projects-orbit')
            with transcript.open('a') as f: f.write('{"role":"assistant","message":{"content":"hel')
            tail=Tail(transcript,'Cursor');tail.poll()
            self.assertEqual(tail.session.prompt,'fictional prompt')

    def test_terminal_profiles_require_the_original_window_identity(self):
        profile={'title':'orbit - Cursor','class':'Chrome_WidgetWin_1','exe':'cursor.exe','target':[1,2,3]}
        with patch.object(terminal,'valid_target',return_value=True), patch.object(terminal,'window_profile',return_value=profile):
            self.assertEqual(terminal.restore_window(profile),(1,2,3))
            self.assertIsNone(terminal.restore_window({'title':'orbit'}))
            self.assertIsNone(terminal.restore_window({**profile,'target':[True,2,3]}))
            self.assertIsNone(terminal.restore_window({**profile,'target':[1,2**40,3]}))
        with patch.object(terminal,'valid_target',return_value=False):
            self.assertIsNone(terminal.restore_window(profile))
        with patch.object(terminal,'valid_target',return_value=True), patch.object(terminal,'window_profile',return_value={**profile,'title':'another project'}):
            self.assertIsNone(terminal.restore_window(profile))

    def test_hotkey_registration_failure_and_cleanup(self):
        hotkey=desktop.GlobalHotkey()
        with patch.object(desktop.user,'RegisterHotKey',return_value=False):
            self.assertFalse(hotkey.set('Ctrl+Alt+N'))
        with patch.object(desktop.user,'RegisterHotKey',return_value=True),\
             patch.object(desktop.user,'UnregisterHotKey') as unregister:
            self.assertTrue(hotkey.set('Ctrl+Shift+F12'))
            self.assertTrue(hotkey.set('Off'))
            unregister.assert_called_once()
        self.assertFalse(hotkey.set('invalid'))

    def test_hotkey_message_is_received_on_its_own_thread(self):
        hotkey=desktop.GlobalHotkey()
        with patch.object(desktop.user,'RegisterHotKey',return_value=True), patch.object(desktop.user,'UnregisterHotKey'):
            try:
                self.assertTrue(hotkey.set('Ctrl+Alt+N'))
                self.assertTrue(desktop.user.PostThreadMessageW(hotkey.thread_id,0x312,hotkey.identity,0))
                until=time.monotonic()+1
                while not hotkey.signal.is_set() and time.monotonic()<until: time.sleep(.005)
                self.assertTrue(hotkey.pressed())
                self.assertFalse(hotkey.pressed())
            finally: hotkey.close()

    def test_personalities_are_distinct_and_bounded(self):
        signatures=[]
        for pet in PETS:
            values=[personality_motion(pet,'working',i/12) for i in range(36)]
            self.assertTrue(all(abs(scale)<.04 and abs(hop)<=2 and abs(sway)<=1 for scale,hop,sway in values))
            self.assertEqual(personality_motion(pet,'error',1),(0,0,0))
            signatures.append(tuple(values))
        self.assertEqual(len(set(signatures)),10)


if __name__=='__main__': unittest.main()
