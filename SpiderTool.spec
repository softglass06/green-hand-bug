# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# 把 selenium 整个包（含子模块 + Selenium Manager 驱动管理程序）一起打包，
# 这样勾选界面里的「动态渲染」时才能正常驱动 Edge 浏览器。
selenium_datas, selenium_binaries, selenium_hiddenimports = collect_all('selenium')

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=selenium_binaries,
    datas=selenium_datas,
    # renderer 是本地模块（动态渲染用），显式声明，确保被打包进去
    hiddenimports=['renderer'] + selenium_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SpiderTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
