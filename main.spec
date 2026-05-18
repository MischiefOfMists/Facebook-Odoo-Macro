# -*- mode: python ; coding: utf-8 -*-
import importlib
import os

# Tự động lấy đường dẫn thực tế của webdriver_manager trên máy bro
try:
    wm_spec = importlib.util.find_spec('webdriver_manager')
    if wm_spec and wm_spec.origin:
        # Lấy ra thư mục cha chứa package webdriver_manager
        wm_dir = os.path.dirname(os.path.dirname(wm_spec.origin))
        webdriver_manager_path = os.path.join(wm_dir, 'webdriver_manager')
    else:
        raise ImportError
except Exception:
    # Fallback nếu không tự tìm được (điền đường dẫn mặc định)
    webdriver_manager_path = 'venv/Lib/site-packages/webdriver_manager'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data', 'data'),  # Include your matrix .txt files
        ('core', 'core'),  # Include scraper.py and other logic
        
        # SỬ DỤNG BIẾN TỰ ĐỘNG TÌM ĐƯỜNG DẪN Ở ĐÂY
        (webdriver_manager_path, 'webdriver_manager'),
    ],
    hiddenimports=[
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.edge.webdriver',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.firefox.webdriver',
        'selenium.webdriver.firefox.service',
        'selenium.webdriver.firefox.options',
        'selenium.webdriver.remote.webdriver',
        'webdriver_manager',
        'webdriver_manager.firefox',
        'webdriver_manager.core'
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
    name='FB_Messenger_Macro', 
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # Nhớ giữ True để kiểm tra xem lúc chạy exe có thiếu module gì không nhé bro
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)