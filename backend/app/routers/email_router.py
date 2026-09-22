"""邮箱配置接口"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EmailAccount
from ..schemas import EmailConfigIn, EmailTestIn
from ..services.crypto import decrypt_code, encrypt_code
from ..services.email_client import test_connection

router = APIRouter()


def _to_dict(acc: EmailAccount) -> dict:
    return {
        "id": acc.id,
        "email": acc.email,
        "imap_host": acc.imap_host,
        "imap_port": acc.imap_port,
        "use_ssl": acc.use_ssl,
        "sender_whitelist": acc.sender_whitelist or "",
        "last_uid": acc.last_uid,
        "created_at": acc.created_at.strftime("%Y-%m-%d %H:%M") if acc.created_at else None,
    }


@router.get("")
def list_accounts(db: Session = Depends(get_db)):
    """获取所有邮箱配置（不返回授权码）"""
    return [_to_dict(a) for a in db.query(EmailAccount).order_by(EmailAccount.id).all()]


@router.post("")
def save_account(body: EmailConfigIn, db: Session = Depends(get_db)):
    """新增/更新邮箱配置（按邮箱地址 upsert；更新时授权码留空表示不修改）"""
    acc = db.query(EmailAccount).filter(EmailAccount.email == body.email.strip()).first()
    if acc:
        if body.auth_code.strip():
            acc.auth_code = encrypt_code(body.auth_code.strip())
        acc.imap_host = body.imap_host.strip()
        acc.imap_port = body.imap_port
        acc.use_ssl = body.use_ssl
        acc.sender_whitelist = body.sender_whitelist.strip()
    else:
        if not body.auth_code.strip():
            raise HTTPException(400, "请填写邮箱授权码")
        acc = EmailAccount(
            email=body.email.strip(),
            imap_host=body.imap_host.strip(),
            imap_port=body.imap_port,
            use_ssl=body.use_ssl,
            sender_whitelist=body.sender_whitelist.strip(),
            auth_code=encrypt_code(body.auth_code.strip()),
        )
        db.add(acc)
    db.commit()
    db.refresh(acc)
    return {"ok": True, "id": acc.id, "message": "邮箱配置已保存"}


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.get(EmailAccount, account_id)
    if not acc:
        raise HTTPException(404, "邮箱配置不存在")
    db.delete(acc)
    db.commit()
    return {"ok": True, "message": "已删除"}


@router.post("/test")
def test_account(body: EmailTestIn, db: Session = Depends(get_db)):
    """测试邮箱连接；授权码留空且该邮箱已保存时，使用已保存的授权码"""
    code = body.auth_code.strip()
    if not code:
        acc = db.query(EmailAccount).filter(EmailAccount.email == body.email.strip()).first()
        if acc:
            code = decrypt_code(acc.auth_code)
        else:
            raise HTTPException(400, "请先填写授权码")
    ok, msg = test_connection(
        body.email.strip(), code, body.imap_host.strip(), body.imap_port, body.use_ssl
    )
    return {"ok": ok, "message": msg}
