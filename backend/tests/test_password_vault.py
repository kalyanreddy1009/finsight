import fitz
import pytest

from app.ingestion.password_vault import PDFPasswordVault, StatementSecurityAndDriftError

MASTER_KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
USER_PASSWORD = "statement-secret-123"
OWNER_PASSWORD = "owner-secret-456"


def _encrypted_pdf(user_password: str = USER_PASSWORD) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Opening balance 1000.00")
    pdf_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=user_password,
        owner_pw=OWNER_PASSWORD,
    )
    doc.close()
    return pdf_bytes


def _plain_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Plain statement")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_encrypted_password_round_trips_through_vault():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)

    # Act
    encrypted = vault.encrypt_password_rule(USER_PASSWORD)
    decrypted = vault.decrypt_password_rule(encrypted)

    # Assert
    assert decrypted == USER_PASSWORD


def test_two_encryptions_of_same_password_produce_different_ciphertexts():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)

    # Act
    first = vault.encrypt_password_rule(USER_PASSWORD)
    second = vault.encrypt_password_rule(USER_PASSWORD)

    # Assert
    assert first != second
    assert vault.decrypt_password_rule(first) == vault.decrypt_password_rule(second) == USER_PASSWORD


def test_decrypting_with_wrong_key_raises_without_leaking_password():
    # Arrange
    encrypted = PDFPasswordVault(MASTER_KEY).encrypt_password_rule(USER_PASSWORD)
    wrong_key_vault = PDFPasswordVault(OTHER_KEY)

    # Act / Assert
    with pytest.raises(StatementSecurityAndDriftError, match="PASSWORD_RULE_DECRYPTION_FAILED") as exc_info:
        wrong_key_vault.decrypt_password_rule(encrypted)
    assert USER_PASSWORD not in str(exc_info.value)


def test_tampered_ciphertext_raises_decryption_failed():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)
    encrypted = vault.encrypt_password_rule(USER_PASSWORD)
    last_nibble = encrypted[-1]
    tampered = encrypted[:-1] + ("0" if last_nibble != "0" else "1")

    # Act / Assert
    with pytest.raises(StatementSecurityAndDriftError, match="PASSWORD_RULE_DECRYPTION_FAILED"):
        vault.decrypt_password_rule(tampered)


def test_malformed_hex_raises_decryption_failed():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)

    # Act / Assert
    with pytest.raises(StatementSecurityAndDriftError, match="PASSWORD_RULE_DECRYPTION_FAILED"):
        vault.decrypt_password_rule("not-hex-at-all")


def test_master_key_of_wrong_length_raises_value_error():
    # Arrange
    short_key = bytes(16)

    # Act / Assert
    with pytest.raises(ValueError, match="32 bytes"):
        PDFPasswordVault(short_key)


def test_encrypted_pdf_unlocks_with_stored_password_rule():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)
    encrypted_rule = vault.encrypt_password_rule(USER_PASSWORD)

    # Act
    doc = vault.open_and_unlock_pdf(_encrypted_pdf(), encrypted_rule, [])

    # Assert
    assert "Opening balance" in doc[0].get_text()
    doc.close()


def test_encrypted_pdf_unlocks_with_fallback_candidate_when_rule_is_absent():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)

    # Act
    doc = vault.open_and_unlock_pdf(_encrypted_pdf(), None, ["wrong-guess", USER_PASSWORD])

    # Assert
    assert doc.page_count == 1
    doc.close()


def test_unencrypted_pdf_opens_directly_without_any_password():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)

    # Act
    doc = vault.open_and_unlock_pdf(_plain_pdf(), None, [])

    # Assert
    assert doc.is_encrypted is False
    assert doc.page_count == 1
    doc.close()


def test_encrypted_pdf_raises_when_no_password_matches():
    # Arrange
    vault = PDFPasswordVault(MASTER_KEY)
    wrong_rule = vault.encrypt_password_rule("not-the-password")

    # Act / Assert
    with pytest.raises(StatementSecurityAndDriftError, match="PDF_DECRYPTION_FAILED"):
        vault.open_and_unlock_pdf(_encrypted_pdf(), wrong_rule, ["also-wrong"])
