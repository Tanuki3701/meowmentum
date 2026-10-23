"""macOS 專用的小工具（只用 ctypes，不需要額外套件）。

在非 macOS 平台上，所有函式都會安靜地回傳預設值。
"""
import ctypes
import ctypes.util
import os
import sys

IS_MAC = sys.platform == "darwin"

_objc = _cg = _cf = None
if IS_MAC:
    try:
        _objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        _objc.objc_getClass.restype = ctypes.c_void_p
        _objc.objc_getClass.argtypes = [ctypes.c_char_p]
        _objc.sel_registerName.restype = ctypes.c_void_p
        _objc.sel_registerName.argtypes = [ctypes.c_char_p]
        _MSG_SEND = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value
    except Exception:
        _objc = None
    try:
        _cg = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        _cf = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

        _cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        _cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        _cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        _cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]

        class _CGRect(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                        ("w", ctypes.c_double), ("h", ctypes.c_double)]

        _cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
        _cg.CGRectMakeWithDictionaryRepresentation.argtypes = [ctypes.c_void_p, ctypes.POINTER(_CGRect)]
        _cf.CFArrayGetCount.restype = ctypes.c_long
        _cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        _cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        _cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        _cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        _cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _cf.CFNumberGetValue.restype = ctypes.c_bool
        _cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
        _cf.CFRelease.argtypes = [ctypes.c_void_p]

        def _key(name):
            return ctypes.c_void_p.in_dll(_cg, name).value

        _K_NUMBER = _key("kCGWindowNumber")
        _K_PID = _key("kCGWindowOwnerPID")
        _K_LAYER = _key("kCGWindowLayer")
        _K_BOUNDS = _key("kCGWindowBounds")
        _K_ALPHA = _key("kCGWindowAlpha")
    except Exception:
        _cg = _cf = None


def _send(restype, obj, selector, *args):
    """呼叫 Objective-C 方法：objc_msgSend 必須依實際參數型別轉型（arm64 必要）。"""
    argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [type(a) for a in args]
    fn = ctypes.CFUNCTYPE(restype, *argtypes)(_MSG_SEND)
    return fn(obj, _objc.sel_registerName(selector), *args)


def hide_dock_icon():
    """讓程式變成「配件」App：不顯示 Dock 圖示、不搶選單列。"""
    if not _objc:
        return
    try:
        ns_app = _send(ctypes.c_void_p, _objc.objc_getClass(b"NSApplication"),
                       b"sharedApplication")
        _send(ctypes.c_bool, ns_app, b"setActivationPolicy:", ctypes.c_long(1))
    except Exception:
        pass


def show_on_all_spaces(widget):
    """讓視窗出現在所有桌面（Spaces），包含全螢幕 App 旁邊。"""
    if not _objc:
        return
    try:
        ns_view = ctypes.c_void_p(int(widget.winId()))
        ns_window = _send(ctypes.c_void_p, ns_view, b"window")
        if not ns_window:
            return
        # CanJoinAllSpaces | Stationary | IgnoresCycle | FullScreenAuxiliary
        behavior = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8)
        _send(None, ctypes.c_void_p(ns_window), b"setCollectionBehavior:",
              ctypes.c_ulong(behavior))
    except Exception:
        pass


def idle_seconds():
    """距離上次滑鼠／鍵盤操作幾秒；取不到時回傳 None。"""
    if not _cg:
        return None
    try:
        # kCGEventSourceStateCombinedSessionState = 0, kCGAnyInputEventType = ~0
        return _cg.CGEventSourceSecondsSinceLastEventType(0, 0xFFFFFFFF)
    except Exception:
        return None


def _num(d, key, ctype, cf_type):
    ref = _cf.CFDictionaryGetValue(d, key)
    if not ref:
        return None
    out = ctype()
    _cf.CFNumberGetValue(ref, cf_type, ctypes.byref(out))
    return out.value


def list_windows():
    """畫面上其他 App 的一般視窗，由前到後：[(window_id, x, y, w, h), ...]。

    只讀取位置和大小（不讀取視窗名稱或內容），所以不需要「螢幕錄製」權限。
    """
    if not _cg:
        return []
    result = []
    arr = None
    try:
        # kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        arr = _cg.CGWindowListCopyWindowInfo(1 | 16, 0)
        if not arr:
            return []
        my_pid = os.getpid()
        rect = _CGRect()
        for i in range(_cf.CFArrayGetCount(arr)):
            d = _cf.CFArrayGetValueAtIndex(arr, i)
            if _num(d, _K_LAYER, ctypes.c_int32, 3) != 0:      # 只要一般視窗
                continue
            if _num(d, _K_PID, ctypes.c_int32, 3) == my_pid:    # 排除自己
                continue
            alpha = _num(d, _K_ALPHA, ctypes.c_double, 13)
            if alpha is not None and alpha < 0.1:
                continue
            bounds = _cf.CFDictionaryGetValue(d, _K_BOUNDS)
            if not bounds or not _cg.CGRectMakeWithDictionaryRepresentation(bounds, ctypes.byref(rect)):
                continue
            if rect.w < 120 or rect.h < 60:
                continue
            wid = _num(d, _K_NUMBER, ctypes.c_int32, 3)
            result.append((wid, int(rect.x), int(rect.y), int(rect.w), int(rect.h)))
    except Exception:
        return []
    finally:
        if arr:
            _cf.CFRelease(arr)
    return result
