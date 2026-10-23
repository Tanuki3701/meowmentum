# PyInstaller 設定：打包成 macOS 的 Meowmentum.app
# 使用方式：bash build_mac.sh（不需要直接執行這個檔案）

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    datas=[("assets/sprites", "assets/sprites"), ("assets/fonts", "assets/fonts"),
           ("assets/tray.png", "assets")],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtNetwork", "PySide6.QtQml",
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
        "CFBundleShortVersionString": "4.0.0",
        "CFBundleDisplayName": "Meowmentum",
    },
)
