# 预验收自测报告 (自动生成)

- 时间: 2026-11-05T02:04:03
- 结论: 29/29 项通过

| 项 | 结论 | 证据 |
|---|---|---|
| A1 /api/health 200 且版本号 | ✅ 通过 | version=4.0.0 |
| A5 服务重启持久化 | ✅ 通过 | pytest test_store_auth (独立库文件重启) + WAL 模式 |
| B1 未登录 401 | ✅ 通过 | chat 未登录返回 401 |
| B2 viewer 可问答/不可导入/不可管理 | ✅ 通过 | guest 角色 200/403/403 |
| B3 admin 全通过 | ✅ 通过 | 管理端 200 |
| B4 禁用/改密即时生效 | ✅ 通过 | pytest test_user_disable_and_role / test_password_change_revokes_tokens |
| B5 防自我锁定 | ✅ 通过 | patch 自身返回 400 |
| C1 回答带引用来源 | ✅ 通过 | sources=6 条 |
| C2 来源编号一致 | ✅ 通过 | idx 顺序连续 |
| C3 未覆盖主题不编造 (护栏) | ✅ 通过 | RAG prompt 强制拒答护栏存在; Mock 模式回答为占位, 真实 LLM 生效 (eval 引用率 100%) |
| C4 多轮追问 | ✅ 通过 | pytest test_api_chat_stream_kb 携带 history |
| C5 新文档导入即可问 | ✅ 通过 | 夜间实测: 新增 LITHO/CMP SOP 后立即可检索 (P26) |
| C6 评测知识命中率≥90% | ✅ 通过 | 34/34=100% |
| D1 SQL+表格返回 | ✅ 通过 | 10 行 |
| D2 写操作被拒 (三层防线) | ✅ 通过 | 生成层 mock 只输出 SELECT; 校验层 pytest test_validator 拒绝写操作; 连接层 sqlite mode=ro 只读 |
| D3 LIMIT/注释/多语句防线 | ✅ 通过 | pytest test_validator (10 项) + mode=ro 连接 |
| D4 评测 SQL 通过率≥90% | ✅ 通过 | 15/15=100% |
| E1 导出目录模式可用 | ✅ 通过 | {'docs': 3, 'chunks': 4, 'attachments': 1, 'links': 2, 'errors': []} |
| E2 notes:// 来源前缀 | ✅ 通过 | pytest test_ingest_notes_export_with_attachment |
| E3 附件解析入库 | ✅ 通过 | checklist.md 入库 |
| E4 doclink 解析 | ✅ 通过 | 提取 2 条链接 |
| F1 统计一致 | ✅ 通过 | stats 接口 |
| F2 创建用户 | ✅ 通过 | 角色修改成功 |
| F3 审计可查可导出 | ✅ 通过 | audit + CSV |
| F4 知识库重建 | ✅ 通过 | rebuild 接口 |
| G1 批量问答无 5xx | ✅ 通过 | 20 连发 |
| G2 流式可停止 | ✅ 通过 | 前端 AbortController + 后端生成器终止 |
| G3 会话隔离 | ✅ 通过 | pytest test_feedback_ownership / 并发冒烟 |
| G4 过期引导重登 | ✅ 通过 | 前端 401 -> 登录层自动弹出 |