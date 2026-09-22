"""批量识别后台任务：筛选待识别发票 → 逐张调用 OCR → 汇总结果"""
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Invoice
from . import ocr_service, task_manager


def _select(db: Session, scope: str):
    """按范围选择发票：pending=从未识别 / failed=识别失败 / all=全部重新识别"""
    q = db.query(Invoice)
    if scope == "pending":
        q = q.filter(Invoice.ocr_status == "pending")
    elif scope == "failed":
        q = q.filter(Invoice.ocr_status == "failed")
    return q.order_by(Invoice.id.asc()).all()


def run_ocr_task(task_id: str, scope: str):
    """批量识别任务入口（后台线程）"""
    db = SessionLocal()
    try:
        if not ocr_service.is_configured():
            task_manager.fail(task_id, "未配置百炼 API Key，请先在 .env 中填写 QWEN_API_KEY 后重启服务")
            return

        rows = _select(db, scope)
        total = len(rows)
        task_manager.progress(
            task_id, total=total, success=0, failed=0, current=""
        )
        if total == 0:
            task_manager.finish(
                task_id,
                {"scanned": 0, "downloaded": 0, "total": 0, "success": 0, "failed": 0},
            )
            task_manager.line(task_id, "没有符合范围的发票需要识别")
            return

        success = failed = 0
        for i, inv in enumerate(rows, 1):
            task_manager.progress(task_id, current=f"{inv.file_name}（{i}/{total}）")
            task_manager.line(task_id, f"识别 {i}/{total}：{inv.file_name}")
            try:
                fields = ocr_service.recognize_one(db, inv)
                success += 1
                task_manager.line(
                    task_id,
                    f"  ✓ {fields.get('seller_name')}  ¥{fields.get('amount_total')}"
                    f"  日期 {fields.get('invoice_date')}",
                )
            except Exception as e:
                failed += 1
                # 失败原因落库，便于前端展示与单张重试
                inv.ocr_status = "failed"
                inv.ocr_error = str(e)
                db.commit()
                task_manager.line(task_id, f"  ✗ 失败：{e}")
            task_manager.progress(task_id, success=success, failed=failed)

        task_manager.finish(
            task_id,
            {
                "scanned": total,
                "downloaded": success,
                "total": total,
                "success": success,
                "failed": failed,
            },
        )
    except Exception as e:
        task_manager.fail(task_id, str(e))
    finally:
        db.close()
