from cryptography.fernet import Fernet, InvalidToken

from config.settings import ENCRYPTION_KEY_PATH


def _load_or_create_fernet_key() -> bytes:
    ENCRYPTION_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ENCRYPTION_KEY_PATH.exists():
        key = ENCRYPTION_KEY_PATH.read_bytes().strip()
        if key:
            return key

    key = Fernet.generate_key()
    ENCRYPTION_KEY_PATH.write_bytes(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_fernet_key())


def encrypt_key(raw_key: str) -> str:
    if not raw_key:
        raise ValueError("raw_key is required")
    return _fernet().encrypt(raw_key.encode("utf-8")).decode("utf-8")


def decrypt_key(encrypted_key: str) -> str:
    if not encrypted_key:
        raise ValueError("encrypted_key is required")
    try:
        return _fernet().decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted key") from exc


def mask_key(raw_key: str) -> str:
    suffix = (raw_key or "")[-3:]
    return f"••••••••...{suffix}"


if __name__ == "__main__":
    sample = "test_api_key_abc"
    encrypted = encrypt_key(sample)
    print(f"[KeyManager] Mask: {mask_key(decrypt_key(encrypted))}")
