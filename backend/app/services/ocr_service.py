"""大模型发票识别服务（阶段二核心模块）

调用阿里云百炼 OpenAI 兼容接口：本地 PDF → Base64 data URI → qwen3.8 模型 →
按固定 JSON 结构返回发票字段 → 解析、校验、归一化。

设计约束：
- 零新增第三方依赖，仅用标准库 urllib 发起 HTTP 请求；
- 惰性初始化：不在模块导入期读取密钥或发起网络请求，缺 API Key 时服务照常启动；
- OFD 暂不支持（多模态 PDF 理解仅支持 PDF），返回明确错误，引导手动录入。
"""
import base64
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Invoice

# 期望模型返回的字段键名（与 Invoice 模型字段对应）
FIELD_KEYS = [
    "invoice_no",
    "invoice_type",
    "invoice_date",
    "amount_total",
    "amount_without_tax",
    "tax_amount",
    "seller_name",
    "seller_tax_no",
    "buyer_name",
    "buyer_tax_no",
    "category",
]

PROMPT = """你是一名专业的中国增值税发票识别助手。请从这份电子发票 PDF 中提取信息，并严格只输出一个 JSON 对象，不要输出任何解释性文字或 markdown 代码块。

JSON 的键固定如下（提取不到的值设为 null，金额只保留数字、不要货币符号和千分位逗号，日期统一为 YYYY-MM-DD 格式）：
{
  "invoice_no": "发票号码（20位或8位数字）",
  "invoice_type": "发票类型，如：电子普通发票/增值税专用发票/普通发票/全电发票/数电发票",
  "invoice_date": "开票日期",
  "amount_total": "价税合计（小写金额），数字",
  "amount_without_tax": "不含税金额，数字",
  "tax_amount": "税额，数字",
  "seller_name": "销售方名称（完整公司名称）",
  "seller_tax_no": "销售方纳税人识别号",
  "buyer_name": "购买方名称（完整名称）",
  "buyer_tax_no": "购买方纳税人识别号",
  "category": "消费类目，如：餐饮/交通/住宿/购物/加油/通讯/其他"
}"""


def is_configured() -> bool:
    return bool(settings.QWEN_API_KEY.strip())


def _normalize_date(v) -> str | None:
    """将各种中文/斜杠日期格式归一为 YYYY-MM-DD"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "null":
        return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            return s
    return s


def _to_float(v) -> float | None:
    """金额转 float，去除货币符号、千分位、中文文字"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("￥", "").replace("¥", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _clean_str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() != "null" else None


def parse_model_text(text: str) -> dict:
    """从模型输出中提取 JSON（兼容被 ```json 包裹或前后有杂散文字的情况）"""
    t = text.strip()
    # 去掉 markdown 代码块
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        t = fence.group(1).strip()
    # 截取第一个 { 到最后一个 }
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        t = t[i : j + 1]
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("模型返回不是 JSON 对象")
    return data


def normalize_fields(raw: dict) -> dict:
    """将模型返回归一化、清洗为可入库字段"""
    out = {k: None for k in FIELD_KEYS}
    for k in FIELD_KEYS:
        v = raw.get(k)
        if k == "invoice_date":
            out[k] = _normalize_date(v)
        elif k.startswith("amount_") or k == "tax_amount":
            out[k] = _to_float(v)
        else:
            out[k] = _clean_str(v)
    # 价税合计缺失时，用不含税金额 + 税额兜底
    if out["amount_total"] is None:
        a, t = out["amount_without_tax"], out["tax_amount"]
        if a is not None and t is not None:
            out["amount_total"] = round(a + t, 2)
    return out


def _call_qwen(pdf_bytes: bytes) -> str:
    """调用 OpenAI 兼容 chat/completions，返回模型文本输出"""
    b64 = base64.b64encode(pdf_bytes).decode()
    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {"file_data": f"data:application/pdf;base64,{b64}"},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        settings.QWEN_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {settings.QWEN_API_KEY.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code == 401:
            raise RuntimeError("API Key 无效或已失效（401），请检查百炼 API Key") from e
        if e.code == 429:
            raise RuntimeError("调用频率受限（429），请稍后重试") from e
        raise RuntimeError(f"模型接口返回 {e.code}：{detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接百炼服务：{e.reason}（请检查网络）") from e

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"模型响应格式异常：{json.dumps(body)[:300]}") from e


def recognize_one(db: Session, inv: Invoice) -> dict:
    """识别单张发票并写库，返回归一化字段；失败时写入 ocr_error"""
    p = Path(inv.file_path)
    if not p.exists():
        raise RuntimeError("发票文件不存在或已被移动")
    if p.suffix.lower() != ".pdf":
        raise RuntimeError("OFD 格式暂不支持自动识别，请在编辑中手动录入字段")

    raw_text = _call_qwen(p.read_bytes())
    fields = normalize_fields(parse_model_text(raw_text))

    # 发票号去重：不同文件识别出同一发票号，只保留一份有效记录
    if fields["invoice_no"]:
        dup = (
            db.query(Invoice)
            .filter(Invoice.invoice_no == fields["invoice_no"], Invoice.id != inv.id)
            .first()
        )
        if dup:
            raise RuntimeError(f"发票号 {fields['invoice_no']} 与已入库发票重复（ID={dup.id}）")

    for k, v in fields.items():
        setattr(inv, k, v)
    inv.ocr_status = "success"
    inv.ocr_error = None
    db.commit()
    return fields
