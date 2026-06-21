# -*- mode: python ; coding: utf-8 -*-

import customtkinter

a = Analysis(
    ['accept_dota.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('images/accept_button.png', 'images'),
        ('images/logo_master.png', 'images'),
        ('images/logo_16.png', 'images'),
        ('images/logo_20.png', 'images'),
        ('images/logo_24.png', 'images'),
        ('images/logo_32.png', 'images'),
        ('images/logo_48.png', 'images'),
        ('images/logo_64.png', 'images'),
        ('images/logo_256.png', 'images'),
        ('images/logo.ico', 'images'),
        (customtkinter.__path__[0], 'customtkinter'),
    ],
    hiddenimports=[
        'customtkinter',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
    ],
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
    name='DotaAutoAccept',
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
    icon='images/logo.ico',
)
