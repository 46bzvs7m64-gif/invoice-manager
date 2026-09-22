"""发票管家后端启动脚本：python run.py"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    print("=" * 46)
    print("  发票管家 后端服务启动")
    print(f"  本机访问:   http://127.0.0.1:{settings.PORT}")
    print(f"  手机访问:   http://<本机局域网IP>:{settings.PORT}")
    print("=" * 46)
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT)
