# Fab Bot 架构说明 (v4.x, 面向后续维护者)

> 技术选型依据与算力评估见 docs/选型与算力评估.md; 部署操作见 docs/DEPLOY.md。

## 1. 模块地图

| 模块 | 职责 | 关键文件 |
|---|---|---|
| `app/llm` | LLM 网关: OpenAI 兼容协议 (chat/chat_stream) + Mock 实现 + Prompt 模板 | `client.py` `prompts.py` |
| `app/rag` | 知识问答: 文档解析分块 / 向量库 / BM25 / 混合检索 / 生成链路 | `ingest.py` `store.py` `bm25.py` `pipeline.py` |
| `app/sqlbot` | 数据查询: 语义层 / SQL 安全校验 / Text2SQL 只读执行 | `schema.py` `validator.py` `text2sql.py` |
| `app/adapters` | MES 适配器接口 + HCL Notes 接入 + 演示数据 | `base.py` `hcl_notes.py` `mock_mes.py` |
| `app/store` | 持久化: SQLite DAO + PBKDF2 口令 + 令牌 | `db.py` `security.py` |
| `app/api` | 路由: 认证/问答/会话/反馈/审计/管理 + 意图路由 | `routes.py` `auth_routes.py` `admin.py` `intent.py` `deps.py` |
| `app/notify` | 企微/钉钉群机器人推送 | `webhook.py` |
| `app/watcher` | 告警轮询守护 (可配置开关) | `alarm_watcher.py` |
| `app/web` | 前端: 聊天页 + 管理后台 (零构建单文件) | `index.html` `admin.html` |
| `eval` | 离线评测集与脚本 | `evalset.json` `run_eval.py` |

## 2. 核心请求流

### 登录
```
POST /api/auth/login → db.authenticate (PBKDF2 校验) → 签发 token (auth_tokens 表)
→ HttpOnly Cookie (fabbot_token) → 后续请求 deps.require_user/require_role 解析
```

### 知识问答 (流式)
```
POST /api/chat/stream
→ require_user → intent.classify(question)          # 加权信号评分
→ _resolve_session: 取/建会话 + 落库用户消息
→ RAG: pipeline._retrieve                           # 向量 top-2k + BM25 top-2k → RRF 融合 top-k
→ LLM chat_stream (vLLM SSE)                        # system=引用约束, 携带最近历史
→ SSE: meta(type,session_id) → delta* → done(sources, message_id)
→ 落库 assistant 消息 + 审计 (JSONL + SQLite 双写)
```

### 数据查询
```
classify → sqlbot.text2sql.query
→ LLM 生成 SQL (schema+语义层+few-shot, 携带历史)
→ validator.validate_sql: 仅单条 SELECT / 禁注释 / 禁多语句 / LIMIT≤200 / 字符串黑名单脱敏
→ sqlite mode=ro 只读执行 (生产: 中间库只读账号)
→ SSE result 事件 (sql/columns/rows/row_count/message_id)
```

## 3. 数据模型 (SQLite, app.db)

| 表 | 用途 | 备注 |
|---|---|---|
| users | 账号 (PBKDF2 散列) | role: viewer/user/admin |
| auth_tokens | 登录令牌 | 过期自动清理; 改密即吊销 |
| chat_sessions | 会话 | 属主校验贯穿所有读写 |
| messages | 消息 | sources/columns/rows 存 JSON; rating 反馈 |
| audit | 审计 | 与 data/audit.log 双写 |

向量库: `data/vector_store/{meta.json,vectors.npy}` (LocalVectorStore);
接口仅 add/search, ≥10 万片段时换 Milvus/pgvector, 上层不动。

## 4. 扩展点 (接真实环境时只动这些)

| 要换什么 | 在哪改 | 注意 |
|---|---|---|
| 真实 LLM | config.yaml → llm.mock=false + base_url | 协议 OpenAI 兼容, 代码零改动 |
| Embedding | rag.embedding.provider=openai | 建议 BGE-M3 (TEI 部署) |
| MES 真数据 | 实现 adapters.MESAdapter / 改 sqlbot.db_path | **只读**, 经中间库, 禁直连生产网 |
| 更多知识源 | rag/ingest.read_document 加分支 / adapters 加适配器 | 走既有 ingest→store 管线 |
| 意图分类 | api/intent.classify | 当前评分制, 可换模型分类, 签名不变 |
| 存储升级 | store/db.py DAO | 换 Postgres, 上层接口不变 |
| 群推送渠道 | notify/webhook.py 加函数 | 企业微信/钉钉已内置 |

## 5. 质量体系

- **单元/接口测试**: `python -m pytest tests -q` (51 项: 校验/持久化/认证/权限/会话/反馈/意图/检索/通知/守护)
- **离线评测**: `python eval/run_eval.py` (40 条: 知识命中率 / SQL 可执行率, 输出 eval/report.md)
- **前端校验**: 修改 index.html/admin.html 后, 用 node --check 校验脚本块语法
- **Lint**: `python -m ruff check app eval tests tools --line-length 120`

## 6. 设计红线 (改动前必读)

1. 生产数据不经任何 LLM 公有云 API (全内网私有化);
2. 数据查询永远是只读 (校验层 + 只读连接双保险), 写操作走「建议+人工确认」;
3. RAG 回答必须可溯源, 检索不到明确告知;
4. 所有问答与操作落审计;
5. prompt 模板集中在 app/llm/prompts.py, 改动需跑评测回归。
