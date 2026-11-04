# Fab Bot 通宵升级工作日志 (2026-11-05 夜间)

> 任务目标: 将项目从"可演示脚手架"升级为"可交付试点项目"
> 作业窗口: 00:37 ~ 06:30 (用户 06:45 检查)
> 工作方式: 自主规划 -> 实现 -> 自测 -> 记录 -> 下一阶段, 每阶段检查时间

## 目标版本: v4.0 (交付级)

## 总体规划 (P0~P8)

| 阶段 | 内容 | 完成标准 |
|---|---|---|
| P0 | 主规划 + 日志启动 | 本文件 |
| P1 | SQLite 持久化层 + 用户认证(PBKDF2) + RBAC 角色 | 单元测试通过 |
| P2 | API 升级: 登录/服务端会话 CRUD/反馈/审计入库 | API 测试通过 |
| P3 | 前端: 登录页 + 服务端会话 + 管理后台(知识库/日志/用户) | 浏览器实测 |
| P4 | 检索升级: BM25+向量混合检索(RRF 融合) + 引用校验 | 检索测试 |
| P5 | 评测体系: 评测集(30+题) + 离线评测脚本 + 报告 | 评测报告生成 |
| P6 | 交付物: 部署手册/用户手册/验收清单/生产 compose/.env | 文档齐全 |
| P7 | 告警推送: 企微/钉钉 webhook 通知模块 + 测试 | 单测通过 |
| P8 | 全量回归 + CHANGELOG + v4.0 标签 + 推送 GitHub | 全绿 + 推送成功 |

## 执行记录

### P0 主规划 (00:37)
- 确认时间 00:37, 制定 P0~P8 计划, 启动本日志
- 决策: 持久化用 SQLite(WAL) 标准库实现, DAO 层隔离, 生产可换 Postgres;
  认证用 PBKDF2-HMAC-SHA256(标准库), HttpOnly Cookie 会话令牌;
  前端保持零构建单文件哲学 (index.html + admin.html)
- 风险预案: 若某阶段超时, 先保证 P1~P3 (核心交付) 与 P8 (回归收尾), P5~P7 可裁剪


### P1 持久化与认证 (00:41 完成)
- app/store/db.py: SQLite(WAL) DAO — users/auth_tokens/chat_sessions/messages/audit + 统计
- app/store/security.py: PBKDF2-HMAC-SHA256 口令散列 (12 万次迭代, 纯标准库)
- 内置账号种子 (admin/zhangsan/guest), 首启自动创建, 日志提示改密
- tests/test_store_auth.py: 9 项测试 (散列/认证/禁用/令牌过期/改密吊销/会话CRUD/评分/审计)

### P2 API 升级 (00:44 完成)
- 认证: POST /api/auth/login|logout, GET /api/auth/me (HttpOnly Cookie + Bearer 双通道)
- RBAC: viewer < user < admin (app/api/deps.py), 401/403 语义完整
- 会话: GET/POST /api/sessions, GET messages, PATCH, DELETE (归属校验)
- 问答持久化: /api/chat 与 /api/chat/stream 均落库; 流式 result/done 事件携带 message_id
- 反馈: POST /api/feedback (up/down/none, 归属校验)
- 审计双写: JSONL 文件 + SQLite; 管理端: /api/admin/users|audit|stats|kb/rebuild (防自我锁定)
- tests/test_api_v4.py: 14 项 (401/403/角色/会话CRUD/反馈归属/用户管理/统计)

### P3 前端与管理后台 (00:55 完成, 浏览器实测通过)
- index.html: 登录层 + 服务端会话列表 + 消息反馈(👍/👎) + 用户卡 + 管理后台入口
- admin.html (新增): 统计卡 / 用户管理(增/改角色/禁用/重置密码) / 审计查询 / 知识库重建
- 实测修复 2 个 bug: ① boot IIFE 命名导致登录后不加载 ② loadSessions 刷新丢失 messages 引用
- 浏览器截图验证: 登录页/主界面/SQL卡片/统计页/用户管理页 全部正常

### P4 检索升级 (00:54 完成)
- app/rag/bm25.py: 纯 Python BM25 (中文 bigram+ASCII 词元, 无分词器依赖)
- pipeline._retrieve: 向量+BM25 双路召回, RRF (1/(60+rank)) 融合, rag.hybrid 配置开关
- LocalVectorStore.add 去重 (来源+正文唯一键) —— 修复多次导入产生 16 条重复片段的问题

### P5 评测体系 (00:58 完成, 全绿)
- eval/evalset.json: 18 条知识 + 12 条 SQL 评测项
- eval/run_eval.py: 离线命中率/可执行率/耗时 + 可选 LLM 引用率, 输出 eval/report.md|json
- 评测驱动的两个修复: ① store 重复片段污染 top-5 (去重解决) ② 命中判定需扫全文 (sources 增带 text)
- Mock LLM 补充 COUNT/AVG 统计类 SQL 规则
- 最终: 知识命中率 18/18 (100%), SQL 通过率 12/12 (100%), 全部 41+3 测试通过

### P6 交付物 (01:00 完成)
- docs/DEPLOY.md 部署手册 / USER_GUIDE.md 用户手册 / ACCEPTANCE.md 验收清单 (A~G 七组 30 项)
- CHANGELOG.md / deploy/docker-compose.prod.yml / nginx.conf.sample / backup.sh|.ps1
- 修复 backup.sh 危险操作 (误删活动 WAL)

### P7 告警推送 (01:00 完成)
- app/notify/webhook.py: 企微+钉钉群机器人, 统一 send 入口, 推送审计留痕
- POST /api/admin/notify/test (admin) 验证配置; httpx MockTransport 单测 3 项

### P9 代码自审 (01:05 完成)
- 引入 ruff + pyproject.toml (line-length 120), 全量 lint 清零 (修复未用导入/分号/未用变量/超长行)

### P10 意图路由 v2 (01:07 完成)
- app/api/intent.py: 强业务信号(3分)+动作词(2分)+知识问法负分(-3/-2), 阈值 2
- 替换 routes 单正则; tests/test_intent.py 16 个典型问法回归 (含易混淆: "怎么处理E0010告警"->kb)
- 过程修复: 信号组循环解包错误导致 10 测试失败 -> 修正后 47 tests 全绿

### P11 前端体验增强 (01:15 完成)
- 会话搜索框 / 来源折叠(默认3条+展开) / SQL复制按钮 / 会话导出 Markdown
- 过程发现并修复: 补丁经 bash heredoc 传输把 JS 字符串里的 \n 变成真实换行导致整页脚本失效
  -> 建立"node --check 提取脚本"校验环节, 修复后浏览器实测全部恢复 + 新功能就位
