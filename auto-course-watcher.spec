from PyInstaller.utils.hooks import collect_data_files, collect_submodules


playwright_datas = collect_data_files("playwright")
playwright_hiddenimports = collect_submodules("playwright")

analysis = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=playwright_datas + [("config.json", ".")],
    hiddenimports=playwright_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="自动看课助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
