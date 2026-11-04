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
