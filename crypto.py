"""
crypto.py — محرك التشفير
AES-256-GCM + Scrypt + HKDF + HMAC-SHA256
"""
import os
import hmac
import hashlib
import secrets
import struct
import json
import time
from typing import Dict

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
except ImportError:
    raise ImportError("نفّذ: pip install cryptography")

from constants import (
    SCRYPT_N, SCRYPT_R, SCRYPT_P,
    KEY_LEN, SALT_LEN, IV_LEN, PAD_BLOCK, VERSION
)
from exceptions import VaultError, AuthError


# ── مسح آمن ─────────────────────────────────────────────────
def secure_wipe(buf: bytearray):
    """مسح البيانات الحساسة من الذاكرة"""
    for i in range(len(buf)):
        buf[i] = 0


# ── الـ Pepper ──────────────────────────────────────────────
def _pepper() -> bytes:
    p = os.environ.get("VAULT_PEPPER", "")
    return p.encode() if p else b""


# ── اشتقاق المفاتيح ─────────────────────────────────────────
def derive_keys(password, salt: bytes):
    """
    اشتقاق مفتاحَين منفصلَين (تشفير + MAC) باستخدام Scrypt + HKDF
    يقبل password كـ str أو SecureString
    """
    if hasattr(password, 'get'):
        password_str = password.get()
    else:
        password_str = password

    secret = password_str.encode() + _pepper()
    kdf = Scrypt(
        salt=salt, length=KEY_LEN * 2,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
        backend=default_backend()
    )
    raw = kdf.derive(secret)

    enc = HKDF(
        algorithm=hashes.SHA256(), length=KEY_LEN,
        salt=None, info=b"vault-enc-v4",
        backend=default_backend()
    ).derive(raw[:KEY_LEN])

    mac = HKDF(
        algorithm=hashes.SHA256(), length=KEY_LEN,
        salt=None, info=b"vault-mac-v4",
        backend=default_backend()
    ).derive(raw[KEY_LEN:])

    secure_wipe(bytearray(raw))
    return enc, mac


# ── HMAC ────────────────────────────────────────────────────
def compute_hmac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, digestmod=hashlib.sha256).digest()


# ── Padding ─────────────────────────────────────────────────
def pad_data(data: bytes) -> bytes:
    """إضافة padding عشوائي لإخفاء الحجم الحقيقي"""
    mod = len(data) % PAD_BLOCK
    pad = (PAD_BLOCK - mod) if mod else PAD_BLOCK
    return struct.pack(">Q", len(data)) + data + secrets.token_bytes(pad)


def unpad_data(padded: bytes) -> bytes:
    """إزالة الـ padding"""
    n = struct.unpack(">Q", padded[:8])[0]
    return padded[8:8 + n]


# ── تشفير / فك تشفير الخزنة ─────────────────────────────────
def encrypt_vault(password, payload: Dict) -> bytes:
    """تشفير بيانات الخزنة بـ AES-256-GCM"""
    salt = secrets.token_bytes(SALT_LEN)
    enc_key, mac_key = derive_keys(password, salt)
    try:
        iv = secrets.token_bytes(IV_LEN)
        pt = json.dumps(payload, ensure_ascii=False).encode()
        ct = AESGCM(enc_key).encrypt(iv, pad_data(pt), None)
        mac = compute_hmac(mac_key, salt + iv + ct)
        container = {
            "version": VERSION,
            "salt":    salt.hex(),
            "iv":      iv.hex(),
            "ciphertext": ct.hex(),
            "hmac":    mac.hex(),
            "meta":    {"kdf": "scrypt", "n": SCRYPT_N, "ts": int(time.time())}
        }
        return json.dumps(container, ensure_ascii=False).encode()
    finally:
        secure_wipe(bytearray(enc_key))
        secure_wipe(bytearray(mac_key))


def decrypt_vault(password, blob: bytes, verify_integrity: bool = True) -> Dict:
    """فك تشفير الخزنة والتحقق من صحة البيانات"""
    try:
        container = json.loads(blob.decode())
    except Exception as e:
        raise VaultError("الملف تالف") from e

    if container.get("version") != VERSION:
        raise VaultError(f"إصدار غير مدعوم: {container.get('version')}")

    salt = bytes.fromhex(container["salt"])
    iv   = bytes.fromhex(container["iv"])
    ct   = bytes.fromhex(container["ciphertext"])
    mac  = bytes.fromhex(container["hmac"])

    enc_key, mac_key = derive_keys(password, salt)
    try:
        if not hmac.compare_digest(compute_hmac(mac_key, salt + iv + ct), mac):
            raise AuthError("كلمة المرور خاطئة")

        pt = AESGCM(enc_key).decrypt(iv, ct, None)
        decrypted = json.loads(unpad_data(pt).decode())

        if verify_integrity and "accounts" in decrypted:
            for i, acc in enumerate(decrypted.get("accounts", [])):
                if not isinstance(acc, dict) or "id" not in acc or "name" not in acc:
                    raise VaultError(f"بيانات حساب تالفة في الموقع {i}")

        return decrypted
    except AuthError:
        raise
    except Exception:
        raise AuthError("فشل فك التشفير")
    finally:
        secure_wipe(bytearray(enc_key))
        secure_wipe(bytearray(mac_key))
