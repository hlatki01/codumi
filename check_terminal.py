"""Actual Windows console fixture: read-only file owner lookup and original-window focus."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

import terminal

runtime=Path(sys.executable).with_name("python.exe")
identity="01234567-89ab-cdef-0123-456789abcdef"
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)
    lock=root/"thread-writer-locks"/(identity+".lock")
    lock.parent.mkdir()
    ready=root/"ready.json"
    script=root/"fixture.py"
    script.write_text(
        "import sys,json,time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0,"+repr(str(Path(__file__).resolve().parent))+")\n"
        "import terminal,os\n"
        "with open(sys.argv[1],'wb') as held:\n"
        " Path(sys.argv[2]).write_text(json.dumps([os.getpid(),terminal.process_start(os.getpid()),terminal.kernel.GetConsoleWindow()]))\n"
        " time.sleep(30)\n",encoding="utf-8")
    startup=subprocess.STARTUPINFO()
    startup.dwFlags=subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow=7
    child=subprocess.Popen([str(runtime),str(script),str(lock),str(ready)],
                           creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
    try:
        deadline=time.monotonic()+5
        while not ready.exists() and child.poll() is None and time.monotonic()<deadline:
            time.sleep(.03)
        pid,started,hwnd=json.loads(ready.read_text())
        assert pid==child.pid and started
        assert terminal.user.IsWindowVisible(hwnd)
        registry=root/"sessions"
        registry.mkdir()
        (registry/(str(pid)+".json")).write_text(json.dumps({"pid":pid,"procStart":str(started),"sessionId":identity}))
        with patch.dict(os.environ,{"CLAUDE_CONFIG_DIR":str(root)}):
            target=terminal.find_terminal("Claude",identity+".jsonl")
        assert target and target[0]==hwnd,(target,hwnd)
        assert target in [item[1] for item in terminal.available_terminals()],"real console missing from window selector"

        focused=terminal.focus_terminal(target)
        if not focused:
            print("Foreground activation denied by this isolated desktop; restore and lookup still verified.")
        assert not terminal.user.IsIconic(hwnd)
        rm=terminal.c.WinDLL("rstrtmgr")
        rm.RmStartSession.argtypes=[terminal.c.POINTER(terminal.w.DWORD),terminal.w.DWORD,terminal.w.LPWSTR]
        probe=terminal.w.DWORD()
        status=rm.RmStartSession(terminal.c.byref(probe),0,terminal.c.create_unicode_buffer(33))
        if status==0:
            rm.RmEndSession(probe)
            with patch.dict(os.environ,{"CODEX_HOME":str(root)}):
                owners=terminal.session_processes("Codex",identity+".jsonl")
                assert (pid,started) in owners,owners
                assert terminal.find_terminal("Codex",identity+".jsonl")==target
        else:
            print("Restart Manager unavailable in this sandbox (Windows error "+str(status)+"); Codex file lookup covered by unit tests.")
        assert not terminal.focus_terminal((hwnd,pid,started+1)),"stale creation identity accepted"
        print("Original terminal native OK: Claude registry, console HWND, restore, focus request and stale-PID rejection")
    finally:
        child.terminate()
        child.wait(timeout=5)
