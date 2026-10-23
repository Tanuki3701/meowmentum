"""macOS 專用的小工具（只用 ctypes，不需要額外套件）。

在非 macOS 平台上，所有函式都會安靜地什麼也不做。
"""
import ctypes
import ctypes.util
import sys

IS_MAC = sys.platform == "darwin"

_objc = None
if IS_MAC:
    try:
        _objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        _objc.objc_getClass.restype = ctypes.c_void_p
        _objc.objc_getClass.argtypes = [ctypes.c_char_p]
        _objc.sel_registerName.restype = ctypes.c_void_p
        _objc.sel_registerName.argtypes = [ctypes.c_char_p]
        _MSG_SEND = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value
    except Exception:  # pragma: no cover - 找不到 objc runtime 就略過
        _objc = None


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
        # NSApplicationActivationPolicyAccessory = 1
        _send(ctypes.c_bool, ns_app, b"setActivationPolicy:", ctypes.c_long(1))
    except Exception:
        pass


def show_on_all_spaces(widget):
    """讓貓咪出現在所有桌面（Spaces），包含全螢幕 App 旁邊。"""
    if not _objc:
        return
    try:
        ns_view = ctypes.c_void_p(int(widget.winId()))
        ns_window = _send(ctypes.c_void_p, ns_view, b"window")
        if not ns_window:
            return
        # CanJoinAllSpaces(1<<0) | Stationary(1<<4) | IgnoresCycle(1<<6) | FullScreenAuxiliary(1<<8)
        behavior = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8)
        _send(None, ctypes.c_void_p(ns_window), b"setCollectionBehavior:",
              ctypes.c_ulong(behavior))
    except Exception:
        pass
