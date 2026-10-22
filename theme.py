"""
إدارة المظهر (داكن / فاتح / تلقائي)
"""
from constants import C, DARK_C, LIGHT_C


def _system_theme_mode() -> str:
    """كشف مظهر النظام (Windows فقط)"""
    try:
        import winreg
        key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return "light" if int(v) == 1 else "dark"
    except Exception:
        return "dark"


def apply_theme(mode: str):
    """تطبيق الثيم على قاموس الألوان النشط C"""
    m = (mode or "system").lower()
    if m in ("system", "auto"):
        m = _system_theme_mode()
    src = LIGHT_C if m == "light" else DARK_C
    for k, v in src.items():
        C[k] = v
