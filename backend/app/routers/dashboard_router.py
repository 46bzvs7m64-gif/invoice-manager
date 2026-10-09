"""仪表盘统计接口

汇总指标（总数/总额/税额/可抵扣进项税/报销进度）、近 6 个月趋势（已用/未用堆叠口径）、
发票类型与消费类目分布、开票对象 TOP5、合规异常检测（重复票号/大额票/未来日期/专票缺税额）。
"""
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invoice
from .invoice_router import _to_dict

router = APIRouter()

# 大额发票预警阈值（元，价税合计）
BIG_AMOUNT = 10_000
# 异常明细最多返回条数
DETAIL_LIMIT = 10


def _round(value: float, digits: int = 2) -> float:
    return round(value or 0, digits)


def _is_special(inv: Invoice) -> bool:
    """增值税专用发票（进项可抵扣）；invoice_type 由大模型识别，兼容不同表述"""
    t = inv.invoice_type or ""
    return ("专用" in t) or ("专票" in t)


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    rows = db.query(Invoice).all()
    ok_rows = [r for r in rows if r.ocr_status == "success"]

    # ---------- 总量与税额 ----------
    total_count = len(rows)
    total_amount = _round(sum(r.amount_total or 0 for r in rows))
    net_total = _round(sum(r.amount_without_tax or 0 for r in rows))
    tax_total = _round(sum(r.tax_amount or 0 for r in rows))
    # 专票进项税额可抵扣；专票缺税额时用 价税合计−不含税 兜底，仍缺则按 0 计
    deductible_tax = 0.0
    for r in rows:
        if not _is_special(r):
            continue
        t = r.tax_amount
        if t is None and r.amount_total is not None and r.amount_without_tax is not None:
            t = r.amount_total - r.amount_without_tax
        deductible_tax += t or 0
    deductible_tax = _round(deductible_tax)

    unused = [r for r in rows if r.status == "unused"]
    used = [r for r in rows if r.status == "used"]
    unused_count, used_count = len(unused), len(used)
    unused_amount = _round(sum(r.amount_total or 0 for r in unused))
    used_amount = _round(sum(r.amount_total or 0 for r in used))

    pending_count = sum(1 for r in rows if r.ocr_status == "pending")
    failed_count = sum(1 for r in rows if r.ocr_status == "failed")

    # ---------- 近 6 个月（含当月，按开票日期） ----------
    base = datetime.now().replace(day=1)
    months = []
    for i in range(5, -1, -1):
        y, m = base.year, base.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y:04d}-{m:02d}")
    monthly = []
    for mo in months:
        mr = [r for r in rows if r.invoice_date and str(r.invoice_date).startswith(mo)]
        m_used = [r for r in mr if r.status == "used"]
        m_unused = [r for r in mr if r.status != "used"]
        monthly.append({
            "month": mo,
            "count": len(mr),
            "amount": _round(sum(r.amount_total or 0 for r in mr)),
            "used_amount": _round(sum(r.amount_total or 0 for r in m_used)),
            "unused_amount": _round(sum(r.amount_total or 0 for r in m_unused)),
            "tax": _round(sum(r.tax_amount or 0 for r in mr)),
        })

    # ---------- 开票对象 TOP5 ----------
    groups: dict = {}
    for r in ok_rows:
        if not r.seller_name:
            continue
        g = groups.setdefault(r.seller_name, {"name": r.seller_name, "count": 0, "amount": 0.0})
        g["count"] += 1
        g["amount"] = round(g["amount"] + (r.amount_total or 0), 2)
    top_sellers = sorted(groups.values(), key=lambda g: g["amount"], reverse=True)[:5]

    # ---------- 发票类型分布 ----------
    type_map: dict = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for r in ok_rows:
        key = (r.invoice_type or "未识别类型").strip()
        type_map[key]["count"] += 1
        type_map[key]["amount"] = round(type_map[key]["amount"] + (r.amount_total or 0), 2)
    type_dist = sorted(
        ({"type": k, "count": v["count"], "amount": v["amount"]} for k, v in type_map.items()),
        key=lambda x: x["amount"], reverse=True,
    )

    # ---------- 消费类目分布 ----------
    cat_map: dict = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for r in ok_rows:
        key = (r.category or "未分类").strip() or "未分类"
        cat_map[key]["count"] += 1
        cat_map[key]["amount"] = round(cat_map[key]["amount"] + (r.amount_total or 0), 2)
    category_dist = sorted(
        ({"category": k, "count": v["count"], "amount": v["amount"]} for k, v in cat_map.items()),
        key=lambda x: x["amount"], reverse=True,
    )[:8]

    # ---------- 合规异常检测 ----------
    # 1) 重复发票号码（同号 ≥2 张，跨销售方也提示）
    no_map: dict = defaultdict(list)
    for r in ok_rows:
        if r.invoice_no:
            no_map[r.invoice_no.strip()].append(r)
    duplicates = []
    for no, lst in no_map.items():
        if len(lst) >= 2:
            duplicates.append({
                "invoice_no": no,
                "count": len(lst),
                "amount": _round(sum(x.amount_total or 0 for x in lst)),
                "ids": [x.id for x in lst],
                "sellers": sorted({x.seller_name or "—" for x in lst}),
                "dates": sorted({x.invoice_date or "—" for x in lst}),
            })
    duplicates.sort(key=lambda d: d["amount"], reverse=True)

    # 2) 大额发票（≥ 阈值，按金额倒序）
    big = sorted(
        (r for r in ok_rows if (r.amount_total or 0) >= BIG_AMOUNT),
        key=lambda r: r.amount_total or 0, reverse=True,
    )[:DETAIL_LIMIT]
    big_list = [{
        "id": r.id, "invoice_no": r.invoice_no or "—",
        "seller_name": r.seller_name or "—", "invoice_date": r.invoice_date or "—",
        "amount_total": _round(r.amount_total),
    } for r in big]

    # 3) 开票日期异常（晚于今天 / 无法匹配 YYYY-MM-DD）
    future = []
    for r in ok_rows:
        d = (r.invoice_date or "").strip()
        if not d:
            continue
        try:
            parsed = datetime.strptime(d[:10], "%Y-%m-%d")
        except ValueError:
            future.append(r)
            continue
        if parsed.date() > datetime.now().date():
            future.append(r)
    future_list = [{
        "id": r.id, "invoice_no": r.invoice_no or "—",
        "seller_name": r.seller_name or "—", "invoice_date": r.invoice_date or "—",
        "amount_total": _round(r.amount_total),
    } for r in future[:DETAIL_LIMIT]]

    # 4) 专票缺税额（影响抵扣核算）
    miss_tax = [r for r in ok_rows if _is_special(r) and not r.tax_amount][:DETAIL_LIMIT]
    miss_tax_list = [{
        "id": r.id, "invoice_no": r.invoice_no or "—",
        "seller_name": r.seller_name or "—", "invoice_date": r.invoice_date or "—",
        "amount_total": _round(r.amount_total),
    } for r in miss_tax]

    anomaly_count = len(duplicates) + len(big_list) + len(future_list) + len(miss_tax_list)

    # 最近采集的 5 张
    recent = [_to_dict(r) for r in sorted(rows, key=lambda r: r.id, reverse=True)[:5]]

    return {
        # 总量
        "total_count": total_count,
        "total_amount": total_amount,
        "net_total": net_total,
        "tax_total": tax_total,
        "deductible_tax": deductible_tax,
        "unused_count": unused_count,
        "unused_amount": unused_amount,
        "used_count": used_count,
        "used_amount": used_amount,
        "used_ratio": round(used_count / total_count * 100, 1) if total_count else 0.0,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "anomaly_count": anomaly_count,
        # 图表
        "monthly": monthly,
        "type_dist": type_dist,
        "category_dist": category_dist,
        "top_sellers": top_sellers,
        # 异常
        "duplicates": duplicates[:DETAIL_LIMIT],
        "big_invoices": big_list,
        "future_invoices": future_list,
        "missing_tax": miss_tax_list,
        "recent": recent,
    }
