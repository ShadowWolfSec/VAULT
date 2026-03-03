import re
import string
import secrets

from constants import C


def gen_password(length=20, upper=True, lower=True, digits=True, symbols=True) -> str:
    pool, req = "", []
    if lower:
        pool += string.ascii_lowercase
        req.append(secrets.choice(string.ascii_lowercase))
    if upper:
        pool += string.ascii_uppercase
        req.append(secrets.choice(string.ascii_uppercase))
    if digits:
        pool += string.digits
        req.append(secrets.choice(string.digits))
    if symbols:
        sym = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        pool += sym
        req.append(secrets.choice(sym))
    if not pool:
        return ""
    rest = [secrets.choice(pool) for _ in range(length - len(req))]
    combined = req + rest
    secrets.SystemRandom().shuffle(combined)
    return "".join(combined)


def pw_strength(pw: str) -> tuple:
    s = 0
    if len(pw) >= 12: s += 20
    if len(pw) >= 16: s += 10
    if len(pw) >= 24: s += 10
    if re.search(r'[a-z]', pw): s += 15
    if re.search(r'[A-Z]', pw): s += 15
    if re.search(r'[0-9]', pw): s += 15
    if re.search(r'[^a-zA-Z0-9]', pw): s += 15
    s = min(s, 100)

    if s < 40:  return s, "strength_weak",   C["danger"]
    if s < 60:  return s, "strength_medium",  C["warning"]
    if s < 80:  return s, "strength_good",    C["accent"]
    return s,   "strength_strong",            C["accent2"]


def pw_strength_icon(score: int) -> str:
    if score < 40:  return "🔴"
    if score < 60:  return "🟡"
    if score < 80:  return "🟢"
    return "💪"


def validate_master_pw(pw: str) -> tuple:
    if len(pw) < 12:
        return False, "يجب أن تكون 12 حرفاً على الأقل"
    if not re.search(r'[A-Z]', pw):
        return False, "يجب أن تحتوي على حرف كبير"
    if not re.search(r'[a-z]', pw):
        return False, "يجب أن تحتوي على حرف صغير"
    if not re.search(r'[0-9]', pw):
        return False, "يجب أن تحتوي على رقم"
    if not re.search(r'[^a-zA-Z0-9]', pw):
        return False, "يجب أن تحتوي على رمز خاص"
    return True, ""


def analyze_vault_security(accounts: list) -> dict:
    weak = []
    pw_map = {}  # pw_hash -> [account_names]

    for acc in accounts:
        pw = acc.get("password", "")
        name = acc.get("name", "?")
        if not pw:
            continue
        score, _, _ = pw_strength(pw)
        if score < 60:
            weak.append(name)
        # تجميع كلمات المرور المتكررة
        if pw not in pw_map:
            pw_map[pw] = []
        pw_map[pw].append(name)

    reused = [names for names in pw_map.values() if len(names) > 1]
    return {"weak": weak, "reused": reused}
