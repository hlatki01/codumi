"""Win32 overlay geometry, regions and non-activating window behavior."""
from __future__ import annotations
import ctypes as c
from ctypes import wintypes as w
import sys
import threading

WINDOWS = sys.platform == "win32"
PET_SIZE = 64


def clamp_pet(x, y, area):
    left, top, right, bottom = area
    return max(left + 12, min(x, right - 76)), max(top + 12, min(y, bottom - 76))


def tray_placement(x, y, area, details=False):
    """Prefer left; fall back right at the left edge without leaving the work area."""
    left, top, right, bottom = area
    x, y = clamp_pet(x, y, area)
    width = min(364, right - left - 100)
    height = min(752 if details else 422, bottom - top - 24)
    if x - left - 12 >= width:
        side, tx = "left", x - width
    elif right - x - PET_SIZE - 12 >= width:
        side, tx = "right", x + PET_SIZE
    else:
        x = right - 76
        side, tx = "left", x - width
    ty = max(top + 12, min(y + 32 - height // 2, bottom - height - 12))
    return dict(x=tx, y=ty, width=width, height=height, side=side,
                connector=y + 32 - ty, pet_x=x, pet_y=y)


def circle_contains(x, y, px, py):
    return (px - x - 32) ** 2 + (py - y - 32) ** 2 <= 32 ** 2


def speech_placement(x,y,area,width,height):
    left,top,right,bottom=area
    width=min(width,right-left-24)
    bx=max(left+12,min(x+40-width,right-width-12))
    above=y-height-8>=top+12
    by=y-height-8 if above else y+72
    by=max(top+12,min(by,bottom-height-12))
    tip=max(20,min(x+18-bx,width-20))
    base=max(20,min(tip-14,width-20))
    return dict(x=bx,y=by,width=width,height=height,tip=tip,base=base,above=above)


class Spring:
    def __init__(self):
        self.value = self.velocity = self.target = 0.0

    def step(self, seconds, reduced=False):
        if reduced:
            self.value, self.velocity = self.target, 0.0
            return False
        # Substeps keep the spring stable after a stalled UI frame.
        remaining = min(max(seconds, 0), .1)
        while remaining > 0:
            dt = min(remaining, 1 / 120)
            self.velocity += (400 * (self.target - self.value) - 29 * self.velocity) * dt
            self.value += self.velocity * dt
            remaining -= dt
        moving = abs(self.value - self.target) > .001 or abs(self.velocity) > .01
        if not moving:
            self.value, self.velocity = self.target, 0.0
        return moving


if WINDOWS:
    user = c.WinDLL("user32", use_last_error=True)
    gdi = c.WinDLL("gdi32", use_last_error=True)

    class MonitorInfo(c.Structure):
        _fields_ = [("size", w.DWORD), ("monitor", w.RECT), ("work", w.RECT), ("flags", w.DWORD)]

    for dll, name, args, result in [
        (user, "GetAncestor", [w.HWND, w.UINT], w.HWND),
        (user, "GetWindowLongPtrW", [w.HWND, c.c_int], c.c_ssize_t),
        (user, "SetWindowLongPtrW", [w.HWND, c.c_int, c.c_ssize_t], c.c_ssize_t),
        (user, "SetWindowPos", [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT], w.BOOL),
        (user, "SetWindowRgn", [w.HWND, w.HANDLE, w.BOOL], c.c_int),
        (user, "MonitorFromPoint", [w.POINT, w.DWORD], w.HANDLE),
        (user, "GetMonitorInfoW", [w.HANDLE, c.POINTER(MonitorInfo)], w.BOOL),
        (user, "SystemParametersInfoW", [w.UINT, w.UINT, c.c_void_p, w.UINT], w.BOOL),
        (gdi, "CreateEllipticRgn", [c.c_int] * 4, w.HANDLE),
        (gdi, "CreateRoundRectRgn", [c.c_int] * 6, w.HANDLE),
        (gdi, "CreatePolygonRgn", [c.POINTER(w.POINT), c.c_int, c.c_int], w.HANDLE),
        (gdi, "CombineRgn", [w.HANDLE, w.HANDLE, w.HANDLE, c.c_int], c.c_int),
        (gdi, "DeleteObject", [w.HANDLE], w.BOOL),
        (gdi, "PtInRegion", [w.HANDLE, c.c_int, c.c_int], w.BOOL),
        (user, "GetWindowRgn", [w.HWND, w.HANDLE], c.c_int),
    ]:
        function = getattr(dll, name)
        function.argtypes, function.restype = args, result


def handle(window):
    return user.GetAncestor(window.winfo_id(), 2) if WINDOWS else window.winfo_id()


def work_area(window, x=None, y=None):
    if WINDOWS:
        point = w.POINT(0 if x is None else int(x), 0 if y is None else int(y))
        monitor = user.MonitorFromPoint(point, 1 if x is None else 2)
        info = MonitorInfo()
        info.size = c.sizeof(info)
        if user.GetMonitorInfoW(monitor, c.byref(info)):
            r = info.work
            return r.left, r.top, r.right, r.bottom
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


def reduced_motion():
    enabled = w.BOOL(True)
    if WINDOWS and user.SystemParametersInfoW(0x1042, 0, c.byref(enabled), 0):
        return not enabled.value
    return False


def prepare(window, topmost=True, no_activate=True):
    window.overrideredirect(True)
    window.attributes("-topmost", topmost)
    window.update_idletasks()
    if WINDOWS:
        hwnd = handle(window)
        style = user.GetWindowLongPtrW(hwnd, -20) | 0x80
        style = style | 0x08000000 if no_activate else style & ~0x08000000
        user.SetWindowLongPtrW(hwnd, -20, style & ~0x40000)


def place(window, x, y, width, height):
    window.geometry(f"{width}x{height}")
    if WINDOWS:
        if not user.SetWindowPos(handle(window), None, round(x), round(y), width, height, 0x14):
            raise c.WinError(c.get_last_error())
    else:
        window.geometry(f"{width}x{height}{round(x):+d}{round(y):+d}")


def shape(window, width, height, connector=None, side="left"):
    if not WINDOWS:
        return
    if connector is None:
        region = gdi.CreateEllipticRgn(0, 0, width, height)
    else:
        start, end = (0, width - 12) if side == "left" else (12, width)
        region = gdi.CreateRoundRectRgn(start, 0, end, height, 32, 32)
        points = [(end - 1, connector - 12), (width, connector), (end - 1, connector + 12)] if side == "left" else [
            (start, connector - 12), (0, connector), (start, connector + 12)]
        polygon = gdi.CreatePolygonRgn((w.POINT * 3)(*[w.POINT(x, y) for x, y in points]), 3, 1)
        if not polygon or not region:
            if polygon:
                gdi.DeleteObject(polygon)
            if region:
                gdi.DeleteObject(region)
            raise c.WinError()
        combined = gdi.CombineRgn(region, region, polygon, 2)
        gdi.DeleteObject(polygon)
        if not combined:
            gdi.DeleteObject(region)
            raise c.WinError()
    if not region:
        raise c.WinError()
    if not user.SetWindowRgn(handle(window), region, True):
        gdi.DeleteObject(region)
        raise c.WinError()


def contains(window, px, py):
    x, y = px - window.winfo_x(), py - window.winfo_y()
    if not (0 <= x < window.winfo_width() and 0 <= y < window.winfo_height()):
        return False
    if not WINDOWS:
        return True
    region = gdi.CreateEllipticRgn(0, 0, 1, 1)
    try:
        return bool(user.GetWindowRgn(handle(window), region) and gdi.PtInRegion(region, x, y))
    finally:
        gdi.DeleteObject(region)


def exit_overlay(window):
    """Allow the exit sprite outside the circle without intercepting input."""
    if WINDOWS:
        hwnd = handle(window)
        user.SetWindowLongPtrW(hwnd,-20,user.GetWindowLongPtrW(hwnd,-20)|0x20)
        if not user.SetWindowRgn(hwnd,None,True):
            raise c.WinError()


class GlobalHotkey:
    """Own the hotkey message queue so Tk cannot consume WM_HOTKEY first."""
    def __init__(self):
        self.signal=threading.Event()
        self.thread=None
        self.thread_id=0
        self.registered=False
        self.identity=0x4344
        if WINDOWS:
            user.RegisterHotKey.argtypes=[w.HWND,c.c_int,w.UINT,w.UINT]
            user.RegisterHotKey.restype=w.BOOL
            user.UnregisterHotKey.argtypes=[w.HWND,c.c_int]
            user.PeekMessageW.argtypes=[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT]
            user.GetMessageW.argtypes=[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT]
            user.GetMessageW.restype=c.c_int
            user.PostThreadMessageW.argtypes=[w.DWORD,w.UINT,w.WPARAM,w.LPARAM]

    def set(self,name):
        if not self.close(): return False
        if name=="Off": return True
        choices={"Ctrl+Alt+N":(0x4003,0x4e),"Ctrl+Shift+F12":(0x4006,0x7b),"Ctrl+Alt+Space":(0x4003,0x20)}
        if not WINDOWS or name not in choices: return False
        ready=threading.Event()
        def listen():
            msg=w.MSG()
            try:
                user.PeekMessageW(c.byref(msg),None,0,0,0)
                self.thread_id=c.windll.kernel32.GetCurrentThreadId()
                self.registered=bool(user.RegisterHotKey(None,self.identity,*choices[name]))
                ready.set()
                if not self.registered: return
                while user.GetMessageW(c.byref(msg),None,0,0)>0:
                    if msg.message==0x312 and msg.wParam==self.identity: self.signal.set()
            finally:
                if self.registered: user.UnregisterHotKey(None,self.identity)
                self.registered=False
                ready.set()
        self.thread=threading.Thread(target=listen,daemon=True,name="global-shortcut")
        self.thread.start()
        if not ready.wait(2):
            self.close()
            return False
        return self.registered

    def pressed(self):
        pressed=self.signal.is_set()
        self.signal.clear()
        return pressed

    def close(self):
        if self.thread and self.thread.is_alive() and WINDOWS and self.thread_id:
            user.PostThreadMessageW(self.thread_id,0x12,0,0)
            self.thread.join(1)
            if self.thread.is_alive(): return False
        self.thread=None
        self.thread_id=0
        self.registered=False
        self.signal.clear()
        return True


def speech_shape(window,width,height,tip,above,base):
    if not WINDOWS: return
    top,bottom=(0,height-12) if above else (12,height)
    edge=bottom-1 if above else top+1
    point=height if above else 0
    region=gdi.CreateRoundRectRgn(0,top,width,bottom,32,32)
    points=(w.POINT*3)(w.POINT(base-9,edge),w.POINT(tip,point),w.POINT(base+9,edge))
    tail=gdi.CreatePolygonRgn(points,3,1)
    try:
        if not region or not tail or not gdi.CombineRgn(region,region,tail,2): raise c.WinError()
        if not user.SetWindowRgn(handle(window),region,True): raise c.WinError()
        region=None
    finally:
        if region: gdi.DeleteObject(region)
        if tail: gdi.DeleteObject(tail)
