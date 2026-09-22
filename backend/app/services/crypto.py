"""授权码加解密（Fernet 对称加密）"""
from cryptography.fernet import Fernet, InvalidToken

from ..config import ensure_encryption_key, settings


def _fernet() -> Fernet:
    ensure_encryption_key()
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_code(plain: str) -> str:
    """加密授权码后存库"""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_code(token: str) -> str:
    """解密授权码；密钥变更导致解密失败时给出明确提示"""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError) as e:
        raise ValueError("授权码解密失败：加密密钥已变更，请重新保存邮箱配置") from e
