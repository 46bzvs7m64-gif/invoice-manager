"""数据库初始化：SQLAlchemy + SQLite"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# SQLite 数据库文件所在目录（不存在则自动创建）
if settings.DATABASE_URL.startswith("sqlite"):
    _db_file = settings.DATABASE_URL.split("///", 1)[-1]
    Path(_db_file).parent.mkdir(parents=True, exist_ok=True)

_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
