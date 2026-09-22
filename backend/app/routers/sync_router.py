"""发票采集接口"""
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import EmailAccount, SyncLog
from ..schemas import SyncStartIn
from ..services import email_client, task_manager

router = APIRouter()


@router.post("/start")
def start_sync(body: SyncStartIn | None = None, db: Session = Depends(get_db)):
    """启动一键采集（后台线程执行，返回任务 ID 供前端轮询进度）"""
    if db.query(EmailAccount).count() == 0:
        raise HTTPException(400, "请先在「邮箱配置」页保存邮箱配置")
    days = body.days if (body and body.days) else settings.DEFAULT_SYNC_DAYS
    days = max(1, min(days, 365))
    task_id = task_manager.create()
    threading.Thread(target=email_client.run_sync_task, args=(task_id, days), daemon=True).start()
    return {"task_id": task_id, "days": days}


@router.get("/status/{task_id}")
def sync_status(task_id: str):
    """查询采集任务进度与实时日志"""
    t = task_manager.get(task_id)
    if not t:
        raise HTTPException(404, "任务不存在或已过期")
    return t


@router.get("/logs")
def sync_logs(db: Session = Depends(get_db)):
    """查询历史采集日志（最近 20 条）"""
    logs = db.query(SyncLog).order_by(SyncLog.id.desc()).limit(20).all()
    return [
        {
            "id": log.id,
            "started_at": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else "",
            "finished_at": log.finished_at.strftime("%Y-%m-%d %H:%M:%S") if log.finished_at else "",
            "total_scanned": log.total_scanned,
            "invoices_found": log.invoices_found,
            "invoices_downloaded": log.invoices_downloaded,
            "invoices_skipped": log.invoices_skipped,
            "invoices_failed": log.invoices_failed,
            "error_detail": log.error_detail,
        }
        for log in logs
    ]
