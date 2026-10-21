"""Read-only original-terminal lookup: identity checks and ambiguity handling."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import terminal

IDENTITY="01234567-89ab-cdef-0123-456789abcdef"


class TerminalTests(unittest.TestCase):
    def test_session_filename_ids(self):
        self.assertEqual(terminal.session_id("rollout-2026-10-20-"+IDENTITY+".jsonl"),IDENTITY)
        self.assertEqual(terminal.session_id(IDENTITY+".jsonl"),IDENTITY)
        self.assertEqual(terminal.session_id("demo-claude"),"")

    def test_registry_matches_exact_session_and_creation_identity(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{"CLAUDE_CONFIG_DIR":folder}):
            registry=Path(folder)/"sessions"
            registry.mkdir()
            good=registry/"123.json"
            good.write_text(json.dumps({"pid":123,"sessionId":IDENTITY,"procStart":"456"}))
            (registry/"9.json").write_text('{"pid":9,"sessionId":"other","procStart":"8"}')
            (registry/"bad.json").write_text("broken")
            before=good.read_bytes()
            self.assertEqual(terminal.session_processes("Claude",IDENTITY+".jsonl"),[(123,456)])
            self.assertEqual(good.read_bytes(),before)

    def test_codex_lock_path(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{"CODEX_HOME":folder}):
            lock=Path(folder)/"thread-writer-locks"/(IDENTITY+".lock")
            lock.parent.mkdir()
            lock.touch()
            with patch.object(terminal,"file_users",return_value=[(12,34)]) as users:
                self.assertEqual(terminal.session_processes("Codex",IDENTITY+".jsonl"),[(12,34)])
                users.assert_called_once_with(lock)

    def test_restart_manager_buffer_and_cleanup(self):
        rm=MagicMock()
        def start(handle,flags,key):
            handle._obj.value=7
            return 0
        def get_list(handle,needed,count,items,reasons):
            needed._obj.value=1
            if items is None:
                return 234
            count._obj.value=1
            items[0].process.pid=123
            items[0].process.started.dwLowDateTime=456
            return 0
        rm.RmStartSession.side_effect=start
        rm.RmRegisterResources.return_value=0
        rm.RmGetList.side_effect=get_list
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"held.lock"
            path.touch()
            with patch.object(terminal.c,"WinDLL",return_value=rm):
                self.assertEqual(terminal.file_users(path),[(123,456)])
            rm.RmEndSession.assert_called_once()
            rm.RmEndSession.reset_mock()
            rm.RmRegisterResources.return_value=5
            with patch.object(terminal.c,"WinDLL",return_value=rm):
                self.assertEqual(terminal.file_users(path),[])
            rm.RmEndSession.assert_called_once()

    def test_hidden_console_uses_original_host_ancestor(self):
        with patch.object(terminal,"session_processes",return_value=[(12,34)]),\
             patch.object(terminal,"process_start",return_value=34),\
             patch.object(terminal.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="null")),\
             patch.object(terminal,"ancestor_window",return_value=(100,56,78)) as fallback:
            self.assertEqual(terminal.find_terminal("Claude",IDENTITY),(100,56,78))
            fallback.assert_called_once_with(12,34)

    def test_nearest_terminal_ancestor_matches_identity(self):
        tree={12:(22,"claude.exe"),22:(32,"powershell.exe"),32:(1,"windowsterminal.exe")}
        with patch.object(terminal,"process_tree",return_value=tree),\
             patch.object(terminal,"process_start",side_effect=lambda pid:{12:30,22:20,32:10}.get(pid,0)),\
             patch.object(terminal,"process_windows",side_effect=lambda pid,started:[(100,pid,started)] if pid==32 else []):
            self.assertEqual(terminal.ancestor_window(12,30),(100,32,10))

    def test_reused_parent_pid_is_not_followed(self):
        with patch.object(terminal,"process_tree",return_value={12:(22,"claude.exe"),22:(0,"windowsterminal.exe")}),\
             patch.object(terminal,"process_start",side_effect=lambda pid:30 if pid==12 else 40),\
             patch.object(terminal,"process_windows") as windows:
            self.assertIsNone(terminal.ancestor_window(12,30))
            windows.assert_not_called()

    def test_multiple_host_windows_require_user_selection(self):
        with patch.object(terminal,"process_tree",return_value={12:(22,"claude.exe"),22:(0,"windowsterminal.exe")}),\
             patch.object(terminal,"process_start",side_effect=lambda pid:30 if pid==12 else 20),\
             patch.object(terminal,"process_windows",return_value=[(100,22,20),(200,22,20)]):
            self.assertIsNone(terminal.ancestor_window(12,30))

    def test_stale_pid_does_not_attach(self):
        with patch.object(terminal,"session_processes",return_value=[(12,34)]),\
             patch.object(terminal,"process_start",return_value=99),\
             patch.object(terminal.subprocess,"run") as run:
            self.assertIsNone(terminal.find_terminal("Claude",IDENTITY))
            run.assert_not_called()

    def test_ambiguous_or_invalid_console_results_are_not_focused(self):
        with patch.object(terminal,"session_processes",return_value=[(12,34),(56,34)]),\
             patch.object(terminal,"process_start",return_value=34),\
             patch.object(terminal.subprocess,"run",side_effect=[
                 SimpleNamespace(returncode=0,stdout="[100, 12, 34]"),
                 SimpleNamespace(returncode=0,stdout="[200, 56, 34]")]):
            self.assertIsNone(terminal.find_terminal("Codex",IDENTITY))


if __name__=="__main__":
    unittest.main()
