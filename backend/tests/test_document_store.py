import hashlib

import pytest

from app.ingestion.document_store import DocumentStore, DocumentStoreError

MASTER_KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
CONTENT = b"ACCOUNT-SECRET-STATEMENT-BODY " * 20


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def store_root(tmp_path):
    return tmp_path / "documents"


@pytest.fixture
def store(store_root):
    return DocumentStore(store_root, MASTER_KEY)


def test_round_trip_returns_original_content(store):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act
    relative = store.save(CONTENT, digest)
    loaded = store.load(relative, digest)

    # Assert
    assert loaded == CONTENT


def test_save_returns_sharded_posix_relative_path_and_creates_file(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act
    relative = store.save(CONTENT, digest)

    # Assert
    assert relative == f"{digest[:2]}/{digest}.bin"
    assert (store_root / digest[:2] / f"{digest}.bin").is_file()


def test_saved_file_on_disk_does_not_contain_plaintext(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act
    relative = store.save(CONTENT, digest)
    blob = (store_root / relative).read_bytes()

    # Assert
    assert CONTENT not in blob
    assert b"ACCOUNT-SECRET" not in blob


def test_each_save_uses_a_fresh_nonce(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act
    relative = store.save(CONTENT, digest)
    first_blob = (store_root / relative).read_bytes()
    store.save(CONTENT, digest)
    second_blob = (store_root / relative).read_bytes()

    # Assert
    assert first_blob[:12] != second_blob[:12]


def test_no_temporary_files_remain_after_save(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act
    store.save(CONTENT, digest)

    # Assert
    shard_entries = sorted(entry.name for entry in (store_root / digest[:2]).iterdir())
    assert shard_entries == [f"{digest}.bin"]


def test_tampered_file_fails_to_load(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)
    relative = store.save(CONTENT, digest)
    path = store_root / relative
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 0x01
    path.write_bytes(bytes(blob))

    # Act / Assert
    with pytest.raises(DocumentStoreError):
        store.load(relative, digest)


def test_wrong_key_fails_to_load_without_leaking_key_material(store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)
    relative = DocumentStore(store_root, MASTER_KEY).save(CONTENT, digest)
    wrong_store = DocumentStore(store_root, OTHER_KEY)

    # Act / Assert
    with pytest.raises(DocumentStoreError) as excinfo:
        wrong_store.load(relative, digest)
    assert OTHER_KEY.hex() not in str(excinfo.value)
    assert MASTER_KEY.hex() not in str(excinfo.value)


def test_wrong_sha_fails_to_load(store):
    # Arrange
    digest = _sha256_hex(CONTENT)
    relative = store.save(CONTENT, digest)
    other_digest = _sha256_hex(b"something else")

    # Act / Assert
    with pytest.raises(DocumentStoreError):
        store.load(relative, other_digest)


def test_missing_document_raises_store_error(store):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act / Assert
    with pytest.raises(DocumentStoreError):
        store.load(f"{digest[:2]}/{digest}.bin", digest)


def test_truncated_document_raises_store_error(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)
    relative = store.save(CONTENT, digest)
    (store_root / relative).write_bytes(b"short")

    # Act / Assert
    with pytest.raises(DocumentStoreError, match="truncated"):
        store.load(relative, digest)


@pytest.mark.parametrize(
    "escaping_path",
    [
        "../escape.bin",
        "aa/../../escape.bin",
        "ab/../../../escape.bin",
    ],
)
def test_path_traversal_is_rejected(store, store_root, escaping_path):
    # Arrange
    digest = _sha256_hex(CONTENT)

    # Act / Assert
    with pytest.raises(ValueError, match="inside the document store"):
        store.load(escaping_path, digest)


def test_absolute_path_outside_root_is_rejected(store, store_root):
    # Arrange
    digest = _sha256_hex(CONTENT)
    outside = store_root.parent / "outside.bin"

    # Act / Assert
    with pytest.raises(ValueError, match="inside the document store"):
        store.load(str(outside), digest)


@pytest.mark.parametrize("bad_key", [b"", bytes(16), bytes(31), bytes(33)])
def test_master_key_must_be_32_bytes(store_root, bad_key):
    # Act / Assert
    with pytest.raises(ValueError, match="32 bytes"):
        DocumentStore(store_root, bad_key)


@pytest.mark.parametrize(
    "bad_sha",
    [
        "",
        "abc",
        "g" * 64,
        _sha256_hex(CONTENT).upper(),
        _sha256_hex(CONTENT)[:63],
        _sha256_hex(CONTENT) + "0",
    ],
)
def test_save_rejects_malformed_sha256_hex(store, bad_sha):
    # Act / Assert
    with pytest.raises(ValueError, match="sha256_hex"):
        store.save(CONTENT, bad_sha)


@pytest.mark.parametrize("bad_sha", ["", "ABC", "z" * 64])
def test_load_rejects_malformed_sha256_hex(store, bad_sha):
    # Act / Assert
    with pytest.raises(ValueError, match="sha256_hex"):
        store.load("aa/aa.bin", bad_sha)


def test_save_rejects_content_that_does_not_match_sha256(store):
    # Act / Assert
    with pytest.raises(ValueError, match="does not match"):
        store.save(b"different bytes", _sha256_hex(CONTENT))
