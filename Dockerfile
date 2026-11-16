# syntax=docker/dockerfile:1
# FabBot 4.4.1 多阶段镜像:
#   阶段1 (node): 构建 React 前端 desktop/ui -> dist
#   阶段2 (python): 后端 + MCP server + 技能库 + 前端产物, 非 root 运行
# 构建: docker build -t fabbot:4.4.1 .   (compose 见 deploy/docker-compose.prod.yml)

# ---- 阶段 1: 前端构建 ----
FROM node:20-alpine AS ui-build
WORKDIR /ui
COPY desktop/ui/package*.json ./
# 有 lock 用 npm ci (可复现); 无 lock 时回退 npm install
RUN npm ci || npm install
# 逐项拷贝源码: 仓库无 .dockerignore, 整目录 COPY 会把宿主机 node_modules/dist 带入
COPY desktop/ui/index.html desktop/ui/vite.config.ts desktop/ui/tsconfig.json ./
COPY desktop/ui/tailwind.config.js desktop/ui/postcss.config.js ./
COPY desktop/ui/src ./src
COPY desktop/ui/public ./public
RUN npm run build

# ---- 阶段 2: 运行时 ----
FROM python:3.12-slim
ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1
WORKDIR /srv/bot
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# 后端 + MCP server + 技能注册表 (skills/*/SKILL.md) + 评测/工具/脚本
COPY app ./app
COPY skills ./skills
COPY eval ./eval
COPY tools ./tools
COPY scripts ./scripts
COPY mcp_server.py backend_runner.py config.yaml ./
# data: git 跟踪的知识样例 + 演示种子脚本; 运行时 db (app.db/向量库) 启动时自动创建
COPY data ./data
# React 构建产物: app/main.py 检测到 dist 后同源托管 SPA (不再回退旧 app/web 页面)
COPY --from=ui-build /ui/dist ./desktop/ui/dist
# 非 root 运行 (compose 的 fabbot-data 卷首次挂载会继承此属主)
RUN useradd --create-home --shell /usr/sbin/nologin fabbot \
    && chown -R fabbot:fabbot /srv/bot
USER fabbot
EXPOSE 8100
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]