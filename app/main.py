"""Fab Bot 应用入口。

启动: uvicorn app.main:app --port 8100 --reload
页面: http://127.0.0.1:8100 (登录页) · /admin 管理后台
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.adapters.mock_mes import DEMO_DB, seed_demo_db
from app.api import admin as admin_api
from app.api import auth_routes
from app.api.routes import router
from app.api.tasks import router as tasks_router
from app.config import ROOT, abs_path, cfg
from app.rag.ingest import get_store, ingest_dir
from app.store import db
from app.watcher.alarm_watcher import start_if_enabled

_watcher = None


def _bootstrap() -> None:
    """启动引导: 初始化数据库(含内置账号) -> 演示库(数据过期自动重种) -> 知识库为空时自动导入。"""
    db.get_conn()  # 建表 + 首次种子账号
    seed_demo_db(DEMO_DB)
    import sqlite3

    conn = sqlite3.connect(str(DEMO_DB))
    max_dt = conn.execute("SELECT COALESCE(MAX(dt), '') FROM alarms").fetchone()[0]
    conn.close()
    if max_dt and max_dt < datetime.now().strftime("%Y-%m-%d"):  # 演示数据滑出时间窗 -> 重种
        seed_demo_db(DEMO_DB, force=True)
        print("[bootstrap] 演示数据已过期, 已按当天重新生成")
    store = get_store()
    kb_dir = abs_path(cfg("rag.knowledge_path", "data/knowledge"))
    if len(store) == 0 and kb_dir.exists() and any(kb_dir.iterdir()):
        summary = ingest_dir(str(kb_dir))
        print(
            f"[bootstrap] 已导入知识库: {summary['chunks']} 片段 / "
            f"{len(summary['files'])} 文件 (errors: {len(summary['errors'])})"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watcher
    _bootstrap()
    _watcher = start_if_enabled()  # config watcher.enabled=false 时为 None
    yield
    if _watcher:
        _watcher.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="Fab Bot", version="4.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(auth_routes.router)
    app.include_router(router)
    app.include_router(admin_api.router)
    app.include_router(tasks_router)

    # 桌面前端 (React 构建产物) 存在时, 由后端托管 —— 与 API 同源, Cookie 免跨域
    dist = ROOT / "desktop" / "ui" / "dist"
    if dist.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{spa_path:path}", include_in_schema=False)
        def spa(spa_path: str):
            if spa_path.startswith(("api/", "docs", "openapi", "redoc")):
                raise HTTPException(404, "Not Found")
            if spa_path == "admin":
                return FileResponse(str(ROOT / "app" / "web" / "admin.html"))
            candidate = (dist / spa_path).resolve()
            if spa_path and str(candidate).startswith(str(dist.resolve())) and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(dist / "index.html")  # SPA fallback
    else:
        @app.get("/")
        def index():
            return FileResponse(str(ROOT / "app" / "web" / "index.html"))

        @app.get("/admin")
        def admin_page():
            return FileResponse(str(ROOT / "app" / "web" / "admin.html"))

    return app


app = create_app()
