"""Encrypted at-rest store for source statement documents.

Each document is one file, `<root>/<first 2 hex chars>/<sha256>.bin`, holding `nonce + ciphertext`.
Content is encrypted with AES-256-GCM; the SHA-256 hex is bound as associated data.
"""

import contextlib
import hashlib
import os
import re
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16
_SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")
_DOCUMENT_SUFFIX = ".bin"
_SHARD_HEX_CHARS = 2


class DocumentStoreError(Exception):
    """Raised when a stored document is missing, truncated, or fails authentication.

    Messages never include key material.
    """


def _require_sha256_hex(value: str) -> None:
    if not isinstance(value, str) or _SHA256_HEX_PATTERN.fullmatch(value) is None:
        raise ValueError("sha256_hex must be 64 lowercase hex characters")


def _write_atomically(target: Path, payload: bytes) -> None:
    file_descriptor, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise


class DocumentStore:
    def __init__(self, root_dir: Path, master_key: bytes) -> None:
        if not isinstance(master_key, bytes) or len(master_key) != KEY_BYTES:
            raise ValueError(f"master_key must be {KEY_BYTES} bytes")
        self._root = Path(root_dir).resolve()
        self._aead = AESGCM(master_key)

    def save(self, content: bytes, sha256_hex: str) -> str:
        """Encrypts and stores content; returns its POSIX-style path relative to the root."""
        _require_sha256_hex(sha256_hex)
        if hashlib.sha256(content).hexdigest() != sha256_hex:
            raise ValueError("content does not match sha256_hex")
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = self._aead.encrypt(nonce, content, sha256_hex.encode("ascii"))
        shard = sha256_hex[:_SHARD_HEX_CHARS]
        directory = self._root / shard
        directory.mkdir(parents=True, exist_ok=True)
        _write_atomically(directory / f"{sha256_hex}{_DOCUMENT_SUFFIX}", nonce + ciphertext)
        return f"{shard}/{sha256_hex}{_DOCUMENT_SUFFIX}"

    def load(self, relative_path: str, sha256_hex: str) -> bytes:
        """Decrypts a stored document and verifies that its plaintext hashes to sha256_hex."""
        _require_sha256_hex(sha256_hex)
        path = self._resolve_inside_root(relative_path)
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise DocumentStoreError("stored document is missing or unreadable") from exc
        if len(blob) < NONCE_BYTES + TAG_BYTES:
            raise DocumentStoreError("stored document is truncated")
        nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
        try:
            plaintext = self._aead.decrypt(nonce, ciphertext, sha256_hex.encode("ascii"))
        except InvalidTag as exc:
            raise DocumentStoreError("stored document failed authentication") from exc
        if hashlib.sha256(plaintext).hexdigest() != sha256_hex:
            raise DocumentStoreError("stored document hash does not match")
        return plaintext

    def _resolve_inside_root(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("relative_path must be a non-empty string")
        candidate = (self._root / relative_path).resolve()
        if candidate == self._root or not candidate.is_relative_to(self._root):
            raise ValueError("relative_path must point inside the document store")
        return candidate
