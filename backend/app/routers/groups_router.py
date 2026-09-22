"""归类分组接口（阶段三）

按销售方 / 购买方对识别成功的发票分组，返回每组数量、金额合计与组内发票，
同时为前端筛选器提供「开票对象」下拉数据来源。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invoice
from .invoice_router import _to_dict

router = APIRouter()


def _group_by(db: Session, column, status: str) -> list[dict]:
    """通用分组：按指定名称列聚合（名称为空的归入「未识别」组）"""
    q = db.query(Invoice).filter(Invoice.ocr_status == "success")
    if status in ("unused", "used"):
        q = q.filter(Invoice.status == status)
    rows = q.order_by(Invoice.invoice_date.desc()).all()

    groups: dict = {}
    order: list = []
    for inv in rows:
        key = getattr(inv, column) or "（未识别）"
        if key not in groups:
            groups[key] = {"name": key, "count": 0, "amount_total": 0.0,
                           "date_min": None, "date_max": None, "invoices": []}
            order.append(key)
        g = groups[key]
        g["count"] += 1
        g["amount_total"] = round(g["amount_total"] + (inv.amount_total or 0), 2)
        g["invoices"].append(_to_dict(inv))
        if inv.invoice_date:
            g["date_min"] = min(g["date_min"] or inv.invoice_date, inv.invoice_date)
            g["date_max"] = max(g["date_max"] or inv.invoice_date, inv.invoice_date)
    # 组按金额合计降序，便于优先查看大额对象
    return sorted((groups[k] for k in order), key=lambda g: g["amount_total"], reverse=True)


@router.get("/sellers")
def seller_groups(status: str = "all", db: Session = Depends(get_db)):
    """按销售方分组；status: all/unused/used"""
    return _group_by(db, "seller_name", status)


@router.get("/buyers")
def buyer_groups(status: str = "all", db: Session = Depends(get_db)):
    """按购买方分组；status: all/unused/used"""
    return _group_by(db, "buyer_name", status)


@router.get("/options")
def group_options(db: Session = Depends(get_db)):
    """筛选用：已有的销售方/购买方/类型/类目去重列表"""
    rows = db.query(Invoice).filter(Invoice.ocr_status == "success").all()

    def uniq(attr):
        return sorted({getattr(r, attr) for r in rows if getattr(r, attr)})

    return {
        "sellers": uniq("seller_name"),
        "buyers": uniq("buyer_name"),
        "types": uniq("invoice_type"),
        "categories": uniq("category"),
    }
