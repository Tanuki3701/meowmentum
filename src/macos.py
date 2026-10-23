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


# ---------------- 毛玻璃（NSVisualEffectView）---------------- #
class _NSRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                ("w", ctypes.c_double), ("h", ctypes.c_double)]


class _NSEdgeInsets(ctypes.Structure):
    _fields_ = [("top", ctypes.c_double), ("left", ctypes.c_double),
                ("bottom", ctypes.c_double), ("right", ctypes.c_double)]


GLASS_AVAILABLE = bool(_objc)


def _nsstring(text):
    cls = _objc.objc_getClass(b"NSString")
    return ctypes.c_void_p(_send(ctypes.c_void_p, cls, b"stringWithUTF8String:",
                                 ctypes.c_char_p(text.encode("utf-8"))))


def apply_glass(widget, mask_path, radius):
    """在視窗後面放一層系統毛玻璃（和系統選單同一種材質），回傳是否成功。

    mask_path：圓角遮罩 PNG（用 capInsets 做九宮格延展）。
    """
    if not _objc:
        return False
    try:
        ns_view = ctypes.c_void_p(int(widget.winId()))
        ns_window = _send(ctypes.c_void_p, ns_view, b"window")
        if not ns_window:
            return False
        ns_window = ctypes.c_void_p(ns_window)
        content = ctypes.c_void_p(_send(ctypes.c_void_p, ns_window, b"contentView"))
        frame_view = ctypes.c_void_p(_send(ctypes.c_void_p, content, b"superview"))
        if not frame_view.value:
            return False

        cls = _objc.objc_getClass(b"NSVisualEffectView")
        vev = ctypes.c_void_p(_send(ctypes.c_void_p, cls, b"alloc"))
        rect = _NSRect(0, 0, float(widget.width()), float(widget.height()))
        vev = ctypes.c_void_p(_send(ctypes.c_void_p, vev, b"initWithFrame:", rect))
        _send(None, vev, b"setMaterial:", ctypes.c_long(5))          # Menu
        _send(None, vev, b"setBlendingMode:", ctypes.c_long(0))      # BehindWindow
        _send(None, vev, b"setState:", ctypes.c_long(1))             # Active
        _send(None, vev, b"setAutoresizingMask:", ctypes.c_ulong(18))

        appearance_cls = _objc.objc_getClass(b"NSAppearance")
        light = _send(ctypes.c_void_p, appearance_cls, b"appearanceNamed:",
                      _nsstring("NSAppearanceNameAqua"))
        if light:
            _send(None, vev, b"setAppearance:", ctypes.c_void_p(light))

        img_cls = _objc.objc_getClass(b"NSImage")
        img = ctypes.c_void_p(_send(ctypes.c_void_p, img_cls, b"alloc"))
        img = ctypes.c_void_p(_send(ctypes.c_void_p, img, b"initWithContentsOfFile:",
                                    _nsstring(mask_path)))
        if img.value:
            r = float(radius)
            _send(None, img, b"setCapInsets:", _NSEdgeInsets(r, r, r, r))
            _send(None, vev, b"setMaskImage:", img)

        _send(None, frame_view, b"addSubview:positioned:relativeTo:", vev,
              ctypes.c_long(-1), content)                             # NSWindowBelow
        return True
    except Exception:
        return False


_dock_cache = {"t": -1e9, "info": None}


def dock_info():
    """估算 Dock 的大小（讀 com.apple.dock 偏好設定；不需要任何權限）。

    回傳 dict(orientation, autohide, width)；width 是 Dock 底座的寬度（點）。
    結果快取 20 秒，只有「在 Dock 上走」模式會用到。
    """
    import subprocess
    import time
    now = time.monotonic()
    if now - _dock_cache["t"] < 20 and _dock_cache["info"]:
        return _dock_cache["info"]
    info = {"orientation": "bottom", "autohide": False, "width": None}
    if IS_MAC:
        def read(key):
            try:
                return subprocess.run(["/usr/bin/defaults", "read", "com.apple.dock", key],
                                      capture_output=True, text=True, timeout=2).stdout.strip()
            except Exception:
                return ""
        try:
            tile = float(read("tilesize") or 48)
        except ValueError:
            tile = 48.0
        info["orientation"] = read("orientation") or "bottom"
        info["autohide"] = read("autohide") == "1"
        apps = read("persistent-apps").count("tile-data") + 1          # + Finder
        others = read("persistent-others").count("tile-data") + 1      # + 垃圾桶
        recents = read("recent-apps").count("tile-data") if read("show-recents") != "0" else 0
        seps = 1 + (1 if recents else 0)
        pitch = tile * 1.03
        icons = apps + others + recents
        info["width"] = (icons - 1) * pitch + seps * pitch * 0.8 + tile * 1.1
    _dock_cache.update(t=now, info=info)
    return info
