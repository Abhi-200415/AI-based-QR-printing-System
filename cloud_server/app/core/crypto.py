import os
import struct
import base64
import hashlib
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.core.config import JWT_SECRET
from app.utils.logger import logger

# ==========================================================
# Application-Level Document Encryption (AES-256-GCM)
# ==========================================================
# Envelope Encryption Architecture:
# 1. Master Key (KEK - Key Encryption Key): 256-bit key from MASTER_ENCRYPTION_KEY env var
# 2. Per-File Key (DEK - Data Encryption Key): Unique 256-bit random key per document
# 3. Authenticated Cipher: AES-256-GCM with 96-bit (12-byte) random nonce and 128-bit tag
# 4. Self-Contained Envelope Format:
#    [MAGIC (4B: b'AEP1')] [FILE_NONCE (12B)] [ENC_DEK_LEN (2B)] [ENC_DEK_PAYLOAD (60B)] [CIPHERTEXT + TAG]
# ==========================================================

MAGIC_HEADER = b"AEP1"
NONCE_LENGTH = 12       # 96-bit standard GCM nonce
DEK_LENGTH = 32         # 256-bit AES key
AD_DEK = b"AI_PRINT_DEK" # Associated data for DEK encryption
AD_FILE = b"AI_PRINT_DOC" # Associated data for Document payload


class CryptoSecurityException(Exception):
    """Raised when cryptographic validation, tampering check, or key operation fails."""
    pass


def _get_master_key() -> bytes:
    """
    Retrieves the Master Key Encryption Key (KEK) from the environment.
    Falls back to a SHA-256 hash of JWT_SECRET if explicit MASTER_ENCRYPTION_KEY is not set.
    Always returns a 32-byte (256-bit) binary key.
    """
    raw_key = os.getenv("MASTER_ENCRYPTION_KEY")
    if raw_key:
        # If provided in hex format (64 chars) or base64 (44 chars), decode safely
        if len(raw_key) == 64:
            try:
                return bytes.fromhex(raw_key)
            except ValueError:
                pass
        return hashlib.sha256(raw_key.encode("utf-8")).digest()

    # Fallback to securely derived secret from server secret
    return hashlib.sha256(f"ai-print-master-kek-{JWT_SECRET}".encode("utf-8")).digest()


def encrypt_document(plaintext: bytes) -> bytes:
    """
    Encrypts customer document bytes using AES-256-GCM envelope encryption.
    Generates a cryptographically random DEK, encrypts DEK with Master Key,
    and encrypts plaintext with the DEK.
    
    Returns:
        Envelope binary bytes containing header, encrypted DEK, and ciphertext.
    """
    if not isinstance(plaintext, bytes):
        raise CryptoSecurityException("Plaintext must be bytes.")

    master_key = _get_master_key()

    # 1. Generate unique random 256-bit DEK and 96-bit nonces
    dek = os.urandom(DEK_LENGTH)
    file_nonce = os.urandom(NONCE_LENGTH)
    dek_nonce = os.urandom(NONCE_LENGTH)

    # 2. Encrypt the DEK with the Master Key (AES-256-GCM)
    master_aesgcm = AESGCM(master_key)
    encrypted_dek_body = master_aesgcm.encrypt(dek_nonce, dek, AD_DEK)
    # Pack dek_nonce (12B) + encrypted_dek_body (32B DEK + 16B tag = 48B) -> total 60B
    encrypted_dek_payload = dek_nonce + encrypted_dek_body

    # 3. Encrypt the plaintext document with the DEK (AES-256-GCM)
    file_aesgcm = AESGCM(dek)
    ciphertext = file_aesgcm.encrypt(file_nonce, plaintext, AD_FILE)

    # 4. Construct envelope
    # Header: MAGIC (4B) + file_nonce (12B) + enc_dek_len (2B uint16) + enc_dek_payload + ciphertext
    enc_dek_len = len(encrypted_dek_payload)
    header = MAGIC_HEADER + file_nonce + struct.pack(">H", enc_dek_len) + encrypted_dek_payload
    
    return header + ciphertext


def decrypt_document(envelope_bytes: bytes, custom_master_key: Optional[bytes] = None) -> bytes:
    """
    Decrypts an AES-256-GCM envelope and recovers the original document plaintext.
    Validates integrity and raises CryptoSecurityException on tampering or invalid key.
    """
    if not isinstance(envelope_bytes, bytes):
        raise CryptoSecurityException("Envelope data must be bytes.")

    min_length = len(MAGIC_HEADER) + NONCE_LENGTH + 2 + 16 + 16
    if len(envelope_bytes) < min_length:
        raise CryptoSecurityException("Encrypted payload is corrupted or too short.")

    # 1. Verify Magic Header
    if not envelope_bytes.startswith(MAGIC_HEADER):
        raise CryptoSecurityException("Invalid ciphertext format or missing encryption header.")

    offset = len(MAGIC_HEADER)

    # 2. Extract File Nonce
    file_nonce = envelope_bytes[offset:offset + NONCE_LENGTH]
    offset += NONCE_LENGTH

    # 3. Extract Encrypted DEK Payload Length & Body
    enc_dek_len = struct.unpack(">H", envelope_bytes[offset:offset + 2])[0]
    offset += 2

    if offset + enc_dek_len > len(envelope_bytes):
        raise CryptoSecurityException("Malformed envelope: invalid DEK payload length.")

    encrypted_dek_payload = envelope_bytes[offset:offset + enc_dek_len]
    offset += enc_dek_len

    if len(encrypted_dek_payload) < NONCE_LENGTH + 16:
        raise CryptoSecurityException("Corrupted DEK payload.")

    dek_nonce = encrypted_dek_payload[:NONCE_LENGTH]
    encrypted_dek_body = encrypted_dek_payload[NONCE_LENGTH:]

    # 4. Decrypt the DEK using Master Key
    master_key = custom_master_key if custom_master_key is not None else _get_master_key()
    try:
        master_aesgcm = AESGCM(master_key)
        dek = master_aesgcm.decrypt(dek_nonce, encrypted_dek_body, AD_DEK)
    except InvalidTag:
        raise CryptoSecurityException("Master key verification failed or DEK payload tampered.")
    except Exception as e:
        raise CryptoSecurityException(f"Failed to decrypt DEK: {e}")

    # 5. Decrypt Document Ciphertext using DEK
    ciphertext = envelope_bytes[offset:]
    try:
        file_aesgcm = AESGCM(dek)
        plaintext = file_aesgcm.decrypt(file_nonce, ciphertext, AD_FILE)
        return plaintext
    except InvalidTag:
        raise CryptoSecurityException("Ciphertext authentication failed! Data has been tampered with.")
    except Exception as e:
        raise CryptoSecurityException(f"Failed to decrypt document payload: {e}")


def is_encrypted_envelope(data: bytes) -> bool:
    """Checks if binary data starts with the AES-256-GCM encryption magic header."""
    return isinstance(data, bytes) and data.startswith(MAGIC_HEADER)
