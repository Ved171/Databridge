from app.core import security


def test_decrypt_credential_falls_back_to_legacy_key(monkeypatch):
    plaintext = '{"host": "db.internal", "port": 5432}'
    current_key = "new-encryption-key-1234567890"
    legacy_key = "change-me-32-char-encryption-key!"

    monkeypatch.setattr(security.settings, "ENCRYPTION_KEY", current_key)
    monkeypatch.setattr(security.settings, "LEGACY_ENCRYPTION_KEY", legacy_key)

    # Encrypt with the legacy key, then ensure decrypt_credential can read it
    ciphertext = security._get_fernet_for_key(legacy_key).encrypt(plaintext.encode()).decode()
    assert security.decrypt_credential(ciphertext) == plaintext
