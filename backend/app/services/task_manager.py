"""采集任务内存管理器：记录进度与实时日志，供前端轮询"""
import threading
import uuid
from datetime import datetime

_LOCK = threading.Lock()
TASKS: dict = {}
MAX_TASKS = 50  # 最多保留最近 50 个任务，防止内存无限增长


def create() -> str:
    """创建新任务，返回任务 ID"""
    task_id = uuid.uuid4().hex[:8]
    with _LOCK:
        TASKS[task_id] = {
            "task_id": task_id,
            "status": "running",  # running / done / error
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "error": None,
            "scanned": 0,
            "found": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "lines": [],
        }
        # 清理过期任务
        if len(TASKS) > MAX_TASKS:
            for k in sorted(TASKS.keys())[: len(TASKS) - MAX_TASKS]:
                TASKS.pop(k, None)
    return task_id


def get(task_id: str):
    return TASKS.get(task_id)


def progress(task_id: str, **kw):
    """更新计数器"""
    with _LOCK:
        t = TASKS.get(task_id)
        if t:
            t.update(kw)


def line(task_id: str, msg: str):
    """追加一条实时日志"""
    ts = datetime.now().strftime("%H:%M:%S")
    with _LOCK:
        t = TASKS.get(task_id)
        if t is not None:
            t["lines"].append(f"[{ts}] {msg}")
            if len(t["lines"]) > 200:
                del t["lines"][:100]


def finish(task_id: str, totals: dict):
    """任务正常完成"""
    ts = datetime.now().strftime("%H:%M:%S")
    with _LOCK:
        t = TASKS.get(task_id)
        if t:
            t.update(totals)
            t["status"] = "done"
            t["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t["lines"].append(
                f"[{ts}] 采集完成：扫描 {totals.get('scanned', 0)} 封，"
                f"下载发票 {totals.get('downloaded', 0)} 张"
            )


def fail(task_id: str, err: str):
    """任务失败"""
    ts = datetime.now().strftime("%H:%M:%S")
    with _LOCK:
        t = TASKS.get(task_id)
        if t:
            t["status"] = "error"
            t["error"] = err
            t["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t["lines"].append(f"[{ts}] 采集失败：{err}")
