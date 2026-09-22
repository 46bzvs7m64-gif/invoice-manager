"""邮件采集服务（阶段一核心模块）

流程：连接 IMAP → 服务端按日期粗过滤 → 客户端按主题/发件人过滤 →
下载发票附件（扩展名+魔数+黑名单校验）→ MD5 去重入库 → 推进增量游标
"""
import email
import hashlib
import imaplib
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import EmailAccount, Invoice, SyncLog
from . import task_manager
from .crypto import decrypt_code

# 主题命中任一关键词即视为候选发票邮件（英文不区分大小写）
SUBJECT_KEYWORDS = ["发票", "invoice"]
# 黑名单关键词：主题或文件名命中则跳过（过滤结账单/行程单等非发票文件）
BLACKLIST_KEYWORDS = ["结账单", "对账单", "账单", "行程单", "扣款凭证", "消费明细"]
# 附件扩展名白名单
ALLOWED_EXTS = {".pdf", ".ofd"}

_EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _imap_date(d: datetime) -> str:
    """IMAP SEARCH 日期格式 dd-Mmm-yyyy（月份必须为英文缩写，避免系统本地化干扰）"""
    return f"{d.day:02d}-{_EN_MONTHS[d.month - 1]}-{d.year}"


def _decode_words(s: str) -> str:
    """解码 MIME encoded-word（如 =?gbk?B?...?=）"""
    if not s:
        return ""
    try:
        out = []
        for text, enc in decode_header(s):
            if isinstance(text, bytes):
                out.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(text)
        return "".join(out)
    except Exception:
        return str(s)


def _decode_filename(part) -> str:
    """提取附件文件名（get_filename 已处理 RFC2231，这里再解码 RFC2047）"""
    raw = part.get_filename()
    if not raw:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode("latin-1", errors="replace")
    return _decode_words(str(raw)).strip()


def _connect(account: EmailAccount, auth_code: str):
    """建立 IMAP 连接并登录、选中收件箱（只读模式，不改动邮件标记）"""
    if account.use_ssl:
        imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port, timeout=15)
    else:
        imap = imaplib.IMAP4(account.imap_host, account.imap_port, timeout=15)
    # 163/126 邮箱要求客户端先发送 ID 命令，否则登录后报 Unsafe Login
    try:
        imaplib.Commands["ID"] = ("NONAUTH", "AUTH", "SELECTED")
        imap._simple_command("ID", '("name" "InvoiceManager" "version" "1.0.0")')
    except Exception:
        pass
    imap.login(account.email, auth_code)
    typ, _ = imap.select("INBOX", readonly=True)
    if typ != "OK":
        raise RuntimeError("无法打开收件箱")
    return imap


def test_connection(email_addr: str, auth_code: str, host: str, port: int, use_ssl: bool):
    """测试邮箱连接，返回 (是否成功, 提示信息)"""
    fake = EmailAccount(email=email_addr, imap_host=host, imap_port=port, use_ssl=use_ssl)
    imap = None
    try:
        imap = _connect(fake, auth_code)
        return True, "连接成功：登录验证通过，收件箱可访问"
    except imaplib.IMAP4.error as e:
        return False, f"登录失败：{e}（请确认已在邮箱设置中开启 IMAP 服务并使用授权码登录）"
    except Exception as e:
        return False, f"连接失败：{e}（请检查服务器地址、端口和网络）"
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass


def _mail_date(msg) -> datetime:
    """解析邮件 Date 头，失败则返回当前时间"""
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        return dt.astimezone() if dt else datetime.now()
    except Exception:
        return datetime.now()


def _process_one(db: Session, imap, account: EmailAccount, uid: int, task_id: str, stats: dict):
    """处理单封邮件：过滤 → 下载附件 → 去重入库"""
    # ---- 拉取邮件头 ----
    typ, data = imap.uid("fetch", str(uid), "(BODY.PEEK[HEADER])")
    if typ != "OK" or not data:
        raise RuntimeError("获取邮件头失败")
    header_bytes = None
    for item in data:
        if isinstance(item, tuple):
            header_bytes = item[1]
            break
    if header_bytes is None:
        raise RuntimeError("邮件头内容为空")
    head_msg = email.message_from_bytes(header_bytes)

    subject = _decode_words(head_msg.get("Subject", ""))
    from_raw = head_msg.get("From", "")
    sender_addr = (parseaddr(from_raw)[1] or from_raw).strip()
    sender_domain = sender_addr.rsplit("@", 1)[-1].lower() if "@" in sender_addr else ""

    # ---- 主题黑名单（结账单/行程单等直接排除）----
    if any(b in subject for b in BLACKLIST_KEYWORDS):
        stats["skipped"] += 1
        task_manager.line(task_id, f"跳过（主题命中黑名单）：{subject[:40]}")
        return

    # ---- 候选判定：发件人白名单命中 或 主题关键词命中 ----
    whitelist = [
        w.strip().lower()
        for w in (account.sender_whitelist or "").replace("，", ",").replace("；", ",").replace(" ", ",").split(",")
        if w.strip()
    ]
    subject_hit = any(k.lower() in subject.lower() for k in SUBJECT_KEYWORDS)
    if not (subject_hit or (whitelist and sender_domain in whitelist)):
        stats["skipped"] += 1
        return
    stats["found"] += 1

    # ---- 拉取完整邮件 ----
    typ, data = imap.uid("fetch", str(uid), "(BODY.PEEK[])")
    raw = None
    for item in data or []:
        if isinstance(item, tuple):
            raw = item[1]
            break
    if raw is None:
        raise RuntimeError("获取邮件正文失败")
    msg = email.message_from_bytes(raw)

    d = _mail_date(head_msg)
    date_str = d.strftime("%Y%m%d")
    local_part = sender_addr.split("@")[0] if "@" in sender_addr else "unknown"
    sender_short = re.sub(r"[^\w.-]", "_", local_part)[:30] or "unknown"

    # ---- 遍历附件 ----
    for part in msg.walk():
        fname = _decode_filename(part)
        if not fname:
            continue
        ext = Path(fname).suffix.lower()
        if ext not in ALLOWED_EXTS:
            continue  # 签名图片等无关附件直接忽略
        # 文件名黑名单
        if any(b in fname for b in BLACKLIST_KEYWORDS):
            stats["skipped"] += 1
            task_manager.line(task_id, f"跳过附件（命中黑名单）：{fname}")
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        # 魔数校验：确保是真实 PDF/OFD 文件，而非改名文件
        if ext == ".pdf" and not payload.startswith(b"%PDF-"):
            stats["skipped"] += 1
            task_manager.line(task_id, f"跳过附件（非有效PDF）：{fname}")
            continue
        if ext == ".ofd" and not payload.startswith(b"PK"):
            stats["skipped"] += 1
            task_manager.line(task_id, f"跳过附件（非有效OFD）：{fname}")
            continue
        # MD5 去重：同一文件（含重复采集）只入库一次
        md5 = hashlib.md5(payload).hexdigest()
        if db.query(Invoice).filter(Invoice.file_md5 == md5).first():
            stats["skipped"] += 1
            task_manager.line(task_id, f"跳过附件（重复发票）：{fname}")
            continue

        # ---- 落盘：存储目录/年份/发件人/日期_UID_原文件名 ----
        safe_name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", fname)
        base = f"{date_str}_{uid}_{safe_name}"
        if len(base) > 150:
            base = f"{date_str}_{uid}_{Path(safe_name).stem[:80]}{ext}"
        save_dir = Path(settings.STORAGE_PATH) / str(d.year) / sender_short
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / base
        n = 1
        while file_path.exists():
            file_path = save_dir / f"{date_str}_{uid}_{n}_{safe_name}"
            n += 1
        file_path.write_bytes(payload)

        db.add(Invoice(
            file_path=str(file_path),
            file_name=fname,
            file_size=len(payload),
            file_md5=md5,
            source_email=account.email,
            source_mail_uid=uid,
            status="unused",
            ocr_status="pending",
        ))
        db.commit()
        stats["downloaded"] += 1
        task_manager.line(task_id, f"已下载发票：{fname}（{len(payload) // 1024} KB）")
        task_manager.progress(task_id, **stats)


def _sync_account(db: Session, account: EmailAccount, days: int, task_id: str) -> dict:
    """采集单个邮箱，返回统计"""
    stats = {"scanned": 0, "found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    auth_code = decrypt_code(account.auth_code)
    task_manager.line(task_id, f"── 开始采集 {account.email}（最近 {days} 天）──")
    imap = _connect(account, auth_code)
    try:
        since = _imap_date(datetime.now() - timedelta(days=days))
        typ, data = imap.uid("search", None, f"(SINCE {since} UID {account.last_uid + 1}:*)")
        if typ != "OK":
            raise RuntimeError(f"IMAP SEARCH 失败：{typ}")
        uid_list = [int(u.decode()) for u in (data[0] or b"").split()]
        uid_list = [u for u in uid_list if u > (account.last_uid or 0)]
        task_manager.line(task_id, f"服务端过滤命中 {len(uid_list)} 封邮件待检查")
        for uid in uid_list:
            stats["scanned"] += 1
            try:
                _process_one(db, imap, account, uid, task_id, stats)
            except Exception as e:
                stats["failed"] += 1
                task_manager.line(task_id, f"邮件 UID={uid} 处理失败：{e}")
            # 推进增量游标：处理过的邮件下次不再拉取
            account.last_uid = max(account.last_uid or 0, uid)
            db.commit()
            task_manager.progress(task_id, **stats)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return stats


def run_sync_task(task_id: str, days: int):
    """后台采集任务入口：采集所有已配置邮箱并写入采集日志"""
    db = SessionLocal()
    started = datetime.now()
    try:
        accounts = db.query(EmailAccount).all()
        if not accounts:
            task_manager.fail(task_id, "未配置邮箱，请先保存邮箱配置")
            return
        totals = {"scanned": 0, "found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
        for acc in accounts:
            try:
                r = _sync_account(db, acc, days, task_id)
            except Exception as e:
                task_manager.line(task_id, f"邮箱 {acc.email} 采集异常：{e}")
                r = {"scanned": 0, "found": 0, "downloaded": 0, "skipped": 0, "failed": 1}
            for k in totals:
                totals[k] += r.get(k, 0)
        db.add(SyncLog(
            started_at=started,
            finished_at=datetime.now(),
            total_scanned=totals["scanned"],
            invoices_found=totals["found"],
            invoices_downloaded=totals["downloaded"],
            invoices_skipped=totals["skipped"],
            invoices_failed=totals["failed"],
        ))
        db.commit()
        task_manager.finish(task_id, totals)
    except Exception as e:
        task_manager.fail(task_id, str(e))
    finally:
        db.close()
