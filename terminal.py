"""Resolve a live session to its original console; never launch a replacement shell."""
import ctypes as c
from ctypes import wintypes as w
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys

WINDOWS = sys.platform=="win32"
TERMINAL_HOSTS={"windowsterminal.exe","windowsterminalpreview.exe","cmd.exe","powershell.exe",
                "pwsh.exe","conhost.exe","openconsole.exe","wezterm-gui.exe","alacritty.exe","mintty.exe"}


def session_id(key):
    match=re.search(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?:\.jsonl)?$",Path(key).name,re.I)
    return match.group(1).lower() if match else ""


if WINDOWS:
    kernel=c.WinDLL("kernel32",use_last_error=True)
    user=c.WinDLL("user32",use_last_error=True)

    class UniqueProcess(c.Structure):
        _fields_=[("pid",w.DWORD),("started",w.FILETIME)]

    class ProcessInfo(c.Structure):
        _fields_=[("process",UniqueProcess),("name",w.WCHAR*256),("service",w.WCHAR*64),
                  ("kind",c.c_int),("status",w.ULONG),("session",w.DWORD),("restartable",w.BOOL)]

    class ProcessEntry(c.Structure):
        _fields_=[("size",w.DWORD),("usage",w.DWORD),("pid",w.DWORD),
                  ("heap",c.c_size_t),("module",w.DWORD),("threads",w.DWORD),
                  ("parent",w.DWORD),("priority",w.LONG),("flags",w.DWORD),
                  ("name",w.WCHAR*260)]

    EnumWindowProc=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)

    for dll,name,args,result in [
        (kernel,"CreateToolhelp32Snapshot",[w.DWORD,w.DWORD],w.HANDLE),
        (kernel,"Process32FirstW",[w.HANDLE,c.POINTER(ProcessEntry)],w.BOOL),
        (kernel,"Process32NextW",[w.HANDLE,c.POINTER(ProcessEntry)],w.BOOL),
        (user,"EnumWindows",[EnumWindowProc,w.LPARAM],w.BOOL),
        (user,"GetClassNameW",[w.HWND,w.LPWSTR,c.c_int],c.c_int),
        (user,"GetWindowTextW",[w.HWND,w.LPWSTR,c.c_int],c.c_int),
        (user,"GetWindowTextLengthW",[w.HWND],c.c_int),
        (user,"GetWindowLongPtrW",[w.HWND,c.c_int],c.c_ssize_t),
        (kernel,"OpenProcess",[w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
        (kernel,"CloseHandle",[w.HANDLE],w.BOOL),
        (kernel,"GetProcessTimes",[w.HANDLE,*([c.POINTER(w.FILETIME)]*4)],w.BOOL),
        (kernel,"AttachConsole",[w.DWORD],w.BOOL),
        (kernel,"FreeConsole",[],w.BOOL),
        (kernel,"GetConsoleWindow",[],w.HWND),
        (user,"GetAncestor",[w.HWND,w.UINT],w.HWND),
        (user,"GetWindow",[w.HWND,w.UINT],w.HWND),
        (user,"IsWindowVisible",[w.HWND],w.BOOL),
        (user,"IsIconic",[w.HWND],w.BOOL),
        (user,"GetWindowThreadProcessId",[w.HWND,c.POINTER(w.DWORD)],w.DWORD),
        (user,"ShowWindow",[w.HWND,c.c_int],w.BOOL),
        (user,"SetForegroundWindow",[w.HWND],w.BOOL),
    ]:
        api=getattr(dll,name)
        api.argtypes,api.restype=args,result


def filetime(value):
    return value.dwLowDateTime|(value.dwHighDateTime<<32)


def process_start(pid):
    if not WINDOWS or type(pid) is not int or pid<=0:
        return 0
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        return 0
    try:
        times=[w.FILETIME() for _ in range(4)]
        return filetime(times[0]) if kernel.GetProcessTimes(handle,*[c.byref(t) for t in times]) else 0
    finally:
        kernel.CloseHandle(handle)


def process_tree():
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot in (None,c.c_void_p(-1).value):
        return {}
    try:
        entry=ProcessEntry()
        entry.size=c.sizeof(entry)
        processes={}
        present=kernel.Process32FirstW(snapshot,c.byref(entry))
        while present:
            processes[entry.pid]=(entry.parent,entry.name.lower())
            present=kernel.Process32NextW(snapshot,c.byref(entry))
        return processes
    finally:
        kernel.CloseHandle(snapshot)


def process_windows(pid,started):
    windows=[]
    @EnumWindowProc
    def collect(hwnd,_):
        owner=w.DWORD()
        user.GetWindowThreadProcessId(hwnd,c.byref(owner))
        if (owner.value==pid and user.IsWindowVisible(hwnd) and
            not user.GetWindow(hwnd,4) and user.GetWindowTextLengthW(hwnd)>0 and
            not user.GetWindowLongPtrW(hwnd,-20)&0x80):
            windows.append((int(hwnd),pid,started))
        return True
    user.EnumWindows(collect,0)
    return windows if process_start(pid)==started else []


def available_terminals():
    if not WINDOWS:
        return []
    processes=process_tree()
    console_pids=set()
    @EnumWindowProc
    def consoles(hwnd,_):
        name=c.create_unicode_buffer(128)
        user.GetClassNameW(hwnd,name,128)
        if name.value=="ConsoleWindowClass":
            owner=w.DWORD()
            user.GetWindowThreadProcessId(hwnd,c.byref(owner))
            console_pids.add(owner.value)
        return True
    user.EnumWindows(consoles,0)
    choices=[]
    for pid,(_,name) in processes.items():
        if name not in TERMINAL_HOSTS and pid not in console_pids:
            continue
        started=process_start(pid)
        if not started:
            continue
        for target in process_windows(pid,started):
            window_class=c.create_unicode_buffer(128)
            user.GetClassNameW(target[0],window_class,128)
            if name not in TERMINAL_HOSTS and window_class.value!="ConsoleWindowClass":
                continue
            title=c.create_unicode_buffer(512)
            user.GetWindowTextW(target[0],title,512)
            if title.value:
                choices.append((title.value,target))
    return choices


def ancestor_window(pid,started):
    # Pseudoconsole handles may have no visible owner; follow the actual host process.
    processes=process_tree()
    seen=set()
    for _ in range(24):
        if pid in seen or pid not in processes or not started or process_start(pid)!=started:
            return None
        seen.add(pid)
        parent,name=processes[pid]
        if name in TERMINAL_HOSTS:
            windows=process_windows(pid,started)
            if windows:
                return windows[0] if len(windows)==1 else None
        parent_started=process_start(parent)
        if not parent_started or parent_started>started:
            return None
        pid,started=parent,parent_started
    return None


def file_users(path):
    if not WINDOWS or not path.is_file():
        return []
    rm=c.WinDLL("rstrtmgr")
    rm.RmStartSession.argtypes=[c.POINTER(w.DWORD),w.DWORD,w.LPWSTR]
    rm.RmRegisterResources.argtypes=[w.DWORD,w.UINT,c.POINTER(w.LPCWSTR),w.UINT,c.POINTER(UniqueProcess),w.UINT,c.POINTER(w.LPCWSTR)]
    rm.RmGetList.argtypes=[w.DWORD,c.POINTER(w.UINT),c.POINTER(w.UINT),c.POINTER(ProcessInfo),c.POINTER(w.DWORD)]
    rm.RmEndSession.argtypes=[w.DWORD]
    handle=w.DWORD()
    status=rm.RmStartSession(c.byref(handle),0,c.create_unicode_buffer(33))
    if status:
        return []
    try:
        names=(w.LPCWSTR*1)(str(path.resolve()))
        status=rm.RmRegisterResources(handle,1,names,0,None,0,None)
        if status:
            return []
        needed,count,reasons=w.UINT(),w.UINT(),w.DWORD()
        result=rm.RmGetList(handle,c.byref(needed),c.byref(count),None,c.byref(reasons))
        for _ in range(3):
            if result!=234 or not 0<needed.value<=256:
                return []
            count.value=needed.value
            items=(ProcessInfo*count.value)()
            result=rm.RmGetList(handle,c.byref(needed),c.byref(count),items,c.byref(reasons))
            if result==0:
                return [(p.process.pid,filetime(p.process.started)) for p in items[:count.value]]
        return []
    finally:
        rm.RmEndSession(handle)


def session_processes(provider,key,home=None):
    home=Path.home() if home is None else Path(home)
    identity=session_id(key)
    if not identity:
        return []
    if provider=="Claude":
        folder=Path(os.environ.get("CLAUDE_CONFIG_DIR",home/".claude"))/"sessions"
        matches=[]
        for path in list(folder.glob("*.json"))[:256]:
            try:
                if path.stat().st_size>65536:
                    continue
                data=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data,dict) or str(data.get("sessionId","")).lower()!=identity:
                    continue
                pid=data.get("pid")
                started=data.get("procStart")
                if type(pid) is int and isinstance(started,(str,int)) and str(started).isdigit():
                    matches.append((pid,int(started)))
            except (OSError,ValueError,TypeError):
                continue
        return matches
    if provider=="Codex":
        lock=Path(os.environ.get("CODEX_HOME",home/".codex"))/"thread-writer-locks"/(identity+".lock")
        return file_users(lock if lock.is_file() else Path(key))
    return []


def console_window(pid,started):
    """Only called in a disposable helper, preserving the app's console attachment."""
    if process_start(pid)!=started or not started:
        return None
    kernel.FreeConsole()
    if not kernel.AttachConsole(pid):
        return None
    try:
        hwnd=kernel.GetConsoleWindow()
        for _ in range(8):
            if not hwnd:
                return None
            root=user.GetAncestor(hwnd,3)
            if root and user.IsWindowVisible(root):
                owner=w.DWORD()
                user.GetWindowThreadProcessId(root,c.byref(owner))
                created=process_start(owner.value)
                return [int(root),owner.value,created] if created else None
            hwnd=user.GetWindow(hwnd,4)
        return None
    finally:
        kernel.FreeConsole()


def find_terminal(provider,key):
    if not WINDOWS:
        return None
    candidates=session_processes(provider,key)
    targets=set()
    for pid,started in candidates[:8]:
        if not started or process_start(pid)!=started:
            continue
        target=None
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--console",str(pid),str(started)],
                                  capture_output=True,text=True,timeout=3,
                                  creationflags=subprocess.CREATE_NO_WINDOW,check=False)
            candidate=json.loads(result.stdout) if result.returncode==0 else None
            if isinstance(candidate,list) and len(candidate)==3 and all(type(n) is int and n>0 for n in candidate):
                target=tuple(candidate)
        except (OSError,ValueError,subprocess.TimeoutExpired):
            pass
        if target is None:
            target=ancestor_window(pid,started)
        if target:
            targets.add(target)
    if len(targets)!=1:
        logging.warning("Terminal lookup: provider=%s processes=%d visible_targets=%d",provider,len(candidates),len(targets))
    return next(iter(targets)) if len(targets)==1 else None


def valid_target(target):
    if not WINDOWS or not target:
        return False
    hwnd,pid,started=target
    owner=w.DWORD()
    user.GetWindowThreadProcessId(hwnd,c.byref(owner))
    return bool(owner.value==pid and process_start(pid)==started and user.IsWindowVisible(hwnd))


def focus_terminal(target):
    if not valid_target(target):
        return False
    hwnd=target[0]
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd,9)
    return bool(user.SetForegroundWindow(hwnd))


if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--console" and WINDOWS:
        print(json.dumps(console_window(int(sys.argv[2]),int(sys.argv[3]))))
