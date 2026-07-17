"""
storage.py — إدارة الملفات الآمنة
atomic_write | SecureFileManager | النسخ الاحتياطية | التحقق من التكامل
"""
import os
import json
import time
import hashlib
import secrets
import shutil
from pathlib import Path

from exceptions import VaultError


# ════════════════════════════════════════════════════════════
#  كتابة ذرية (atomic write)
# ════════════════════════════════════════════════════════════
def atomic_write(path: Path, data: bytes):
    """
    يكتب الملف عبر ملف مؤقت ثم يعيد تسميته لضمان عدم تلف البيانات
    في حالة انقطاع التيار الكهربائي أو أي خطأ مفاجئ
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            tmp.chmod(0o600)
        except Exception:
            pass
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ════════════════════════════════════════════════════════════
#  مدير الملفات الآمن
# ════════════════════════════════════════════════════════════
class SecureFileManager:
    """إدارة ملفات الخزنة مع نسخ احتياطية وتحقق من التكامل"""

    def __init__(self, vault_path: Path, max_backups: int = 5):
        self.vault_path = vault_path
        self.max_backups = max_backups
        self.backup_dir = vault_path.parent / ".vault_backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.integrity_file = vault_path.with_suffix(".integrity")

    # ── Checksum ────────────────────────────────────────────
    def calculate_checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def verify_integrity(self, file_path: Path) -> tuple:
        """التحقق من تكامل الملف عبر checksum محفوظ مسبقاً"""
        try:
            if not file_path.exists():
                return False, "الملف غير موجود"

            data = file_path.read_bytes()
            calculated = self.calculate_checksum(data)

            if self.integrity_file.exists():
                integrity_data = json.loads(self.integrity_file.read_text())
                stored = integrity_data.get(str(file_path), {}).get("checksum")
                if stored and stored != calculated:
                    return False, "الملف تالف (checksum غير متطابق)"

            return True, calculated
        except Exception as e:
            return False, f"خطأ في التحقق: {e}"

    def save_integrity(self, file_path: Path, checksum: str):
        """حفظ معلومات التكامل"""
        try:
            integrity_data = {}
            if self.integrity_file.exists():
                integrity_data = json.loads(self.integrity_file.read_text())

            integrity_data[str(file_path)] = {
                "checksum":  checksum,
                "timestamp": int(time.time()),
                "size":      file_path.stat().st_size if file_path.exists() else 0
            }
            atomic_write(self.integrity_file, json.dumps(integrity_data).encode())
        except Exception:
            pass  # لا نوقف العملية إذا فشل حفظ التكامل

    # ── النسخ الاحتياطية ────────────────────────────────────
    def create_backup(self) -> Path:
        if not self.vault_path.exists():
            raise VaultError("الملف الرئيسي غير موجود")

        timestamp = time.time_ns()
        backup_name = f"vault_{timestamp}_{secrets.token_hex(4)}.dat"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(self.vault_path, backup_path)
        try:
            backup_path.chmod(0o600)
        except (OSError, PermissionError):
            pass

        checksum = self.calculate_checksum(backup_path.read_bytes())
        self.save_integrity(backup_path, checksum)
        self._cleanup_old_backups()

        return backup_path

    def _cleanup_old_backups(self):
        try:
            backups = sorted(
                self.backup_dir.glob("vault_*.dat"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for backup in backups[self.max_backups:]:
                backup.unlink()
                if self.integrity_file.exists():
                    integrity_data = json.loads(self.integrity_file.read_text())
                    integrity_data.pop(str(backup), None)
                    atomic_write(self.integrity_file, json.dumps(integrity_data).encode())
        except Exception:
            pass

    def atomic_write_with_backup(self, data: bytes) -> Path:
        """كتابة ذرية مع نسخة احتياطية تلقائية"""
        # نسخة من الملف القديم قبل الكتابة (إن وُجد)
        had_existing = self.vault_path.exists()
        if had_existing:
            self.create_backup()

        checksum = self.calculate_checksum(data)
        atomic_write(self.vault_path, data)

        try:
            self.vault_path.chmod(0o600)
        except (OSError, PermissionError):
            pass

        self.save_integrity(self.vault_path, checksum)

        # إذا لم يكن الملف موجوداً من قبل (أول حفظ) — خذ نسخة الآن
        # نستخدم shutil مباشرة بدون atomic_write لتجنب fsync مكرر
        if not had_existing:
            try:
                timestamp = time.time_ns()
                backup_name = f"vault_{timestamp}_{secrets.token_hex(4)}.dat"
                backup_path = self.backup_dir / backup_name
                shutil.copy2(self.vault_path, backup_path)
                try:
                    backup_path.chmod(0o600)
                except (OSError, PermissionError):
                    pass
                self._cleanup_old_backups()
            except Exception:
                pass

        return self.vault_path

    def list_backups(self) -> list:
        backups = []
        for backup in sorted(
            self.backup_dir.glob("vault_*.dat"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            is_valid, checksum = self.verify_integrity(backup)
            backups.append({
                "path":      backup,
                "timestamp": backup.stat().st_mtime,
                "size":      backup.stat().st_size,
                "valid":     is_valid,
                "checksum":  checksum if is_valid else "تالف"
            })
        return backups

    def restore_from_backup(self, backup_path: Path) -> bool:
        try:
            is_valid, _ = self.verify_integrity(backup_path)
            if not is_valid:
                return False

            if self.vault_path.exists():
                self.create_backup()

            shutil.copy2(backup_path, self.vault_path)
            self.vault_path.chmod(0o600)

            is_valid, checksum = self.verify_integrity(self.vault_path)
            if is_valid:
                self.save_integrity(self.vault_path, checksum)
                return True
            return False
        except Exception:
            return False
