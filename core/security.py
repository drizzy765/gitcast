import os
import re
from pathlib import Path
from cryptography.fernet import Fernet
from config.settings import ENCRYPTION_KEY_PATH
from api.analytics import track

# [Security] module for data protection and sensitive content scanning

def generate_key():
    """Creates a new Fernet key and saves it to ENCRYPTION_KEY_PATH."""
    key = Fernet.generate_key()
    ENCRYPTION_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ENCRYPTION_KEY_PATH, "wb") as key_file:
        key_file.write(key)
    
    # Add to .gitignore if not already present
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            content = f.read()
        if ".secret_key" not in content:
            with open(gitignore_path, "a") as f:
                f.write("\n.secret_key\n")
            print("[Security] Added .secret_key to .gitignore")
    
    return key

def load_key():
    """Loads the existing key or generates a new one."""
    if not ENCRYPTION_KEY_PATH.exists():
        return generate_key()
    with open(ENCRYPTION_KEY_PATH, "rb") as key_file:
        return key_file.read()

def encrypt_file(path: str):
    """Encrypts a file in place using Fernet symmetric encryption."""
    key = load_key()
    f = Fernet(key)
    with open(path, "rb") as file:
        file_data = file.read()
    encrypted_data = f.encrypt(file_data)
    with open(path, "wb") as file:
        file.write(encrypted_data)
    print(f"[Security] Encrypted: {path}")

def decrypt_file(path: str) -> bytes:
    """Decrypts a file and returns the bytes without writing to disk."""
    key = load_key()
    f = Fernet(key)
    with open(path, "rb") as file:
        encrypted_data = file.read()
    return f.decrypt(encrypted_data)

def scan_for_secrets(ocr_text: str) -> dict:
    """
    Scans OCR text for potential sensitive patterns.
    Returns {"clean": bool, "matches": list}
    """
    patterns = [
        r"KEY\s*=\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
        r"TOKEN\s*=\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
        r"SECRET\s*=\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
        r"PASSWORD\s*=\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
        r"Bearer\s+([a-zA-Z0-9_\-\.]{20,})",
        r"sk-[a-zA-Z0-9]{20,}",
        r"pk-[a-zA-Z0-9]{20,}",
        r"[a-fA-F0-9]{32,}", # Long hex strings
    ]
    
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, ocr_text, re.IGNORECASE)
        if found:
            matches.extend(found)
    
    unique_matches = list(set(matches))
    if unique_matches:
        track("sensitive_content_blocked", {"pattern_count": len(unique_matches)})

    return {
        "clean": len(matches) == 0,
        "matches": unique_matches
    }

def delete_capture(screenshot_path: str):
    """Securely deletes a screenshot from disk."""
    try:
        path = Path(screenshot_path)
        if path.exists():
            # Overwrite with random data before deleting (basic secure delete)
            size = path.stat().st_size
            with open(path, "wb") as f:
                f.write(os.urandom(size))
            path.unlink()
            print(f"[Security] Securely deleted: {screenshot_path}")
    except Exception as e:
        print(f"[Security] Error deleting {screenshot_path}: {e}")

if __name__ == "__main__":
    print("=== SECURITY MODULE TEST ===")
    
    # Test encryption/decryption
    test_file = "test_security.png"
    with open(test_file, "wb") as f:
        f.write(b"fake image data")
    
    print("Original data: b'fake image data'")
    encrypt_file(test_file)
    
    try:
        decrypted = decrypt_file(test_file)
        print(f"Decrypted data: {decrypted}")
        assert decrypted == b"fake image data"
        print("Encryption/Decryption test: PASSED")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

    # Test secret scanning
    test_text = "My API key is KEY=sk-1234567890abcdef1234567890 and my token is Bearer some-long-token-string-here"
    scan_results = scan_for_secrets(test_text)
    print(f"Scan results: {scan_results}")
    assert not scan_results["clean"]
    assert len(scan_results["matches"]) >= 2
    print("Secret scanning test: PASSED")
