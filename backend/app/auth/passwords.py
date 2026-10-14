"""Password hashing with Argon2id. See docs/decisions/005."""
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

MIN_LENGTH, MAX_LENGTH = 12, 128

# argon2-cffi defaults: 64 MiB of memory, 3 passes, 4 lanes. Slow on purpose.
_hasher = PasswordHash((Argon2Hasher(),))

# Checked when the email is unknown, so a failed login costs the same time whether or not
# the account exists. Otherwise the response time would reveal which emails are registered.
_DUMMY_HASH = _hasher.hash("a dummy password that matches no account")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_hash.startswith("$argon2"):
        _hasher.verify(password, _DUMMY_HASH)  # same work as a real check
        return False
    return _hasher.verify(password, password_hash)