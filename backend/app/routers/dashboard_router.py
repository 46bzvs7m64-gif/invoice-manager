"""仪表盘统计接口（阶段四）

返回整体统计（总数/总金额/未使用）、近 6 个月趋势、开票对象 TOP5、最近采集。
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invoice
from .invoice_router import _to_dict

router = APIRouter()


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    rows = db.query(Invoice).all()

    total_count = len(rows)
    total_amount = round(sum(r.amount_total or 0 for r in rows), 2)
    unused_count = sum(1 for r in rows if r.status == "unused")
    unused_amount = round(sum(r.amount_total or 0 for r in rows if r.status == "unused"), 2)

    # 近 6 个月（含当月）按开票日期统计
    base = datetime.now().replace(day=1)
    months = []
    for i in range(5, -1, -1):
        y, m = base.year, base.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y:04d}-{m:02d}")
    monthly = []
    for m in months:
        mr = [r for r in rows if r.invoice_date and str(r.invoice_date).startswith(m)]
        monthly.append({
            "month": m,
            "count": len(mr),
            "amount": round(sum(r.amount_total or 0 for r in mr), 2),
        })

    # 开票对象 TOP5（识别成功的发票，按销售方金额）
    groups: dict = {}
    for r in rows:
        if r.ocr_status == "success" and r.seller_name:
            g = groups.setdefault(r.seller_name, {"name": r.seller_name, "count": 0, "amount": 0.0})
            g["count"] += 1
            g["amount"] = round(g["amount"] + (r.amount_total or 0), 2)
    top_sellers = sorted(groups.values(), key=lambda g: g["amount"], reverse=True)[:5]

    # 最近采集的 5 张
    recent = [_to_dict(r) for r in sorted(rows, key=lambda r: r.id, reverse=True)[:5]]

    return {
        "total_count": total_count,
        "total_amount": total_amount,
        "unused_count": unused_count,
        "unused_amount": unused_amount,
        "monthly": monthly,
        "top_sellers": top_sellers,
        "recent": recent,
    }
