# Fab Bot —— 半导体工厂智能助手 (脚手架)

面向半导体工厂内网的 AI 助手项目脚手架, 包含两个可运行的核心模块:

| 模块 | 功能 | 位置 |
|---|---|---|
| 知识问答 | SOP/手册/FAQ 的 RAG 问答, 强制引用来源 | `app/rag/` |
| 数据查询 | 自然语言 -> SQL, 只读执行, 带 200 行上限 | `app/sqlbot/` |

Web 界面 (`app/web/index.html`, 单文件无构建依赖): 多会话管理 (localStorage
持久化)、流式打字机输出 (SSE)、Markdown 渲染、引用来源卡片、SQL 结果表格、
意图提示、会话清空/复制, 支持移动端。

配套文档: [整体技术方案](docs/半导体工厂智能助手技术方案.docx) ·
[选型与算力评估](docs/选型与算力评估.md)

## 快速开始 (Mock 模式, 无 GPU 可跑)

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8100
```

打开 http://127.0.0.1:8100 即可对话。启动时自动完成:
1. 生成演示数据库 (机台/在制/良率/告警四张表);
2. 导入 `data/knowledge/` 下的示例知识文档。

试试: 「最近未处理的告警有哪些」「ETCH 区几台机台是 DOWN 的」「射频功率漂移怎么处理」

## 接入真实 LLM (vLLM)

```bash
# 在 GPU 服务器上 (显存需求见 docs/选型与算力评估.md)
pip install vllm
vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ --port 8000 --max-model-len 8192
```

然后把 `config.yaml` 改两处:
```yaml
llm:
  mock: false
  base_url: "http://<GPU服务器IP>:8000/v1"
  model: "Qwen/Qwen2.5-32B-Instruct-AWQ"
```

Embedding 同理: `rag.embedding.provider` 改为 `openai`, 指向 BGE-M3 服务
(如 TEI: `text-embeddings-inference`), 或先用 Ollama 跑小模型验证。

Ollama 快速替代: `ollama serve` 后 `base_url: "http://127.0.0.1:11434/v1"`。

## 常用接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | 统一入口, 自动分流知识问答/数据查询 |
| POST | `/api/chat/stream` | 流式版统一入口 (SSE: meta→delta*/result→done) |
| POST | `/api/kb/ask` | 知识问答直连 |
| POST | `/api/data/query` | 数据查询直连 |
| POST | `/api/kb/ingest` | 导入文档 (`{"path": "data/knowledge"}` 可省略) |
| POST | `/api/kb/ingest_notes` | 导入 HCL Notes 内容 (export/domino 双模式) |
| GET | `/api/health` | 健康检查 (含模型模式/知识库规模) |
| GET | `/docs` | Swagger 交互文档 |

## 导入自己的知识库

把 SOP/手册 (.md/.txt/.docx/.pdf) 放进 `data/knowledge/`, 然后:
`curl -X POST http://127.0.0.1:8100/api/kb/ingest`
(.docx/.pdf 需先 `pip install python-docx pdfplumber`; 扫描件建议先用 MinerU 做 OCR)

## 接入 HCL Notes (Lotus Notes)

Notes 内容存于 Domino 服务器 .nsf 库, 不能直接读文件, 须经接口抽取。三种路线:

| 路线 | 方式 | 适用 |
|---|---|---|
| 定时导出 (推荐) | 导出代理 / COM 脚本产出 JSON+附件 → `POST /api/kb/ingest_notes` | 安全, 与中间库原则一致 |
| Domino HTTP | Bot 用只读账号经 `?OpenDocument` 等经典 URL 拉取 | 实时性好, 需 IT 开通 |
| COM 自动化 | `tools/export_notes_com.py` (需本机 Notes 客户端 + pywin32) | 无服务器权限时的过渡 |

导出 JSON 契约与 Domino 客户端实现见 `app/adapters/hcl_notes.py`;
导出目录样例见 `data/demo/notes_export_sample/`。

要点:
- **notes:// 文档链接**: 私有协议, Bot 点不开; 适配器会解析出链接 UNID 并在
  知识条目上标注「文档链接」, 目标文档需纳入导出范围才能被检索
- **富文本**: 经 HTML 渲染转纯文本 (保留列表/换行); 表格类内容建议整理成附件
- **附件**: .docx/.pdf/.md 等附件自动落入既有解析管线
- **权限**: 导出/拉取账号对目标库只读, 导出文件落盘位置注意密级
- 快速试跑: `POST /api/kb/ingest_notes` body `{"path": "data/demo/notes_export_sample"}`

## 目录结构

```
app/
├── llm/        # LLM 网关 (OpenAI 兼容协议 + Mock) 与 Prompt 模板
├── rag/        # 知识问答: 导入分块/向量库/检索生成
├── sqlbot/     # 数据查询: schema 语义层 / SQL 安全校验 / Text2SQL
├── adapters/   # MES 适配器接口 + HCL Notes 接入 + 演示数据 (真实接入写在这里)
├── api/        # 路由 + 审计日志
└── web/        # 聊天界面 (单页, 无需前端构建)
tools/          # HCL Notes COM 导出脚本等辅助工具
data/
├── knowledge/  # 待导入的 SOP/手册 (已有 2 个示例)
└── demo/       # 演示库 (seed_demo_db.py 可重置)
tests/          # python -m pytest tests -q
```

## 生产化改造清单

- [ ] 向量库: `LocalVectorStore` -> Milvus / pgvector (接口已对齐, 换实现即可)
- [ ] 数据源: `sqlbot.db_path` / `adapters.MESAdapter` -> IT 侧只读中间库
- [ ] 权限: 对接公司 LDAP/SSO, 按角色过滤可查询的表与列
- [ ] 审计: JSONL -> 数据库/日志平台, 按资安要求配置保留期
- [ ] 入口: 接入企业微信/钉钉/飞书机器人, 推广成本远低于独立 Web
- [ ] HTTPS 与部署: 见 `Dockerfile` + `docker-compose.yml` (vLLM + pgvector)
- [ ] 评测: 建 50~100 条真实问题评测集, 每次改动回归

## 已实现的安全设计

- SQL 只放行单条 SELECT、禁注释、强制 LIMIT<=200、sqlite 以 `mode=ro` 只读打开
- RAG 答案强制引用来源编号, 检索不到明确说"未找到"
- 所有 `/api/chat` 请求落审计日志 (用户/问题/耗时)
