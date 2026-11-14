# 更新日志

## v4.4.0 (2026-11-15) —— 云模型接入 · Agent 循环 · Teams/Notes 适配 · 安全纵深

### 新增
- **LLM Provider 层 (E0)**: provider = openai(默认) / azure(Azure OpenAI v1 兼容端点, api-key 头) /
  azure-classic(经典 deployment URL); chat 与流式双路径全过 provider;
  云端不可达自动降级 Mock 并在回答首行标注 (llm.fallback_mock)
- **内置 ReAct Agent 循环 (D3)**: app/agent/loop.py —— 工具白名单(风险分级/requires_confirm 预留) +
  Hook(参数消毒+全量审计) + 最多 3 轮决策; mock 规则路径与真实 LLM JSON 决策双实现;
  SSE 新事件 agent_step, 前端步骤条展示; 新端点 /api/agent/chat(/stream)
- **MCP 工具扩充 (D1/D2)**: 新增 kb_search / shift_report / kb_sources_check, 共 7 工具;
  全部统一 envelope {ok, data, error}; 冒烟脚本覆盖 7/7 工具;
  streamable-http 可选 X-FabBot-Key 共享密钥 (C5); 启动预热导入修复 worker 线程冷导入挂起
- **Skill 执行器 v0.1 (D4)**: app/skillhub/runner.py —— frontmatter 校验 / MCP 工具映射 /
  Fernet 密钥注入 / 30s 超时受控执行 / 输出截断 / 全量审计; 端点 /api/skills/{name}/run
- **技能中心 UI (D5)**: 技能卡片(权限徽章/工具标签) + 详情弹层 + 参数执行 + 结果弹层
- **桌面管理页 (B1)**: 五页签 —— 统计/用户管理(角色/禁用/重置密码/防自锁)/审计查询+CSV 导出/
  全用户会话管理/配置管理(白名单键读写); 仅 admin 角色可见
- **Teams 通知渠道 (B3)**: app/notify/teams.py 双格式 —— O365 Connector(MessageCard) +
  Power Automate(Adaptive Card); 告警分级配色卡片+机台分布表; watcher 默认 platform=teams;
  推送测试 UI 渠道下拉 (teams/企微/钉钉/飞书); 新增飞书渠道 feishu.py
- **交班报告 Word 导出+推送 (B4)**: python-docx 导出 /api/tasks/shift/export;
  /api/tasks/shift/push 一键推送摘要到 Teams
- **HCL Notes 深化 (B5)**: 文档级增量同步(UNID 跳过+去重键) / 多库逐库拉取(失败隔离) /
  检索来源带 doclink, 引用弹层"在 Notes 中打开原文"(notes:// 协议); 定时同步守护 notes.sync
- **Rerank 精排 (E1)**: app/rag/rerank.py 三级 provider —— off(规则降级, 机台号/告警码精确加权) /
  vllm(/v1/rerank) / local(CrossEncoder); 管线 RRF→rerank→top_k, 异常静默降级零阻塞
- **意图分类模型化 (E2)**: classify_smart —— 真实 LLM 走 JSON 分类(温度 0), 低置信/超时回退关键词
- **多轮上下文压缩 (E3)**: >10 轮历史自动摘要压缩([对话摘要] 前缀), mock 截断/真实 LLM 摘要

### UI/体验
- A1 流式打字机: 40ms 批量 flush(防逐 token 重渲染) + 思考中三点动画 + 滚动跟随(上滚即停+回到底部) + aria-live
- A2 Markdown 强化: 代码块语言标签+一键复制+流式未闭合 fence 容错
- A3 引用升级: 正文 [N] 上标可点击溯源 + 流式期间来源骨架先行
- A4 骨架屏(会话切换) + 消息气泡入场动效; A5 图表配色/网格/tooltip 跟随暗色主题
- 修复: 会话消息"双数据源脱节"导致流式不渲染的问题 (Chat.tsx 重构为单一 messages 状态)

### 安全 (OWASP LLM Top 10 对照)
- C1 提示注入纵深防御: 输入侧扫描(审计标注+剥伪造分隔符, 不硬拒防误杀) +
  检索资料"资料非指令"信任边界 + SQL 独立链路; 注入评测 10/10 检出、正常问法 0 误伤
- C2 登录防爆破: 5 次/10 分钟锁 15 分钟 (管理员豁免防自锁), 锁定审计留痕
- C3 会话加固: 令牌绑定 UA 摘要(换浏览器需重登) + /api/auth/logout_all 全端登出
- C4 PII 脱敏: 审计落盘前手机号/邮箱/IP → ***, 机台号/告警码原样保留; 正文截断可配
- C5 MCP 密钥校验 + 工具调用全量审计

### 质量
- 测试 63 → 114 项全绿 (新增 provider/安全/agent/rerank/notes/docx 套件)
- 评测三项 100% 不回退 (知识 42/42 · SQL 17/17 · 意图 59/59); ruff 清零; tsc 零错误
- MCP 冒烟 7/7; 桌面端打包 v4.4.0 冒烟通过


## v4.1.0 (2026-11-05 夜间) —— 交付强化

### 新增
- 意图路由 v2: 加权信号评分 (含知识问法负分保护), 指标纳入评测 (49/49)
- 混合检索调优: Markdown 感知分块 (标题硬边界+H1/H2 面包屑), top_k 参数扫描定标
- 用户级限流: 每分钟滑动窗口 (可配置, 429 语义), 四个问答入口挂载
- 历史消息分页: keyset 游标 + 前端"加载更早消息"
- 管理后台: 会话管理页签 (全用户视角+删除) / 来源片段预览 / 按来源摘除 / 审计 CSV 导出
- 前端: 会话搜索 / 重命名 / 来源点击看全文弹层 / 来源折叠 / SQL 复制 / 导出 Markdown / 表格渲染
- 运维: 告警轮询守护 (默认关) / 企微钉钉推送 / bench 压测 / install 一键安装 / demo_push
- 文档: ARCHITECTURE.md / 方案附录B / 晨检导读; README 真实界面截图

### 质量
- 测试 44 -> 63 项; 覆盖率 88%; ruff lint 清零 (pyproject 定标)
- 评测集 41 -> 49 条: 知识命中率 100% (34/34), SQL 100% (15/15), 意图 100% (49/49)
- 一键门禁: bash scripts/check_all.sh
- 夜间守夜巡检: 11 轮门禁全部通过 (03:00~05:42, 每 20 分钟)

### 修复
- 向量库重复导入去重 (来源+正文唯一键)
- ingest 返回语义: chunks(处理数) 与 added(新增数) 分离
- 审计覆盖补全: kb/ask 与 data/query 直连入口纳入审计 (含 SQL 拒绝留痕)
- 前端: boot IIFE 命名 / loadSessions 丢消息引用 / 消息映射丢 id / showTab 页签遗漏

## v4.0.0 (2026-11-05) —— 交付级升级

### 新增
- **认证与角色**: 账号登录 (PBKDF2 散列), viewer/user/admin 三级权限, 会话令牌管理
- **服务端会话持久化**: 对话历史落 SQLite (WAL), 换设备登录可回看; 会话改名/删除
- **消息反馈**: 回答 👍/👎, 管理后台统计质量
- **管理后台** (`/admin`): 系统统计 / 用户管理 / 审计查询 / 知识库重建
- **审计双写**: JSONL 文件 + SQLite, 全操作留痕
- **混合检索**: BM25 + 向量 RRF 融合, 机台号/告警码等精确关键词命中率显著提升
- **向量库去重**: 重复导入自动跳过 (来源+正文唯一键)
- **离线评测体系**: eval/evalset.json (18 知识 + 12 SQL) + run_eval.py + 报告;
  当前 知识命中率 100%, SQL 通过率 100%
- **交付文档包**: 部署手册 DEPLOY.md / 用户手册 USER_GUIDE.md / 验收清单 ACCEPTANCE.md
- **运维脚本**: deploy/backup.sh|.ps1, nginx 样例, 生产 compose

### v3.x 功能 (保留)
- 知识问答 RAG (引用溯源) / Text2SQL 只读安全执行 / HCL Notes 双模式接入 /
  流式输出 (SSE) / 多会话 Web UI / Mock 离线演示模式

### 安全
- SQL 仅放行单条只读 SELECT + 强制 LIMIT + 只读连接 (延续)
- 登录接口失败审计 (status=fail); 管理员防自我锁定
- Cookie HttpOnly + SameSite=Lax; 令牌过期自动清理

### 已知限制
- SQLite 单机存储, 高并发或多实例需迁 Postgres (DAO 层已隔离)
- 意图路由为关键词粗分, 计划切换模型意图分类
- Rerank 接口位预留未实现 (rag.hybrid 已覆盖大部分收益)

## v3.0 (2026-11-04)
- 首个公开版本: 双模块脚手架 + Notes 接入 + 技术方案文档

## v4.2.0 (2026-11-06) —— 方案文档正式改版 + 评测扩充

- 技术方案 docx 正式改版 (V1.1): 新增附录 B「平台能力交付与质量基线」,
  摘要/实施路线/模块说明同步 v4.1 交付状态; 15 页, postcheck 9/9 + 视觉验收通过
- 评测集 49 -> 59 条 (kb 42 + sql 17): LITHO/CMP 语料深挖; 意图负向信号补点检规则
- 三项指标保持 100% (知识 42/42, SQL 17/17, 意图 59/59); 65 项测试全绿
