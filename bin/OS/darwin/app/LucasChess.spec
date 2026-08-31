# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Lucas Chess R6 macOS app bundle.

Build it through BuildApp.py rather than calling pyinstaller directly -- that
script also fixes up the engine permissions and signs the bundle, which a bare
pyinstaller run does not do.

Layout note: everything collected lands under sys._MEIPASS, and Code/__init__.py
treats that folder as both bin/ and the folder above it when `frozen` is set. So
`OS/darwin` and `Resources` are shipped at the top of the collected tree, exactly
the two names the source layout uses.
"""

import os

# SPECPATH is bin/OS/darwin/app
DARWIN = os.path.dirname(SPECPATH)            # noqa: F821  (injected by PyInstaller)
BIN = os.path.dirname(os.path.dirname(DARWIN))
ROOT = os.path.dirname(BIN)

VERSION = "6.0.4"

# Files some engines write into their own folder at run time. They must not be
# collected: fractal's chesslog in particular grows without bound, and a stale
# one from a test run would be baked into the bundle.
ENGINE_JUNK_NAMES = {"chesslog", "bug.log"}
ENGINE_JUNK_SUFFIXES = (".log", ".tmp", ".profraw", ".profdata")


def engine_files():
    """Every file under Engines/, one (src, dest_dir) pair each, junk removed."""
    root = os.path.join(DARWIN, "Engines")
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        dest = "OS/darwin/Engines" if rel == "." else os.path.join("OS/darwin/Engines", rel)
        for name in files:
            if name in ENGINE_JUNK_NAMES or name.endswith(ENGINE_JUNK_SUFFIXES):
                continue
            out.append((os.path.join(dirpath, name), dest))
    return out


# The engines and FasterCode, minus the build machinery, which is developer-only.
darwin_data = engine_files() + [
    (os.path.join(DARWIN, "OSEngines.py"), "OS/darwin"),
    (os.path.join(DARWIN, "uci_options.sqlite"), "OS/darwin"),
]
darwin_data += [
    (os.path.join(DARWIN, name), "OS/darwin")
    for name in os.listdir(DARWIN)
    if name.startswith("FasterCode.") and name.endswith(".so")
]

a = Analysis(                                                        # noqa: F821
    [os.path.join(BIN, "LucasR.py")],
    pathex=[BIN, DARWIN],
    binaries=[],
    datas=darwin_data + [(os.path.join(ROOT, "Resources"), "Resources")],
    # Both are imported at runtime from OS/darwin, which Code/__init__.py puts on
    # sys.path; the static analysis cannot see either.
    hiddenimports=["FasterCode", "OSEngines"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtMultimediaWidgets", "PySide6.QtQuick",
              "PySide6.QtQml", "PySide6.QtDesigner", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "matplotlib", "numpy.f2py"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)                                                    # noqa: F821

exe = EXE(                                                           # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LucasChess",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,      # the app takes .pgn/.lcsb arguments itself
    target_arch=None,          # native: arm64 here, x86_64 on Intel
    codesign_identity=None,    # BuildApp.py signs afterwards
    entitlements_file=None,
)

coll = COLLECT(                                                      # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LucasChess",
)

app = BUNDLE(                                                        # noqa: F821
    coll,
    name="Lucas Chess R6.app",
    icon=os.path.join(SPECPATH, "LucasChess.icns"),                  # noqa: F821
    bundle_identifier="org.lucaschess.r6",
    version=VERSION,
    info_plist={
        "CFBundleName": "Lucas Chess R6",
        "CFBundleDisplayName": "Lucas Chess R6",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.board-games",
        "NSHumanReadableCopyright": "GPL 3.0 - Lucas Monge",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Chess game",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.data"],
                "CFBundleTypeExtensions": ["pgn", "lcdb", "lcsb", "bmt"],
            }
        ],
    },
)
