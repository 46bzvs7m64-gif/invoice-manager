"""接口请求模型（Pydantic）"""
from typing import Optional

from pydantic import BaseModel


class EmailConfigIn(BaseModel):
    email: str
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    auth_code: str = ""  # 更新已有配置时留空表示不修改
    sender_whitelist: str = ""


class EmailTestIn(BaseModel):
    email: str
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    auth_code: str = ""  # 为空且该邮箱已保存时，使用已保存的授权码测试


class SyncStartIn(BaseModel):
    days: Optional[int] = None  # 采集最近天数，为空使用系统默认


class InvoiceUpdate(BaseModel):
    """发票字段手动编辑（全部可选，仅更新提交的字段）"""

    invoice_no: Optional[str] = None
    invoice_type: Optional[str] = None
    invoice_date: Optional[str] = None
    amount_total: Optional[float] = None
    amount_without_tax: Optional[float] = None
    tax_amount: Optional[float] = None
    seller_name: Optional[str] = None
    seller_tax_no: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_no: Optional[str] = None
    category: Optional[str] = None


class UseIn(BaseModel):
    """单张标记已使用：使用备注（如报销单号/用途）"""

    remark: Optional[str] = None


class BatchUse(BaseModel):
    """批量标记已使用"""

    ids: list[int]
    remark: Optional[str] = None
