"""Regression checks for the transcript boundary; uses only synthetic data."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sessions import LIMIT, Monitor, Session, Tail


def codex(event, **values):
    return {"type": "event_msg", "payload": {"type": event, **values}}


def line(record):
    return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


class SessionTests(unittest.TestCase):
    def test_codex_lifecycle_and_usage(self):
        s = Session("one", "Codex")
        s.apply(codex("user_message", message="Olá"), 10)
        self.assertEqual((s.state, s.prompt), ("working", "Olá"))
        s.apply({"type": "response_item", "payload": {"type": "function_call", "name": "request_user_input"}}, 11)
        self.assertEqual(s.state, "waiting")
        s.apply(codex("token_count", info={"total_token_usage": {"total_tokens": 123}}), 12)
        s.apply(codex("token_count", info=None), 12)
        self.assertEqual(s.tokens, 123)
        s.apply({"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer"}}, 13)
        self.assertEqual(s.state, "idle")
        self.assertEqual(s.display_state(314), "sleeping")
        self.assertEqual(s.display_state(14), "idle")

    def test_claude_tools_error_and_recovery(self):
        s = Session("two", "Claude")
        s.apply({"type": "user", "cwd": r"D:\Projetos\Olá", "message": {"content": "Teste"}}, 1)
        self.assertEqual(s.project, "Olá")
        s.apply({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "AskUserQuestion"}]}}, 2)
        self.assertEqual(s.state, "waiting")
        s.apply({"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True}]}}, 3)
        self.assertEqual(s.state, "error")
        s.apply({"type": "assistant", "message": {"content": [], "stop_reason": "end_turn"}}, 4)
        self.assertEqual(s.state, "idle")

    def test_partial_utf8_and_invalid_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "one.jsonl"
            payload = line(codex("user_message", message="ação"))
            split = payload.index("ç".encode()) + 1
            path.write_bytes(b"not json\n[]\n" + payload[:split])
            tail = Tail(path, "Codex")
            tail.poll()
            self.assertEqual(tail.session.prompt, "")
            with path.open("ab") as f:
                f.write(payload[split:])
            tail.poll()
            self.assertEqual(tail.session.prompt, "ação")
            count = len(tail.session.events)
            tail.poll()
            self.assertEqual(len(tail.session.events), count)

    def test_truncation_and_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "one.jsonl"
            path.write_bytes(line(codex("user_message", message="long old text")))
            tail = Tail(path, "Codex")
            tail.poll()
            path.write_bytes(line(codex("task_complete")))
            tail.poll()
            self.assertEqual(tail.session.state, "idle")
            other = Path(folder) / "replacement.jsonl"
            other.write_bytes(line(codex("user_message", message="replacement with longer text than before")))
            os.replace(other, path)
            tail.poll()
            self.assertIn("replacement", tail.session.prompt)

    def test_large_initial_tail_and_oversized_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "one.jsonl"
            path.write_bytes(b"x" * (LIMIT + 20) + b"\n" + line(codex("task_started")))
            tail = Tail(path, "Codex")
            tail.poll()
            self.assertEqual(tail.session.state, "working")
            with path.open("ab") as f:
                f.write(b"x" * (LIMIT + 20) + b"\n" + line(codex("task_complete")))
            tail.poll()
            tail.poll()
            self.assertEqual(tail.session.state, "idle")

    def test_discovery_is_read_only_bounded_and_snapshot_isolated(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder) / ".codex/sessions"
            root.mkdir(parents=True)
            for i in range(52):
                (root / f"{i}.jsonl").write_bytes(line(codex("task_started")))
            nested = root / "subagents"
            nested.mkdir()
            (nested / "child.jsonl").write_bytes(line(codex("task_started")))
            originals = {p: p.read_bytes() for p in root.rglob("*.jsonl")}
            monitor = Monitor(folder)
            snapshot = monitor.poll()
            self.assertEqual(len(snapshot), 48)
            snapshot[0].events.clear()
            self.assertTrue(monitor.poll()[0].events)
            self.assertEqual(originals, {p: p.read_bytes() for p in originals})

    def test_invalid_first_record_does_not_block_session(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "one.jsonl"
            invalid = {"type": "event_msg", "payload": {"type": []}}
            path.write_bytes(line(invalid) + line(codex("task_started")))
            tail = Tail(path, "Codex")
            tail.poll()
            self.assertEqual(tail.session.state, "working")

    def test_absent_agent_directories(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Monitor(folder).poll(), [])


if __name__ == "__main__":
    unittest.main()
