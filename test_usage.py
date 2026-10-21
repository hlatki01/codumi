"""Token totals from usage records, not context-window sizes or repeated chunks."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import compact_tokens
from sessions import Session, Tail, Monitor


def assistant(identity,**usage):
    return {"type":"assistant","message":{"id":identity,"content":[],"usage":usage}}


def encoded(record):
    return (json.dumps(record)+"\n").encode()


class UsageTests(unittest.TestCase):
    def test_claude_sums_input_output_and_cache_once_per_message(self):
        s=Session("one","Claude")
        record=assistant("a",input_tokens=10,output_tokens=2,
                         cache_creation_input_tokens=3,cache_read_input_tokens=5,
                         cache_creation={"ephemeral_5m_input_tokens":3})
        s.apply(record,1)
        s.apply(record,1)
        self.assertEqual(s.tokens,20)
        s.apply(assistant("a",output_tokens=7),2)
        self.assertEqual(s.tokens,25)
        s.apply(record,1)
        self.assertEqual(s.tokens,25)
        s.apply(assistant("b",input_tokens=4,output_tokens=2),3)
        self.assertEqual(s.tokens,31)

    def test_missing_ids_uuid_fallback_and_invalid_usage(self):
        s=Session("one","Claude")
        for record in (None,[],{"type":"assistant","message":[]},
                       assistant([],input_tokens=20),assistant("x"*257,input_tokens=20)):
            s.add_claude_tokens(record)
        self.assertEqual(s.tokens,0)
        record=assistant(None,input_tokens=4,output_tokens=True,cache_read_input_tokens=-1,
                         cache_creation_input_tokens="30",total_tokens=10**1000)
        record["uuid"]="fallback"
        s.apply(record,1)
        s.apply(record,1)
        self.assertEqual(s.tokens,4)

    def test_background_history_scan_deduplicates_overlap_and_keeps_live_state(self):
        with tempfile.TemporaryDirectory() as folder,patch("sessions.LIMIT",1024):
            path=Path(folder)/"session.jsonl"
            records=[{"type":"user","message":{"content":"first"}},
                     assistant("a",input_tokens=10,output_tokens=2,cache_creation_input_tokens=3,cache_read_input_tokens=5)]
            records += [{"type":"progress","data":"x"*100} for _ in range(40)]
            records += [assistant("b",input_tokens=20,output_tokens=4),
                        assistant("c",input_tokens=5,output_tokens=1),
                        {"type":"user","message":{"content":"latest"}}]
            path.write_bytes(b"".join(encoded(r) for r in records))
            tail=Tail(path,"Claude")
            tail.poll()
            self.assertTrue(tail.session.tokens_partial)
            self.assertEqual((tail.session.state,tail.session.prompt),("working","latest"))
            for _ in range(20):
                if not tail.session.tokens_partial:
                    break
                tail.poll()
            self.assertFalse(tail.session.tokens_partial)
            self.assertEqual(tail.session.tokens,50)
            self.assertEqual((tail.session.state,tail.session.prompt),("working","latest"))
            with path.open("ab") as f:
                f.write(encoded(assistant("a",output_tokens=5))*2)
            tail.poll()
            self.assertEqual(tail.session.tokens,53)
            path.write_bytes(encoded(assistant("new",input_tokens=2)))
            tail.poll()
            self.assertEqual(tail.session.tokens,2)
            self.assertFalse(tail.session.tokens_partial)

    def test_snapshots_do_not_share_usage_bookkeeping(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True):
            path=Path(folder)/".claude/projects/project/session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_bytes(encoded(assistant("a",input_tokens=10)))
            monitor=Monitor(folder)
            snapshot=monitor.poll()[0]
            snapshot._claude_usage.clear()
            with path.open("ab") as f:
                f.write(encoded(assistant("a",input_tokens=10,output_tokens=5)))
            self.assertEqual(monitor.poll()[0].tokens,15)

    def test_codex_totals_remain_cumulative(self):
        s=Session("one","Codex")
        for total in (100,100,50,150,True,-5,"200",10**1000):
            s.apply({"type":"token_usage_record","payload":{"thread_token_usage":{"total_tokens":total}}},1)
        self.assertEqual(s.tokens,150)

    def test_compact_display(self):
        for count,expected in [(0,"0"),(42,"42"),(1000,"1K"),(1250,"1.2K"),(128_000,"128K"),
                               (999_999,"999.9K"),(1_000_000,"1M"),(1_299_999,"1.2M"),(2_500_000,"2.5M")]:
            self.assertEqual(compact_tokens(count),expected)


if __name__=="__main__":
    unittest.main()
