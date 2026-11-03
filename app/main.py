"""Fab Bot 应用入口。

启动: uvicorn app.main:app --port 8100 --reload
页面: http://127.0.0.1:8100
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.adapters.mock_mes import DEMO_DB, seed_demo_db
from app.api.routes import router
from app.config import ROOT, abs_path, cfg
from app.rag.ingest import get_store, ingest_dir


def _bootstrap() -> None:
    """演示引导: 自动建演示库; 知识库为空且有文档时自动导入。"""
    seed_demo_db(DEMO_DB)
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
    _bootstrap()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Fab Bot", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(router)

    @app.get("/")
    def index():
        return FileResponse(str(ROOT / "app" / "web" / "index.html"))

    return app


app = create_app()
