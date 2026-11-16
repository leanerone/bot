# Fab Bot 架构说明 (v4.4.1, 面向后续维护者)

> 技术选型依据与算力评估见 docs/选型与算力评估.md; 部署操作见 docs/DEPLOY.md;
> MCP 工具契约见 docs/MCP_TOOLS.md。

## 1. 模块地图

| 模块 | 职责 | 关键文件 |
|---|---|---|
| `app/llm` | LLM 网关: Provider 层 (openai/azure/azure-classic) + 流式 + Mock + 降级态 (degraded) + Prompt 模板 | `client.py` `prompts.py` |
| `app/rag` | 知识问答: 文档解析分块 / 向量库 (原子写) / BM25 / 混合检索 / rerank 精排 / 生成链路 | `ingest.py` `store.py` `bm25.py` `pipeline.py` `rerank.py` |
| `app/sqlbot` | 数据查询: 语义层 / SQL 安全校验 / Text2SQL 只读执行 | `schema.py` `validator.py` `text2sql.py` |
| `app/agent` | ReAct Agent 循环: 工具白名单 (风险分级/requires_confirm 预留) + Hook 消毒审计 + 步数可配/重复去重 | `loop.py` |
| `app/skillhub` | 技能注册表 (SKILL.md frontmatter 校验) + 受控执行器 (Fernet 密钥注入/30s 超时/结构化截断/审计) | `registry.py` `runner.py` |
| `app/guard` | 提示注入扫描: 正则特征 + NFKC/拆字归一化双路匹配 + 信任边界分隔符 | `prompt_guard.py` |
| `app/services` | 领域服务: 交班报告生成 (Word 导出/推送共用) | `shift_report.py` |
| `app/adapters` | MES 适配器接口 + HCL Notes 接入 + 演示数据 (0 字节自愈/过期重种) | `base.py` `hcl_notes.py` `mock_mes.py` |
| `app/store` | 持久化: SQLite DAO + PBKDF2 口令 + 令牌 (UA 绑定/TTL 缓存即时失效) | `db.py` `security.py` |
| `app/api` | 路由: 认证/问答/Agent/技能/任务/图表/审计/管理/配置 + 意图路由 (关键词+模型混合) | `routes.py` `agent_routes.py` `skillhub.py` `tasks.py` `admin.py` `admin_config.py` `intent.py` `deps.py` `auth_lock.py` `limits.py` |
| `app/notify` | 群推送: Teams 双格式 (Connector MessageCard / Power Automate Adaptive Card) + 企微/钉钉/飞书 | `teams.py` `webhook.py` `feishu.py` |
| `app/watcher` | 告警轮询守护 + Notes 定时增量同步 (均可配置开关) | `alarm_watcher.py` `notes_sync.py` |
| `app/log.py` | 统一日志框架 (fabbot.* 子日志器, 级别/文件轮转可配) | `log.py` |
| `app/web` | 零构建回退页 (无 React dist 时使用) | `index.html` `admin.html` |
| `desktop/shell` | C# WPF + WebView2 轻壳: 无边框/托盘/全局热键 Ctrl+Alt+F/sidecar 管理 | `MainWindow.xaml.cs` |
| `desktop/ui` | React18+TS+Tailwind 前端: 工作台/对话/知识库/数据台/任务/技能/管理/设置 | `src/pages/` |
| `mcp_server.py` | MCP Server: 7 工具统一 envelope, stdio / streamable-http (密钥头) | `mcp_server.py` |
| `backend_runner.py` | PyInstaller sidecar 入口: 数据根落位/配置兜底 (与仓库 config 同构)/UI 落位 | `backend_runner.py` |
| `skills/` | 官方技能声明 (rag / text2sql / alarm-watch) | `*/SKILL.md` |
| `eval` | 离线评测集 (65 条: kb42+sql17+chitchat6, 意图同集评测) 与脚本 | `evalset.json` `run_eval.py` |

## 2. 核心请求流

### 登录
```
POST /api/auth/login → 限流 + auth_lock (防爆破锁定/admin 全局限速)
→ db.authenticate (PBKDF2 校验) → 签发 token (auth_tokens 表, 绑定 UA 摘要)
→ HttpOnly Cookie (fabbot_token) → 后续请求 deps.require_user/require_role 解析
   (resolve_token 带 60s TTL 缓存; 禁用/改密/吊销即时清缓存)
```

### 知识问答 (流式)
```
POST /api/chat/stream
→ require_user → 限流 → guard.scan (注入扫描标注) → intent.classify_smart
   # 关键词得分远离阈值短路; 临界问法走 LLM JSON 分类 (温度0, 低置信回退)
→ _resolve_session: 取/建会话 (uuid ID) + 落库用户消息
→ RAG: pipeline._retrieve        # 向量/BM25 各取 top 2×k → RRF(1/(60+rank)) 融合 → rerank (off/vllm/local) → top_k
→ LLM chat_stream (Provider 层)  # system=引用约束+资料信任边界, 携带历史 (>10 轮自动压缩)
→ SSE: meta(type,session_id) → delta* → done(sources, message_id)
→ 落库 assistant 消息 + 审计 (JSONL + SQLite 双写, PII 脱敏)
```

### 数据查询
```
classify → sqlbot.text2sql.query
→ LLM 生成 SQL (schema+语义层+few-shot, 携带历史)
→ validator.validate_sql: 仅单条 SELECT / 禁注释 / 禁多语句 / LIMIT≤200 / 字符串黑名单脱敏
→ sqlite mode=ro 只读执行 (生产: 中间库只读账号)
→ SSE result 事件 (sql/columns/rows/row_count/message_id)
```

### Agent 循环 (v4.4 D3)
```
POST /api/agent/chat(/stream)
→ require_user → 限流 → guard.scan → 提前建会话并落库提问 (meta 即带 session_id)
→ run_agent: 思考→工具→观察, 最多 agent.max_steps 轮 (默认 3, 同工具同参去重)
   工具白名单: kb_search / sql_query / alarms_open / shift_report (全部只读, 与 MCP 同源实现)
   Hook: 每次调用前 prompt_guard.sanitize 参数 + 全量审计
   mock: 规则演示路径; 真实 LLM: JSON 结构化决策 (不依赖 function-calling API)
→ SSE: meta(type,session_id) → agent_step* (工作线程+队列实时推送, 15s ping 保活)
   → delta* → done(sources, steps, session_id, message_id)
→ 落库 assistant 消息 + 审计
```

### 技能执行 (v4.4 D4/D5)
```
POST /api/skills/{name}/run (user+; viewer 403)
→ registry 校验 frontmatter → 工具映射 (MCP 名 → 宿主白名单工具)
→ 密钥注入 (skillhub.secrets, Fernet 解密不落日志) → 30s 超时受控执行
→ 输出结构化截断 (≤20000 字符, 保持合法 JSON) → 全量审计
UI: 写权限技能弹写确认卡 (_confirmed); GET /api/skills/{name}/runs 回看最近执行
```

### MCP 消费 (连接器模式)
```
AIWEB Agent / MCP 客户端 → mcp_server.py (stdio 或 streamable-http:8111)
→ 7 工具 (见 docs/MCP_TOOLS.md) → 与 Web 同一套底层实现
→ 统一 envelope {ok, data, error}; http 模式可选 X-FabBot-Key (常量时间比较)
```

## 3. 数据模型 (SQLite, app.db)

| 表 | 用途 | 备注 |
|---|---|---|
| users | 账号 (PBKDF2 散列) | role: viewer/user/admin |
| auth_tokens | 登录令牌 | 过期自动清理; 改密即吊销; UA 摘要绑定 |
| chat_sessions | 会话 | uuid 随机 ID; 属主校验贯穿所有读写 |
| messages | 消息 | sources/columns/rows 存 JSON; rating 反馈; 索引 session_id |
| audit | 审计 | 与 data/audit.log 双写; PII 脱敏 |
| tasks | 我的任务 | 归属校验; 索引 user_id |

向量库: `data/vector_store/{meta.json,vectors.npy}` (LocalVectorStore, tmp+os.replace 原子写);
接口仅 add/search, ≥10 万片段时换 Milvus/pgvector, 上层不动。

## 4. 扩展点 (接真实环境时只动这些)

| 要换什么 | 在哪改 | 注意 |
|---|---|---|
| 真实 LLM | config.yaml → llm.mock=false + base_url (+provider) | openai/azure/azure-classic 三协议; 云端出口须先过 D1 合规决策 |
| Embedding | rag.embedding.provider=openai | 建议 BGE-M3 (TEI 部署) |
| Rerank | rag.rerank.provider=vllm/local | 默认 off 规则降级零回归; 异常静默降级 |
| MES 真数据 | 实现 adapters.MESAdapter / 改 sqlbot.db_path | **只读**, 经中间库, 禁直连生产网 |
| 更多知识源 | rag/ingest.read_document 加分支 / adapters 加适配器 | 走既有 ingest→store 管线 (先去重后嵌入) |
| 意图分类 | api/intent.classify_smart | 关键词+模型混合已实装; 换模型签名不变 |
| 存储升级 | store/db.py DAO | 换 Postgres, 上层接口不变 |
| 群推送渠道 | notify/ 加模块 | Teams/企微/钉钉/飞书已内置 |
| 新技能 | skills/<name>/SKILL.md | frontmatter 规范见 docs/SKILL_SPEC.md; 工具须在宿主白名单 |
| Agent 新工具 | agent/loop.py TOOLS + mcp_server.py | 风险分级 + Hook 审计; 写操作须 requires_confirm |

## 5. 质量体系

- **单元/接口测试**: `python -m pytest tests -q` (138 项: 校验/持久化/认证/权限/会话/反馈/
  意图/检索/通知/守护/provider/安全/agent/rerank/notes/docx/缺陷回归)
- **离线评测**: `python eval/run_eval.py` (65 条: 知识 42/42 · SQL 17/17 · 意图 65/65, 输出 eval/report.md)
- **MCP 冒烟**: `python scripts/mcp_smoke.py` (stdio 握手 + 7/7 工具)
- **一键门禁**: `bash scripts/check_all.sh` (lint+测试+评测+MCP 冒烟+前端语法+UI 构建)
- **CI**: GitHub Actions (.github/workflows/ci.yml) 与门禁同套 + 前端 tsc --noEmit / npm build
- **前端校验**: React UI 走 tsc; 零构建回退页改后用 node --check 校验脚本块
- **Lint**: `python -m ruff check app eval tests tools scripts mcp_server.py backend_runner.py --line-length 120`

## 6. 设计红线 (改动前必读)

1. **生产数据默认全内网私有化, 不经任何 LLM 公有云 API。**
   现状如实说明: v4.4 E0 已实装可选云端 Provider (llm.provider=azure/azure-classic),
   默认配置为本地 openai 兼容端点 + Mock, 不启用任何云端出口; 一旦配置 Azure,
   问答内容 (含检索出的生产知识片段) 将发送至公有云 API。
   **⚠️ 待决策层确认**: 启用 Azure 云端出口前, 必须经正式合规决策修订本红线
   (数据分级/脱敏边界/合同与审计要求), 未经批准不得在生产配置中启用云端 provider;
   本条的安全意图 (生产数据不出内网) 在决策前持续有效。
2. 数据查询永远是只读 (校验层 + 只读连接双保险), 写操作走「建议+人工确认」;
   Agent 工具白名单当前全部只读, 写工具须 requires_confirm + 写确认卡;
3. RAG 回答必须可溯源, 检索不到明确告知;
4. 所有问答与操作落审计 (含 Agent 工具调用与技能执行);
5. prompt 模板集中在 app/llm/prompts.py, 改动需跑评测回归。