# PyInstaller 設定：打包成 macOS 的 Meowmentum.app
# 使用方式：bash build_mac.sh（不需要直接執行這個檔案）
VERSION = {}
exec(open("src/version.py").read(), VERSION)

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    datas=[("assets/sprites", "assets/sprites"), ("assets/fonts", "assets/fonts"),
           ("assets/tray.png", "assets")],
    hiddenimports=["EventKit", "Foundation", "objc"],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtWebEngineCore", "PySide6.QtMultimedia"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Meowmentum",
    console=False,
    strip=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Meowmentum", strip=True, upx=False)
app = BUNDLE(
    coll,
    name="Meowmentum.app",
    icon="assets/icon.png",
    bundle_identifier="io.github.tanuki3701.meowmentum",
    info_plist={
        "LSUIElement": True,              # 不顯示 Dock 圖示
        "NSHighResolutionCapable": True,  # Retina 清晰顯示
        "CFBundleShortVersionString": VERSION["VERSION"],
        "CFBundleVersion": VERSION["VERSION"],
        "CFBundleDisplayName": "Meowmentum",
        # 會議提醒（預設關閉）：打開時 macOS 會先問你要不要讓喵動力讀取行事曆
        "NSCalendarsUsageDescription": "Meowmentum reads upcoming events so your cat can remind you before a meeting.",
        "NSCalendarsFullAccessUsageDescription": "Meowmentum reads upcoming events so your cat can remind you before a meeting.",
    },
)
