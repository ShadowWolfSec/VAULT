"""
طبقة الأمان
SecureString | SecureLogger | ErrorHandler | LockManager
"""
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from constants import MAX_ATTEMPTS, LOCKOUT_SEC
from exceptions import VaultError, AuthError, LockedError
from storage import atomic_write


# ════════════════════════════════════════════════════════════
#  إدارة آمنة للسلاسل النصية الحساسة
# ════════════════════════════════════════════════════════════
class SecureString:
    """تخزين كلمات المرور بشكل آمن مع مسح تلقائي من الذاكرة"""

    def __init__(self, data: str):
        self._data = bytearray(data.encode())
        self._wiped = False

    def get(self) -> str:
        if self._wiped:
            raise ValueError("تم مسح القيمة الحساسة")
        return self._data.decode()

    def wipe(self):
        """مسح آمن للبيانات من الذاكرة بيتاً بيتاً"""
        if not self._wiped:
            for i in range(len(self._data)):
                self._data[i] = 0
            self._wiped = True

    def __del__(self):
        try:
            self.wipe()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.wipe()


# ════════════════════════════════════════════════════════════
#  التسجيل الآمن للأحداث
# ════════════════════════════════════════════════════════════
class SecureLogger:
    """مسجل آمن يمنع تسجيل البيانات الحساسة"""

    def __init__(self, log_file: Path = None):
        self.logger = logging.getLogger("vault_security")
        self.logger.setLevel(logging.INFO)
        self.logger.addFilter(self._sensitive_filter)

        if log_file:
            handler = RotatingFileHandler(
                log_file, maxBytes=1024 * 1024, backupCount=3,
                encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)

    def _sensitive_filter(self, record):
        sensitive_words = ['password', 'كلمة المرور', 'token', 'key', 'secret']
        msg = record.getMessage().lower()
        for word in sensitive_words:
            if word in msg:
                record.msg = "[FILTERED]"
                record.args = ()
                break
        return True

    def log_security_event(self, event_type: str, details: str = ""):
        self.logger.info(f"SECURITY: {event_type} - {details}")

    def log_error(self, error_type: str, details: str = ""):
        self.logger.error(f"ERROR: {error_type} - {details}")


# ════════════════════════════════════════════════════════════
#  معالج الأخطاء
# ════════════════════════════════════════════════════════════
class ErrorHandler:
    """معالج أخطاء محسن مع إحصاء الأخطاء"""

    def __init__(self, logger: SecureLogger = None):
        self.logger = logger or SecureLogger()
        self.error_counts = {}

    def handle_vault_error(self, error: Exception, context: str = "") -> tuple:
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        if isinstance(error, AuthError):
            self.logger.log_security_event("AUTH_FAILED", context)
            return "فشل المصادقة", False
        elif isinstance(error, LockedError):
            self.logger.log_security_event("VAULT_LOCKED", context)
            return str(error), False
        elif isinstance(error, VaultError):
            self.logger.log_error("VAULT_ERROR", f"{context}: {str(error)}")
            return str(error), False
        else:
            self.logger.log_error("UNEXPECTED_ERROR", f"{context}: {str(error)}")
            return "حدث خطأ غير متوقع", False

    def handle_file_error(self, error: Exception, file_path: Path) -> tuple:
        if isinstance(error, PermissionError):
            self.logger.log_security_event("PERMISSION_DENIED", str(file_path))
            return "لا توجد صلاحيات الوصول للملف", False
        elif isinstance(error, FileNotFoundError):
            self.logger.log_error("FILE_NOT_FOUND", str(file_path))
            return "الملف غير موجود", False
        elif isinstance(error, OSError):
            self.logger.log_error("OS_ERROR", f"{file_path}: {str(error)}")
            return "خطأ في نظام الملفات", False
        else:
            self.logger.log_error("FILE_ERROR", f"{file_path}: {str(error)}")
            return "خطأ في قراءة/كتابة الملف", False

    def get_error_summary(self) -> dict:
        return dict(self.error_counts)


# ════════════════════════════════════════════════════════════
#  نظام القفل (الحماية من القوة الغاشمة)
# ════════════════════════════════════════════════════════════
class LockManager:
    """
    يمنع هجمات Brute-Force بآليتين:
    1. ملف .lock لحفظ الحالة بين الجلسات
    2. تأخير تصاعدي في الذاكرة — يعمل حتى لو حُذف .lock
       لأن الحذف يحتاج إعادة تشغيل البرنامج، والتأخير
       يبدأ فوراً من أول محاولة في نفس الجلسة
    """

    def __init__(self, vault_path: Path):
        self.lock_file  = vault_path.with_suffix(".lock")
        self.failed     = 0
        self.lock_time  = 0.0
        # تأخير تصاعدي (ثوانٍ) لكل محاولة فاشلة
        self._delays    = [0, 2, 4, 8, 16, 30]
        self._load()

    def _load(self):
        if not self.lock_file.exists():
            return
        try:
            d = json.loads(self.lock_file.read_text())
            self.failed    = d.get("failed", 0)
            self.lock_time = d.get("lock_time", 0.0)
        except Exception:
            self.reset()

    def _save(self):
        try:
            atomic_write(
                self.lock_file,
                json.dumps({
                    "failed":    self.failed,
                    "lock_time": self.lock_time
                }).encode()
            )
        except Exception:
            pass

    def reset(self):
        self.failed    = 0
        self.lock_time = 0.0
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except Exception:
                pass

    def check(self):
        """
        يتحقق من القفل ويُطبق التأخير التصاعدي.
        التأخير يعمل في نفس الجلسة حتى لو حُذف .lock —
        لأن self.failed محفوظ في الذاكرة طوال تشغيل البرنامج.
        """
        # تأخير تصاعدي بناءً على المحاولات في هذه الجلسة
        delay_idx = min(self.failed, len(self._delays) - 1)
        delay     = self._delays[delay_idx]
        if delay > 0:
            time.sleep(delay)

        # قفل كامل بعد MAX_ATTEMPTS
        if self.failed >= MAX_ATTEMPTS:
            rem = LOCKOUT_SEC - (time.time() - self.lock_time)
            if rem > 0:
                raise LockedError(
                    f"🔒 محاولات كثيرة — انتظر {int(rem//60)}د {int(rem%60)}ث"
                )
            self.reset()

    def fail(self):
        self.failed += 1
        if self.failed >= MAX_ATTEMPTS:
            self.lock_time = time.time()
            self._save()
            raise LockedError(
                f"🔒 تم القفل بعد {MAX_ATTEMPTS} محاولات. انتظر {LOCKOUT_SEC//60} دقيقة."
            )
        self._save()
        return MAX_ATTEMPTS - self.failed

    def success(self):
        self.reset()
