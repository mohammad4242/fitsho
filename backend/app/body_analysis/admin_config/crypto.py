from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class CredentialEncryptionError(ValueError):
    pass


class CredentialCipher:
    def __init__(self, master_key: SecretStr | str | None) -> None:
        raw_key = master_key.get_secret_value() if isinstance(master_key, SecretStr) else master_key
        if not raw_key:
            raise CredentialEncryptionError("AI credential encryption is not configured")
        try:
            self._fernet = Fernet(raw_key.encode())
        except (TypeError, ValueError) as error:
            raise CredentialEncryptionError("AI credential encryption key is invalid") from error

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except (InvalidToken, ValueError) as error:
            raise CredentialEncryptionError("Stored AI credential cannot be decrypted") from error
