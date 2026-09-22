"""智能识别接口：批量启动 / 进度查询 / 单张重试"""
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invoice
from ..services import ocr_batch, ocr_service, task_manager

router = APIRouter()

SCOPES = ("pending", "failed", "all")


@router.post("/start")
def start_ocr(scope: str = "pending"):
    """启动批量识别（后台线程）；scope: pending/failed/all"""
    if scope not in SCOPES:
        raise HTTPException(400, "scope 仅支持 pending / failed / all")
    task_id = task_manager.create()
    # 识别任务复用任务管理器，补充识别专用计数器
    t = task_manager.get(task_id)
    t.update(total=0, success=0, failed=0, current="")
    threading.Thread(target=ocr_batch.run_ocr_task, args=(task_id, scope), daemon=True).start()
    return {"task_id": task_id, "scope": scope}


@router.get("/status/{task_id}")
def ocr_status(task_id: str):
    """查询批量识别进度"""
    t = task_manager.get(task_id)
    if not t:
        raise HTTPException(404, "任务不存在或已过期")
    return t


@router.post("/retry/{invoice_id}")
def retry_one(invoice_id: int, db: Session = Depends(get_db)):
    """单张发票重新识别（同步返回结果）"""
    if not ocr_service.is_configured():
        raise HTTPException(400, "未配置百炼 API Key，请先在 .env 中填写 QWEN_API_KEY 后重启服务")
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "发票不存在")
    try:
        fields = ocr_service.recognize_one(db, inv)
        return {"ok": True, "fields": fields}
    except Exception as e:
        raise HTTPException(400, str(e)) from e
