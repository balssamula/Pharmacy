"""Generate a PBKDF2 password hash for ADMIN_PASSWORD_HASH (no passwords printed)."""
import getpass
import hashlib
import os

password = getpass.getpass("كلمة مرور المدير الجديدة: ")
if len(password) < 12:
    raise SystemExit("اختر كلمة مرور لا تقل عن 12 حرفًا")
confirmation = getpass.getpass("تأكيد كلمة المرور: ")
if password != confirmation:
    raise SystemExit("كلمتا المرور غير متطابقتين")
iterations = 320000
salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
print(f"ADMIN_PASSWORD_HASH=\"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}\"")
