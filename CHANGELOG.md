# 更新日志

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
