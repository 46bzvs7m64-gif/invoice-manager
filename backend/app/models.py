"""数据库模型：邮箱配置 / 发票 / 采集日志"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from .database import Base


class EmailAccount(Base):
    """邮箱配置表"""

    __tablename__ = "email_account"

    id = Column(Integer, primary_key=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    imap_host = Column(String(100), nullable=False)
    imap_port = Column(Integer, nullable=False, default=993)
    auth_code = Column(Text, nullable=False)  # Fernet 加密存储
    use_ssl = Column(Boolean, nullable=False, default=True)
    sender_whitelist = Column(Text, default="")  # 逗号分隔的发件人域名白名单
    last_uid = Column(Integer, nullable=False, default=0)  # 增量同步游标：已处理的最大邮件 UID
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Invoice(Base):
    """发票表（阶段一仅填文件与来源字段，OCR 字段由阶段二填充）"""

    __tablename__ = "invoice"

    id = Column(Integer, primary_key=True)
    # ---- 以下字段由阶段二大模型识别后填充 ----
    invoice_no = Column(String(50), index=True)
    invoice_type = Column(String(50))
    invoice_date = Column(String(20))
    amount_total = Column(Float)  # 价税合计
    amount_without_tax = Column(Float)
    tax_amount = Column(Float)
    seller_name = Column(String(200), index=True)
    seller_tax_no = Column(String(50))
    buyer_name = Column(String(200), index=True)
    buyer_tax_no = Column(String(50))
    category = Column(String(50))
    # ---- 文件与来源 ----
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(300), nullable=False)
    file_size = Column(Integer, default=0)
    file_md5 = Column(String(32), index=True)  # 文件去重
    source_email = Column(String(200))
    source_mail_uid = Column(Integer, index=True)
    # ---- 状态 ----
    status = Column(String(20), nullable=False, default="unused")  # unused/used
    used_remark = Column(String(200))
    used_at = Column(DateTime)
    ocr_status = Column(String(20), nullable=False, default="pending")  # pending/success/failed
    ocr_error = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SyncLog(Base):
    """采集日志表"""

    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    total_scanned = Column(Integer, default=0)
    invoices_found = Column(Integer, default=0)
    invoices_downloaded = Column(Integer, default=0)
    invoices_skipped = Column(Integer, default=0)
    invoices_failed = Column(Integer, default=0)
    error_detail = Column(Text)
