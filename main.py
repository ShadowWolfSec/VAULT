#!/usr/bin/env python3
"""

"""
import sys
import os

# ── إخفاء CMD على Windows وإغلاقه نهائياً ────────────────
if sys.platform == "win32":
    import ctypes
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # إخفاء
    except Exception:
        pass

# ── التحقق من المكتبات ────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    try:
        import tkinter.messagebox as mb
        mb.showerror("مكتبات مفقودة",
                     "نفّذ: pip install cryptography\nثم أعد تشغيل البرنامج")
    except Exception:
        print("خطأ: نفّذ: pip install cryptography")
    sys.exit(1)

try:
    import tkinter as tk
except ImportError:
    print("خطأ: tkinter غير متاح")
    sys.exit(1)

from app import VaultApp


def main():
    try:
        VaultApp()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        try:
            import tkinter.messagebox as mb
            mb.showerror("خطأ غير متوقع", str(e))
        except Exception:
            print(f"خطأ: {e}")
    finally:
        # إغلاق نهائي يضمن إنهاء العملية حتى لو بقيت threads مفتوحة
        os._exit(0)


if __name__ == "__main__":
    main()
