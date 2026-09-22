"""全局配置：从 .env 加载，缺失项使用默认值"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend 目录
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class Settings:
    def __init__(self):
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{(BASE_DIR / 'data' / 'invoices.db').as_posix()}",
        )
        self.STORAGE_PATH = os.getenv("STORAGE_PATH", str(BASE_DIR / "invoices_files"))
        self.QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
        # OpenAI 兼容接口地址（百炼华北2北京地域；新加坡地域改为 dashscope-intl.aliyuncs.com）
        self.QWEN_BASE_URL = os.getenv(
            "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        # PDF 理解支持模型：qwen3.8-flash（低成本，默认）/ qwen3.8-max（高精度）
        self.QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.8-flash")
        self.ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
        try:
            self.DEFAULT_SYNC_DAYS = int(os.getenv("DEFAULT_SYNC_DAYS", "90"))
        except ValueError:
            self.DEFAULT_SYNC_DAYS = 90
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8000"))


settings = Settings()


def ensure_encryption_key():
    """首次运行自动生成 Fernet 密钥并写回 .env，避免用户手动配置"""
    if settings.ENCRYPTION_KEY:
        return
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    settings.ENCRYPTION_KEY = key
    try:
        with open(ENV_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n# 授权码加密密钥（系统自动生成，请勿删除）\nENCRYPTION_KEY={key}\n")
    except OSError:
        pass
