"""发票管家后端入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .database import Base, engine
from . import models  # noqa: F401  确保模型注册到 Base.metadata
from .routers import (
    dashboard_router,
    email_router,
    groups_router,
    invoice_router,
    ocr_router,
    sync_router,
)

app = FastAPI(title="发票管家 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 建表（SQLite，无历史迁移需求）
Base.metadata.create_all(bind=engine)

app.include_router(email_router.router, prefix="/api/email", tags=["邮箱配置"])
app.include_router(sync_router.router, prefix="/api/sync", tags=["发票采集"])
app.include_router(ocr_router.router, prefix="/api/ocr", tags=["智能识别"])
app.include_router(groups_router.router, prefix="/api/groups", tags=["归类分组"])
app.include_router(dashboard_router.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(invoice_router.router, prefix="/api/invoices", tags=["发票管理"])

# 前端静态页面（阶段一使用单页 HTML，后续替换为 Vue3 工程构建产物）
_static = BASE_DIR / "static"
_static.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
