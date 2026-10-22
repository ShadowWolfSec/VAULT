"""
 ثوابت وإعدادات التطبيق
"""

# ════════════════════════════════════════════════════════════
#  إعدادات الأمان
# ════════════════════════════════════════════════════════════
SCRYPT_N        = 2**17      # 128 MB — مقاوم لـ GPU
SCRYPT_R        = 8
SCRYPT_P        = 1
KEY_LEN         = 32
SALT_LEN        = 32
IV_LEN          = 12
PAD_BLOCK       = 4096
VERSION         = 4
# ── مسار بيانات التطبيق ─────────────────────────────────
import sys as _sys, os as _os
from pathlib import Path as _Path

def _data_dir() -> _Path:
    """
    مجلد بيانات التطبيق الدائم:
    Windows  : %LOCALAPPDATA%\\VAULT\\
    Linux/Mac: ~/.local/share/VAULT/
    يبقى ثابتاً بغض النظر عن موقع EXE أو py
    """
    if _os.name == 'nt':
        local = _os.environ.get('LOCALAPPDATA', '')
        base  = _Path(local) if local else (_Path.home() / 'AppData' / 'Local')
    else:
        xdg  = _os.environ.get('XDG_DATA_HOME', '')
        base = _Path(xdg) if xdg else (_Path.home() / '.local' / 'share')
    d = base / 'VAULT'
    d.mkdir(parents=True, exist_ok=True)
    return d

APP_DIR    = str(_data_dir())
VAULT_FILE = str(_data_dir() / 'vault.dat')
MAX_ATTEMPTS    = 5
LOCKOUT_SEC     = 300        # 5 دقائق
SESSION_TIMEOUT = 600        # 10 دقائق (افتراضي)
BACKUP_SUFFIX   = ".bak"

# ════════════════════════════════════════════════════════════
#  ألوان واجهة داكنة احترافية
# ════════════════════════════════════════════════════════════
DARK_C = {
    "bg":          "#0d1117",
    "bg2":         "#161b22",
    "bg3":         "#1c2128",
    "panel":       "#21262d",
    "border":      "#30363d",
    "accent":      "#58a6ff",
    "accent2":     "#3fb950",
    "danger":      "#f85149",
    "warning":     "#e3b341",
    "text":        "#c9d1d9",
    "text_dim":    "#8b949e",
    "text_bright": "#f0f6fc",
    "btn_bg":      "#21262d",
    "btn_hover":   "#30363d",
    "entry_bg":    "#0d1117",
    "select":      "#1f6feb",
}

LIGHT_C = {
    "bg":          "#ffffff",
    "bg2":         "#f3f4f6",
    "bg3":         "#e5e7eb",
    "panel":       "#f9fafb",
    "border":      "#d1d5db",
    "accent":      "#2563eb",
    "accent2":     "#059669",
    "danger":      "#dc2626",
    "warning":     "#d97706",
    "text":        "#111827",
    "text_dim":    "#374151",
    "text_bright": "#111827",
    "btn_bg":      "#f3f4f6",
    "btn_hover":   "#e5e7eb",
    "entry_bg":    "#ffffff",
    "select":      "#2563eb",
}

# الألوان النشطة (قابلة للتعديل بتغيير الثيم)
C = dict(DARK_C)

# ════════════════════════════════════════════════════════════
#  الخطوط
# ════════════════════════════════════════════════════════════
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 14, "bold")
FONT_MONO   = ("Consolas", 10)
FONT_SMALL  = ("Segoe UI", 9)
