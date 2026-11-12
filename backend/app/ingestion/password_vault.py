"""PDF password vault: encrypted stored passwords and protected statement unlocking."""

import os

import fitz  # PyMuPDF
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_256_KEY_BYTES = 32
AESGCM_NONCE_BYTES = 12


class StatementSecurityAndDriftError(Exception):
    """Raised when PDF decryption fails or bank column layout drifts."""


class PDFPasswordVault:
    """Decrypts stored account PDF passwords and unlocks protected Indian bank statements."""

    def __init__(self, master_aes_key: bytes):
        if len(master_aes_key) != AES_256_KEY_BYTES:
            raise ValueError("Master key must be exactly 32 bytes for AES-256-GCM.")
        self._aesgcm = AESGCM(master_aes_key)

    def encrypt_password_rule(self, plaintext_password: str) -> str:
        # A fresh random nonce per call: reusing a nonce under the same key breaks AES-GCM.
        nonce = os.urandom(AESGCM_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext_password.encode("utf-8"), None)
        return (nonce + ciphertext).hex()

    def decrypt_password_rule(self, encrypted_hex: str) -> str:
        try:
            raw = bytes.fromhex(encrypted_hex)
            nonce, ciphertext = raw[:AESGCM_NONCE_BYTES], raw[AESGCM_NONCE_BYTES:]
            return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except (ValueError, InvalidTag):
            # Never include the password, key, or cause details in the message.
            raise StatementSecurityAndDriftError(
                "PASSWORD_RULE_DECRYPTION_FAILED: stored password rule could not be decrypted."
            ) from None

    def open_and_unlock_pdf(
        self, pdf_bytes: bytes, encrypted_password_hex: str | None, fallback_candidates: list[str]
    ) -> fitz.Document:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if not doc.is_encrypted:
            return doc

        passwords_to_try: list[str] = []
        if encrypted_password_hex:
            passwords_to_try.append(self.decrypt_password_rule(encrypted_password_hex))
        passwords_to_try.extend(fallback_candidates)

        for candidate in passwords_to_try:
            if doc.authenticate(candidate) > 0:
                return doc

        raise StatementSecurityAndDriftError(
            "PDF_DECRYPTION_FAILED: No configured password unlocked the statement."
        )
