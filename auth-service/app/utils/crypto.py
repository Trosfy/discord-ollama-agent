"""Cryptography utilities (bcrypt)"""
import bcrypt


def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        password_bytes = plain_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password)
    except Exception:
        return False
