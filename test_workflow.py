"""V0.3 models: optional metadata, per-project overrides and attention order."""
import json
import time
import unittest

from companion import ProjectPreferences,CompletionHistory,attention_queue,project_id
from sessions import Session
import desktop


class WorkflowTests(unittest.TestCase):
    def test_attention_is_a_live_queue_and_orders_errors_first(self):
        now=time.time()
        sessions=[Session('a','Claude',state='working'),Session('b','Cursor',state='waiting',updated=now),
                  Session('c','Codex',state='error',updated=now-1000)]
        self.assertEqual([s.key for s in attention_queue(sessions)],['c','b'])
        sessions[2].state='working'
        self.assertEqual([s.key for s in attention_queue(sessions)],['b'])

    def test_project_overrides_validate_and_preserve_inheritance(self):
        session=Session('a','Claude',cwd='D:/Projects/orbit')
        other=Session('b','Codex',cwd=session.cwd)
        projects=ProjectPreferences()
        for field,value in [('pet','dragon'),('tone','playful'),('edge',True),('alert.error',False),('muted',True)]:
            self.assertTrue(projects.set(session,field,value))
        self.assertEqual(projects.get(other),{})
        self.assertEqual(ProjectPreferences(projects.values).get(session)['pet'],'dragon')
        self.assertTrue(projects.set(session,'pet',None))
        self.assertNotIn('pet',projects.get(session))
        for field,value in [('pet','unknown'),('tone',[]),('edge','true'),('muted',1),('extra','anything')]:
            self.assertFalse(projects.set(session,field,value))
        clean=ProjectPreferences({project_id(session):{'pet':'cat','edge':None,'unknown':True}})
        self.assertEqual(clean.get(session),{'pet':'cat'})

    def test_history_is_opt_in_deduplicated_and_contains_no_prompts_or_paths(self):
        now=time.time()
        session=Session('D:/private/transcript.jsonl','Claude',cwd='D:/Projects/orbit',prompt='PRIVATE PROMPT',completed=now)
        history=CompletionHistory()
        history.add(session)
        self.assertEqual(history.records,[])
        history.enabled=True
        history.add(session);history.add(session)
        self.assertEqual(len(history.records),1)
        text=json.dumps(history.records)
        self.assertNotIn('PRIVATE PROMPT',text)
        self.assertNotIn('transcript.jsonl',text)
        self.assertNotIn('D:/',text)
        self.assertEqual(CompletionHistory(True,history.records).records,history.records)
        history.disable()
        self.assertFalse(history.enabled)
        self.assertEqual(history.records,[])

    def test_history_has_a_size_and_age_limit_and_discards_unknown_fields(self):
        history=CompletionHistory(True)
        for i in range(110): history.add(Session(str(i),'Cursor',completed=time.time(),cwd='D:/orbit'))
        self.assertEqual(len(history.records),100)
        history.records[0]['time']=time.time()-31*86400
        history.prune()
        self.assertEqual(len(history.records),99)
        data={**history.records[0],'prompt':'secret','extra':'ignored'}
        restored=CompletionHistory(True,[None,{},data])
        self.assertEqual(len(restored.records),1)
        self.assertNotIn('prompt',restored.records[0])
        self.assertNotIn('extra',restored.records[0])

    def test_history_ignores_malformed_saved_records(self):
        data={'id':'a'*64,'session':'b'*64,'project':'c'*64,'name':'orbit','provider':[], 'time':time.time()}
        self.assertEqual(CompletionHistory(True,[data]).records,[])

    def test_presentation_shortcut_uses_a_distinct_combination(self):
        from unittest.mock import patch
        hotkey=desktop.GlobalHotkey()
        with patch.object(desktop.user,'RegisterHotKey',return_value=True) as register,patch.object(desktop.user,'UnregisterHotKey'):
            try:
                self.assertTrue(hotkey.set('Ctrl+Alt+P'))
                register.assert_called_once_with(None,hotkey.identity,0x4003,0x50)
            finally: hotkey.close()

    def test_edge_coordinates_keep_saved_positions_logical(self):
        area=(-1280,0,0,720)
        self.assertEqual(desktop.edge_position(-1260,100,area),(-1318,100))
        self.assertEqual(desktop.edge_position(-88,100,area),(-26,100))
        self.assertIsNone(desktop.edge_position(-600,100,area))


class PeriodicUpdateTests(unittest.TestCase):
    def app(self):
        from app import App
        from unittest.mock import Mock
        app=App.__new__(App)
        app.demo=app.closed=app.update_busy=False
        app.staged_update=app.update_info=None
        app.next_update_check=30
        app.start_update_task=Mock()
        return app

    def test_waits_until_due_and_schedules_six_hours_after_each_check(self):
        from unittest.mock import patch
        app=self.app()
        with patch('app.time.monotonic',return_value=29): app.maybe_check_updates()
        app.start_update_task.assert_not_called()
        with patch('app.time.monotonic',return_value=30): app.maybe_check_updates()
        self.assertEqual(app.next_update_check,21630)
        self.assertTrue(app.start_update_task.call_args.kwargs['background'])
        with patch('app.time.monotonic',return_value=21629): app.maybe_check_updates()
        self.assertEqual(app.start_update_task.call_count,1)
        with patch('app.time.monotonic',return_value=21630): app.maybe_check_updates()
        self.assertEqual(app.start_update_task.call_count,2)

    def test_demo_busy_closed_and_staged_apps_skip_automatic_checks(self):
        from unittest.mock import patch
        for name,value in [('demo',True),('closed',True),('update_busy',True),('staged_update',{'root':'verified'})]:
            with self.subTest(name=name):
                app=self.app();setattr(app,name,value)
                with patch('app.time.monotonic',return_value=100): app.maybe_check_updates()
                app.start_update_task.assert_not_called()
                self.assertEqual(app.next_update_check,30)

    def test_manual_check_resets_deadline_and_cannot_discard_staged_package(self):
        from unittest.mock import patch
        app=self.app()
        with patch('app.time.monotonic',return_value=500): app.check_updates()
        self.assertEqual(app.next_update_check,22100)
        self.assertFalse(app.start_update_task.call_args.kwargs['background'])
        app.start_update_task.reset_mock();app.staged_update={'root':'verified'}
        app.check_updates()
        app.start_update_task.assert_not_called()

    def test_background_failure_preserves_available_update_without_ui_alert(self):
        import queue
        from unittest.mock import Mock
        app=self.app();app.update_busy=True
        app.update_info={'version':'v9.0.0'};app.update_status='available'
        app.update_results=queue.Queue();app.update_results.put(('auto_failed',None))
        app.tray=Mock()
        app.check_update_results()
        self.assertFalse(app.update_busy)
        self.assertEqual(app.update_info,{'version':'v9.0.0'})
        self.assertEqual(app.update_status,'available')
        app.tray.refresh.assert_not_called()


if __name__=='__main__': unittest.main()
