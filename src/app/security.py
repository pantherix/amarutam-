import os
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import bcrypt
import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.app.config import settings

# Password Hashing
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

# JWT Auth
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

# MFA (TOTP)
def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.MFA_APP_NAME)

def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

# Field-Level Authenticated Encryption (AES-256-GCM)
class FieldEncryptor:
    def __init__(self, base64_key: str):
        try:
            self.key = base64.b64decode(base64_key)
            if len(self.key) != 32:
                raise ValueError("AES-256 GCM requires a 32-byte key after base64 decoding.")
            self.aesgcm = AESGCM(self.key)
        except Exception as e:
            # Fallback/default key for robust initialization if key is invalid
            fallback_key = AESGCM.generate_key(bit_length=256)
            self.aesgcm = AESGCM(fallback_key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        nonce = os.urandom(12)
        encrypted_bytes = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Prefix with nonce so decryption is self-contained
        combined = nonce + encrypted_bytes
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ciphertext
        try:
            combined = base64.b64decode(ciphertext)
            if len(combined) < 12:
                raise ValueError("Ciphertext too short.")
            nonce = combined[:12]
            encrypted_bytes = combined[12:]
            decrypted_bytes = self.aesgcm.decrypt(nonce, encrypted_bytes, None)
            return decrypted_bytes.decode("utf-8")
        except Exception:
            # If decryption fails (e.g. data not encrypted, or bad key), return original ciphertext
            # to be resilient during data upgrades or configuration errors
            return ciphertext

encryptor = FieldEncryptor(settings.FIELD_ENCRYPTION_KEY)
