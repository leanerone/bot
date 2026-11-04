#!/usr/bin/env bash
# 一键质量门禁: lint + 测试 + 评测 + 前端脚本语法校验
# 用法: bash scripts/check_all.sh    (全部通过退出码 0)
set -e
cd "$(dirname "$0")/.."
echo "== 1/4 ruff lint =="
python -m ruff check app eval tests tools scripts --select E,F,W --line-length 120
echo "== 2/4 pytest =="
python -m pytest tests -q
echo "== 3/4 离线评测 =="
PYTHONIOENCODING=utf-8 python eval/run_eval.py >/dev/null
echo "   评测通过 (见 eval/report.md)"
echo "== 4/4 前端脚本语法 =="
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
echo "== 全部通过 =="
