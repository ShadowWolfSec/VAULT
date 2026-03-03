"""

"""


class VaultError(Exception):
    """خطأ عام في الخزنة"""
    pass


class AuthError(VaultError):
    """خطأ في المصادقة (كلمة مرور خاطئة)"""
    pass


class LockedError(VaultError):
    """الخزنة مقفلة بسبب محاولات فاشلة متكررة"""
    pass
