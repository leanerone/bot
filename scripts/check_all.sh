#!/usr/bin/env bash
# 一键质量门禁: lint + 测试 + 评测 + MCP 冒烟 + 前端脚本语法 + 桌面 UI 构建
# 用法: bash scripts/check_all.sh    (全部通过退出码 0)
set -e
cd "$(dirname "$0")/.."
echo "== 1/6 ruff lint =="
python -m ruff check app eval tests tools scripts mcp_server.py backend_runner.py --select E,F,W --line-length 120
echo "== 2/6 pytest =="
python -m pytest tests -q
echo "== 3/6 离线评测 =="
python data/demo/seed_demo_db.py   # 评测/MCP 冒烟依赖演示库, 先显式重种
PYTHONIOENCODING=utf-8 python eval/run_eval.py >/dev/null
echo "   评测通过 (见 eval/report.md)"
echo "== 4/6 MCP 冒烟 (stdio 7 工具) =="
PYTHONIOENCODING=utf-8 python scripts/mcp_smoke.py
echo "== 5/6 前端脚本语法 =="
if command -v node >/dev/null 2>&1; then
python - <<'PY'
import re
from pathlib import Path
for f in ["app/web/index.html", "app/web/admin.html"]:
    html = Path(f).read_bytes().decode("utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    Path("_chk.js").write_bytes(m.group(1).encode("utf-8"))
    print("  extracted:", f)
PY
node --check _chk.js && rm _chk.js
else
  echo "   跳过 (未检测到 node)"
fi
echo "== 6/6 桌面 UI 构建 (tsc + vite) =="
if command -v npm >/dev/null 2>&1; then
  (cd desktop/ui && (npm ci || npm install) && npx tsc --noEmit && npm run build)
else
  echo "   跳过 (未检测到 npm)"
fi
echo "== 全部通过 =="