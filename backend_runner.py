"""FabBot 后端 sidecar 入口 (PyInstaller 打包用)。

职责:
1. 解析可写数据根目录 FabBotData, 通过 FABBOT_ROOT 传给 app.config;
2. 首次运行: 落位默认 config.yaml (内嵌兜底) + 知识样例到 data/knowledge;
3. 启动 uvicorn (端口由 C# 壳通过 FABBOT_PORT 指定)。
"""
import os
import shutil
import sys
import time
from pathlib import Path

base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
root = base / "FabBotData"
os.environ["FABBOT_ROOT"] = str(root)
os.environ.setdefault("FABBOT_PORT", "8100")

(root / "knowledge").mkdir(parents=True, exist_ok=True)
(root / "data").mkdir(parents=True, exist_ok=True)

# 默认配置 (内嵌兜底; 与仓库 config.yaml 同构 v4.4, 首次落位后用户可编辑)
DEFAULT_CONFIG = """# FabBot Desktop 默认配置 (由安装器生成, 可编辑)
llm:
  mock: true
  provider: openai
  base_url: "http://127.0.0.1:8000/v1"
  api_key: "EMPTY"
  api_version: "2024-10-21"
  model: "Qwen2.5-32B-Instruct-AWQ"
  timeout: 120
  fallback_mock: true

rag:
  knowledge_path: "data/knowledge"
  store_path: "data/vector_store"
  chunk_size: 500
  chunk_overlap: 80
  top_k: 6
  hybrid: true
  rerank:
    provider: off
    model: "BAAI/bge-reranker-v2-m3"
    top_n: 6
  embedding:
    provider: mock
    base_url: "http://127.0.0.1:8001/v1"
    model: "bge-m3"

sqlbot:
  db_path: "data/demo/fab_demo.db"
  max_rows: 200

audit:
  path: "data/audit.log"
  mask_pii: true
  max_text_len: 200

store:
  db_path: "data/app.db"

auth:
  token_ttl_hours: 24
  cookie_secure: false
  trusted_proxies: []
  bootstrap_users:
    - {username: admin,   password: admin123, role: admin,  display_name: 管理员}
    - {username: zhangsan, password: user123, role: user,   display_name: 张工}
    - {username: guest,   password: guest123, role: viewer, display_name: 访客}

notes:
  mode: export
  export_dir: "data/notes_export"
  domino:
    base_url: ""
    db_path: ""
    view: "($All)"
    username: ""
    password: ""
  databases: []
  sync:
    interval_minutes: 0

notify:
  teams_webhook: ""
  teams_format: connector
  wechat_webhook: ""
  dingtalk_webhook: ""
  feishu_webhook: ""

mcp:
  require_key: false
  key: ""

ratelimit:
  chat_per_minute: 30
  login_per_5min: 10

auth_lock:
  max_failures: 5
  window_minutes: 10
  lock_minutes: 15
  admin_per_minute: 3

intent:
  model_margin: 2
  min_confidence: 0.6

agent:
  max_steps: 3

skillhub:
  secrets: {}
  fernet_key: ""

cors:
  allow_origins: ["http://127.0.0.1:8100", "http://localhost:8100"]

logging:
  level: INFO
  file: ""

watcher:
  enabled: false
  interval_minutes: 10
  levels: [ALARM, CRITICAL]
  platform: teams
"""

meipass = Path(getattr(sys, "_MEIPASS", base))
ui_dist = meipass / "ui_dist"
if ui_dist.exists():
    target_ui = root / "ui_dist"
    if not target_ui.exists():
        shutil.copytree(ui_dist, target_ui, dirs_exist_ok=True)
        print("[runner] 桌面前端已落位 ui_dist")

# 1) config.yaml 落位 (bundle 优先, 损坏/缺失用内嵌兜底)
target_cfg = root / "config.yaml"
bundled_cfg = meipass / "bundle" / "config.yaml"
need_cfg = not target_cfg.exists() or target_cfg.stat().st_size < 100
if need_cfg:
    content = None
    if bundled_cfg.exists():
        for _ in range(3):  # 防杀毒/索引器瞬时锁
            try:
                content = bundled_cfg.read_bytes()
                break
            except PermissionError:
                time.sleep(0.5)
    if not content or len(content) < 100:
        content = DEFAULT_CONFIG.encode("utf-8")
    target_cfg.write_bytes(content)
    print("[runner] config.yaml 已落位")

# 2) 知识样例落位到 data/knowledge (与默认配置对齐)
bundled_kb = meipass / "bundle" / "knowledge"
bundled_skills = meipass / "bundle" / "skills"
target_skills = root / "skills"
if bundled_skills.exists() and not any(target_skills.glob("*/SKILL.md")):
    shutil.copytree(bundled_skills, target_skills, dirs_exist_ok=True)
    print("[runner] SKILL 目录已落位")
target_kb = root / "data" / "knowledge"
target_kb.mkdir(parents=True, exist_ok=True)
if bundled_kb.exists() and not any(target_kb.iterdir()):
    for attempt in range(3):
        try:
            shutil.copytree(bundled_kb, target_kb, dirs_exist_ok=True)
            print("[runner] 知识样例已复制到 data/knowledge")
            break
        except PermissionError:
            time.sleep(0.5)
legacy_kb = root / "knowledge"
if legacy_kb.exists() and any(legacy_kb.glob("*.md")) and not any(target_kb.iterdir()):
    shutil.copytree(legacy_kb, target_kb, dirs_exist_ok=True)

port = int(os.environ["FABBOT_PORT"])

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
