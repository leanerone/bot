# Fab Bot 部署手册 (v4.4.1)

> 适用: 工厂内网试点部署 (办公网段, 50 人以内)。默认全程不需要公网。
> 配置键名/默认值以仓库 `config.yaml` 与代码为准; 本文覆盖 v4.4 新增全部配置。

## 1. 环境要求

| 项 | 要求 |
|---|---|
| 服务器 | Windows / Linux 均可, 4 核 8G 起步 (不含 LLM 算力) |
| Python | 3.10+ (Docker 镜像为 3.12) |
| Node.js | 18+ (仅构建 React 前端 / 桌面打包时需要) |
| GPU (可选) | 跑真实 LLM 时按 docs/选型与算力评估.md 配置 |
| 网络 | 用户可访问本机端口 8100; MCP 跨机消费另开 8111; 访问 Domino/中间库按需开通 |

依赖说明: `python-docx` / `pdfplumber` 自 v4.4.1 起为**必选** (.docx/.pdf 知识解析 +
交班报告 Word 导出); `mcp` 为 MCP Server 依赖; rerank local 模式另需
`sentence-transformers` (按需安装)。

## 2. 快速部署 (Mock 模式, 验证部署正确性)

```bash
git clone https://github.com/leanerone/bot.git fabbot && cd fabbot
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

验证: 浏览器打开 `http://<服务器IP>:8100`, 用 admin / admin123 登录
(**首次登录后立即在管理后台改密码**)。

前端: 存在 `desktop/ui/dist` (或 PyInstaller 布局的 `ui_dist`) 时同源托管 React 新版 UI;
否则回退零构建页面 (`app/web/`)。构建新版 UI: `cd desktop/ui && npm install && npm run build`。

## 3. 生产化配置清单

1. **改默认密码**: 管理后台 → 用户 → admin 重置密码; 逐一创建真实用户。
2. **接入真实模型**: `config.yaml` → `llm.mock: false`, `base_url` 指向 vLLM 服务
   (启动命令见 docs/选型与算力评估.md)。
3. **Embedding**: `rag.embedding.provider: openai`, 指向 BGE-M3 服务 (TEI)。
4. **知识导入**: SOP/手册放 `data/knowledge/`, Notes 导出 JSON 放 `data/notes_export/`,
   管理后台 → 知识库 → 全量重建。同名文档上传自动替换旧版本。
5. **生产数据**: `sqlbot.db_path` 指向 IT 侧只读中间库 (改造说明见
   app/sqlbot/text2sql.py 头注释); 禁止直连生产库。
6. **通知渠道**: 配置 `notify.teams_webhook` (公司内网默认 Teams), 见 §4.3。
7. **审计留存**: `data/app.db` 与 `data/audit.log` 纳入备份。
8. **安全项**: 逐项过 §8 安全清单 (CORS/可信代理/MCP 密钥/HTTPS)。

## 4. 配置参考 (config.yaml, v4.4.1)

所有相对路径相对项目根目录解析 (与启动工作目录无关); PyInstaller sidecar 模式由
`FABBOT_ROOT` 环境变量指定可写数据根。管理后台「配置」页签可读写其中白名单键
(llm.mock/llm.model/rag.top_k/rag.hybrid/ratelimit.*/watcher.*/notes.mode),
写前自动备份 `config.yaml.bak`; 其余键直接编辑文件后重启。

### 4.1 LLM (llm.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `llm.mock` | `true` | Mock 演示模式 (无 GPU 可跑); 接真实模型置 false |
| `llm.provider` | `openai` | `openai`=任意 OpenAI 兼容服务 (vLLM/Ollama/OneAPI, Bearer 认证); `azure`=Azure OpenAI v1 兼容端点 (`https://<资源名>.openai.azure.com/openai/v1`, api-key 头); `azure-classic`=经典 deployment URL (拼 `?api-version=`) |
| `llm.base_url` | `http://127.0.0.1:8000/v1` | 推理服务地址 |
| `llm.api_key` | `EMPTY` | vLLM 本地可留 EMPTY; Azure 填资源密钥 |
| `llm.api_version` | `2024-10-21` | 仅 azure-classic 使用 |
| `llm.model` | `Qwen2.5-32B-Instruct-AWQ` | 模型名 (Azure 为部署名) |
| `llm.timeout` | `120` | 请求超时 (秒) |
| `llm.fallback_mock` | `true` | 云端不可达自动降级 Mock, 回答首行标注; 降级态经 `/api/health` 的 `llm.degraded` 暴露, 云端恢复自动复位 |

> ⚠️ **合规提示**: 启用 azure/azure-classic 意味着生产数据可能经公有云 LLM API,
> 与架构红线 D1 (全内网私有化) 冲突 —— 必须先经决策层合规确认 (见
> docs/ARCHITECTURE.md §6), 默认部署保持本地私有化。

Ollama 快速替代: `ollama serve` + `llm.base_url: http://127.0.0.1:11434/v1`,
`llm.model` 填已 pull 的模型名。

### 4.2 检索与精排 (rag.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `rag.knowledge_path` | `data/knowledge` | 知识文档目录 |
| `rag.store_path` | `data/vector_store` | 向量库 (meta.json + vectors.npy, 原子写) |
| `rag.chunk_size` / `rag.chunk_overlap` | `500` / `80` | 分块参数 (Markdown 标题硬边界) |
| `rag.top_k` | `6` | 返回片段数 |
| `rag.hybrid` | `true` | BM25+向量 RRF 混合检索 |
| `rag.rerank.provider` | `off` | `off`=规则降级 (机台号/告警码精确加权, 零依赖); `vllm`=OpenAI 兼容 `/v1/rerank` 端点 (vLLM rerank/TEI 等); `local`=sentence-transformers CrossEncoder (CPU 可跑) |
| `rag.rerank.model` | `BAAI/bge-reranker-v2-m3` | 精排模型 |
| `rag.rerank.top_n` | `6` | 精排后保留条数; 管线 RRF→rerank→top_k, 精排异常静默降级零阻塞 |
| `rag.embedding.provider` | `mock` | `mock`=哈希向量演示; `openai`=真实 embedding 服务 |
| `rag.embedding.base_url` / `model` / `api_key` | `http://127.0.0.1:8001/v1` / `bge-m3` / `EMPTY` | 建议 BGE-M3 (TEI 部署) |

### 4.3 通知与值守 (notify.* / watcher.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `notify.teams_webhook` | `''` | Teams: O365 Connector Incoming Webhook 或 Power Automate 触发器 URL |
| `notify.teams_format` | `connector` | `connector`=MessageCard (兼容存量); `flow`=Adaptive Card (**推荐**, Microsoft 已宣布 O365 Connector 退役, 新装环境用 Power Automate) |
| `notify.wechat_webhook` / `dingtalk_webhook` / `feishu_webhook` | `''` | 企微/钉钉/飞书群机器人 (可选渠道) |
| `watcher.enabled` | `false` | 告警轮询守护开关 |
| `watcher.interval_minutes` | `10` | 轮询间隔 (分钟) |
| `watcher.levels` | `[ALARM, CRITICAL]` | 触发推送的告警级别 |
| `watcher.platform` | `teams` | 推送渠道: teams/wechat/dingtalk/feishu |

卡片分级配色: CRITICAL 红 / ALARM 橙 / WARN 黄。管理后台「推送测试」可选渠道验证。

### 4.4 MCP Server (mcp.*)

```bash
python mcp_server.py                                  # stdio (同机 Agent 子进程)
python mcp_server.py --transport streamable-http --port 8111   # 跨机消费
```

| 键 | 默认 | 说明 |
|---|---|---|
| `mcp.require_key` | `false` | streamable-http 模式要求 `X-FabBot-Key` 请求头 (**跨机消费建议 true**); stdio 同机无需 |
| `mcp.key` | `''` | 共享密钥; 服务端常量时间比较 (防时序侧信道), 缺失/错误返回 401 |

7 个工具的名称/参数/返回 envelope 见 docs/MCP_TOOLS.md; 冒烟: `python scripts/mcp_smoke.py`。

### 4.5 技能密钥 (skillhub.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `skillhub.secrets` | `{}` | 技能运行时注入的密钥表; 值写 `fernet:<密文>` 时运行时解密, 不落日志 |
| `skillhub.fernet_key` | `''` | Fernet 主密钥 (base64, `cryptography` 生成); 留空则明文密钥仅内网自用 |

技能执行权限 user+ (viewer 只读); 声明写权限的技能触发写确认卡。

### 4.6 认证与防爆破 (auth.* / auth_lock.* / ratelimit.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `auth.token_ttl_hours` | `24` | 令牌有效期; 令牌绑定 UA 摘要 (换浏览器需重登) |
| `auth.cookie_secure` | `false` | **HTTPS 部署置 true** |
| `auth.trusted_proxies` | `[]` | 可信反代 IP 列表; 仅这些直连来源才采信 X-Forwarded-For (防伪造头绕过按 IP 的锁定/限流; 不配则反代后所有用户共享代理 IP) |
| `auth.bootstrap_users` | admin/zhangsan/guest | 首次建库种子账号, 上线后改密/禁用 |
| `auth_lock.max_failures` | `5` | 窗口内最大登录失败次数 (按 用户名+IP) |
| `auth_lock.window_minutes` | `10` | 失败统计窗口 |
| `auth_lock.lock_minutes` | `15` | 锁定时长 (423); admin 豁免锁定防自锁 |
| `auth_lock.admin_per_minute` | `3` | admin 全局限速 (豁免锁定但不豁免限速, 防换 IP 爆破唯一入口) |
| `ratelimit.chat_per_minute` | `30` | 每用户问答限流 (0=不限) |
| `ratelimit.login_per_5min` | `10` | 登录限流 (按 用户名@IP) |

令牌解析带 60s TTL 缓存 (认证热路径免 SQL); 禁用/改密/吊销即时清缓存, 即时生效保留。
多实例部署时锁定/限流计数应迁 Redis (当前为进程内计数)。

### 4.7 CORS 与日志 (cors.* / logging.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `cors.allow_origins` | `[http://127.0.0.1:8100, http://localhost:8100]` | 跨域白名单; 桌面/同源托管无需 CORS; 配 `['*']` 放开但浏览器禁带凭证 (cookie 认证体系不建议) |
| `logging.level` | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `logging.file` | `''` | 日志文件 (相对项目根, 空=仅控制台); 例 `data/fabbot.log` (自动轮转) |

### 4.8 Notes 同步 (notes.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `notes.mode` | `export` | `export`=读导出目录; `domino`=Domino HTTP 拉取 |
| `notes.export_dir` | `data/notes_export` | 导出 JSON 目录 |
| `notes.domino.*` | — | base_url/db_path/view/username/password |
| `notes.databases` | `[]` | 多库逐库增量拉取 (失败隔离); 留空退回单库配置 |
| `notes.sync.interval_minutes` | `0` | >0 启用定时增量同步守护 (仅 mode=domino); 0=关闭 |
| `notes.domino_sync_since_days` | `30` | 增量拉取回看窗口 |

### 4.9 意图与 Agent (intent.* / agent.*)

| 键 | 默认 | 说明 |
|---|---|---|
| `intent.model_margin` | `2` | 关键词得分与阈值差 ≥ 此值直接短路 (不调模型, 省首字节延迟); 临界问法才走 LLM 分类 |
| `intent.min_confidence` | `0.6` | 模型分类最低置信度, 低于回退关键词 |
| `agent.max_steps` | `3` | ReAct 循环最大决策轮数; 同工具同参数重复调用自动去重 |

### 4.10 其余

`sqlbot.db_path` (演示库 `data/demo/fab_demo.db`, 生产指向只读中间库) /
`sqlbot.max_rows` (200) / `audit.path` (`data/audit.log`) / `audit.mask_pii` (true,
手机号/邮箱/IP 脱敏) / `audit.max_text_len` (200, 0=不截断) / `store.db_path` (`data/app.db`)。

## 5. Docker 部署 (推荐)

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

v4.4.1 镜像为**完整多阶段构建** (根目录 Dockerfile):

- 阶段 1 (node:20-alpine): `npm ci` 构建 React 前端 (`desktop/ui` → dist);
- 阶段 2 (python:3.12-slim): 安装 requirements, 拷贝 app/ + skills/ + eval/ + tools/ +
  scripts/ + mcp_server.py + backend_runner.py + config.yaml + data/ (知识样例与演示种子)
  + 前端 dist; 非 root 用户 (fabbot) 运行; 内置 HEALTHCHECK (/api/health)。

compose 要点: 端口 8100; `fabbot-data` 卷持久化 data/ (会话/审计/向量库/演示库);
`config.yaml` 挂载**可写** (管理端配置写回 + .bak 备份需要, 勿加 :ro)。
vLLM/Embedding 按 GPU 机器单独部署, 通过 `llm.base_url` / `rag.embedding.base_url` 指向
(容器内访问宿主机服务用 `host.docker.internal` 或宿主内网 IP)。

MCP 跨机消费: 容器内另起 `python mcp_server.py --transport streamable-http --port 8111`
并映射端口 + 配置 `mcp.require_key: true`。

## 6. 桌面版打包与安装 (Windows)

```powershell
deploy\desktop-package.ps1 -Version 4.4.1   # npm 构建 → PyInstaller sidecar → dotnet publish → 组装 → 冒烟
iscc deploy\installer.iss                    # 生成 dist\Setup-FabBot-4.4.1.exe (Inno Setup 6.x)
```

- 布局: 安装根目录 = C# 壳 (FabBot.exe, net8.0-windows 框架依赖发布, 目标机需
  .NET 8 Desktop Runtime); `backend\FabBotBackend\` = PyInstaller sidecar;
- 安装器自动检测 WebView2 Runtime (缺失时引导安装); 用户数据目录
  `FabBotData` (config.yaml/data/知识/ui_dist 运行时落位) **卸载时保留**;
- 绿色版: 直接运行组装目录 `dist\FabBot-4.4.1\FabBot.exe`;
- 详细构建步骤见 desktop/BUILD.md。托盘常驻, 全局热键 **Ctrl+Alt+F** 呼出/隐藏。

## 7. 日常运维

- **重启**: `python -m uvicorn app.main:app --port 8100` (建议配 systemd/NSSM)
- **备份**: `deploy/backup.ps1` (Windows) / `deploy/backup.sh` (Linux),
  备份 data/ 全目录, 建议每日定时
- **知识库更新**: 覆盖文档后管理后台重建, 或「导入常规文档」/上传 (自动去重, 同名版本替换)
- **健康检查**: `GET /api/health` (version/kb_chunks/llm.mock/llm.degraded/notes_mode);
  日志看 `logging.file` (或控制台) + `data/audit.log` + 管理后台审计页
- **评测回归**: `python eval/run_eval.py` (知识/SQL/意图三项); 一键门禁 `bash scripts/check_all.sh`
- **CI**: GitHub Actions 在 main/fabai-hub 推送与 PR 自动跑 lint/测试/评测/MCP 冒烟 + 前端 tsc/构建

## 8. 故障排查

| 现象 | 处理 |
|---|---|
| 登录 401 | 确认账号未被禁用 (管理后台→用户); 忘记密码用另一 admin 重置; 换浏览器需重登 (UA 绑定) |
| 登录 423 | 失败次数过多临时锁定 (默认 15 分钟); admin 被限速 (429) 稍后再试 |
| 回答提示 LLM 不可用/首行"降级" | `llm.mock` 是否 false 而推理服务未启动; `curl http://<vllm>/v1/models`; health 的 llm.degraded 为 true 表示云端故障自动降级, 恢复后自动复位 |
| 检索结果差 | 管理后台重建知识库; 检查文档是否扫描件 (先 OCR); `python eval/run_eval.py` 看命中率; 有 GPU/TEI 时开 rerank |
| SQL 查询报错 | 确认 db_path 指向的库存在且为只读账号; 看 audit 表 status=fail 记录 |
| 上传 413 / 提问 422 | 原始文件超 10MB / 问题超 4000 字上限 |
| Teams 推送失败 | webhook 是否过期; O365 Connector 退役环境改 `teams_format: flow` + Power Automate |
| 反代后锁定误伤全员 | 配置 `auth.trusted_proxies` 为反代 IP, 使其采信 XFF 区分真实来源 |
| MCP 401 | streamable-http 开了 require_key 但客户端未带 X-FabBot-Key 头 |

## 9. 安全清单 (上线前逐项确认)

- [ ] admin 默认密码已修改; bootstrap_users 中的示例账号已处理
- [ ] 服务器仅办公网可达, 防火墙限制 8100/8111 访问范围
- [ ] SQL 中间库账号为只读
- [ ] data/ 目录备份与保留策略已配置 (按资安要求)
- [ ] HTTPS: 前置 nginx 反代 + 证书 (deploy/nginx.conf.sample); `auth.cookie_secure: true`;
      `auth.trusted_proxies` 填反代 IP
- [ ] `cors.allow_origins` 仅列可信前端源 (不用 `*`)
- [ ] MCP 跨机暴露时 `mcp.require_key: true` + 强密钥
- [ ] 启用 Azure 等云端 provider 前已完成 D1 红线合规决策 (默认不启用)
- [ ] `logging.file` 已配置并纳入留存; 审计 PII 脱敏保持开启