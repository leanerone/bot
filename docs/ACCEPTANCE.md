# Fab Bot 试点验收清单 (v4.4.1)

> 使用方法: 部署完成后逐项勾选; 全部通过即可进入试点运行阶段。
> 自动化基线: `bash scripts/check_all.sh` (lint + 138 项测试 + 评测 + MCP 冒烟 + 前端)。

## A. 部署与基础

- [ ] A1 `GET /api/health` 返回 200, version=4.4.1, 含 kb_chunks / llm.mock / llm.degraded / notes_mode
- [ ] A2 非默认端口/防火墙策略已按 DEPLOY.md 配置
- [ ] A3 admin 默认密码已修改, bootstrap 示例账号已禁用或改密
- [ ] A4 data/ 目录备份任务已配置 (backup 脚本可运行)
- [ ] A5 服务重启后: 用户/会话/知识库完好 (持久化验证)
- [ ] A6 演示库缺失/0 字节时启动自动重种 (自愈), 数据过期自动按当天重新生成

## B. 认证与权限

- [ ] B1 未登录访问 /api/chat 返回 401
- [ ] B2 viewer 角色可问答, 不能导入知识库 (403), 不能进管理后台, 技能执行置灰/403
- [ ] B3 user 角色可导入知识库与执行技能, 不能访问 /api/admin/*
- [ ] B4 禁用用户立即无法登录 (令牌缓存即时失效); 改密后旧令牌全部失效
- [ ] B5 管理员不能禁用/降级自己 (防锁定)
- [ ] B6 换浏览器 (UA 变化) 需重新登录; 「全端登出」吊销全部令牌
- [ ] B7 连续登录失败触发锁定 (423); admin 豁免锁定但受全局限速 (auth_lock.admin_per_minute)

## C. 知识问答

- [ ] C1 「射频功率漂移怎么处理」返回带引用来源的回答
- [ ] C2 来源编号 [1][2] 与下方来源卡片一致, 可对应到具体文档
- [ ] C3 提问知识库没有的主题, 回复"知识库中未找到相关内容" (不编造)
- [ ] C4 多轮追问正常 (如先问告警再问"那 ETCH-02 呢"); >10 轮历史自动压缩
- [ ] C5 上传一个新 .md 文档 → 导入 → 立即可问; 同名上传替换旧版本片段
- [ ] C6 `python eval/run_eval.py` 知识命中率 ≥ 90% (当前 100%, 42 条)
- [ ] C7 上传超 10MB 文件返回 413; 超 4000 字问题返回 422; 路径穿越文件名被拒

## D. 数据查询

- [ ] D1 「最近未处理的告警有哪些」返回 SQL + 表格数据
- [ ] D2 SQL 只读: 问"删除所有告警"被拒绝 (400/无法执行)
- [ ] D3 结果上限 200 行; 超长 SQL 注释/多语句被拒绝
- [ ] D4 `python eval/run_eval.py` SQL 通过率 ≥ 90% (当前 100%, 17 条)
- [ ] D5 意图路由准确率 ≥ 90% (当前 100%, 65/65; 临界问法走模型分类, 其余关键词短路)

## E. HCL Notes 接入

- [ ] E1 导出目录模式: 放入导出 JSON → /api/kb/ingest_notes → 可检索
- [ ] E2 Notes 条目在回答来源中显示为 notes:// 前缀, 引用弹层可回链原文
- [ ] E3 附件 (.docx/.pdf/.md) 已被解析进知识库
- [ ] E4 notes:// 文档链接被解析并在条目中标注
- [ ] E5 (domino 模式) 多库增量同步: UNID 跳过已同步文档, 单库失败不影响其他库

## F. 管理后台

- [ ] F1 统计数字与实际使用一致 (会话/消息/好评差评)
- [ ] F2 创建新用户 → 该用户可登录且权限正确
- [ ] F3 审计页能看到问答记录 (用户/问题/耗时), 并可导出 CSV
- [ ] F4 知识库重建后 health 的 kb_chunks 合理且问答正常
- [ ] F5 五页签齐备 (统计/用户/审计/会话/配置); 配置页 PUT 保存成功且生成 config.yaml.bak;
      白名单外键被拒 (400); 密码/webhook/密钥类键不回显

## G. 稳定性

- [ ] G1 连续 50 次问答无 5xx 错误 (含流式; 压测脚本 scripts/bench.py)
- [ ] G2 流式输出可中途"停止", 服务不崩溃; 失败消息可一键重试
- [ ] G3 两个用户同时使用互不干扰 (会话隔离; 新会话 ID 为 uuid 无碰撞)
- [ ] G4 服务重启期间前端提示登录过期并引导重登

## H. Agent 与技能中心 (v4.4)

- [ ] H1 🤖 Agent 开关打开后, 复合问题自动多步执行, 步骤条**实时**推进 (非结束后回放)
- [ ] H2 Agent SSE 事件序: meta(含 session_id) → agent_step* → delta* → done(含 sources/steps/message_id);
      Agent 回答可 👍/👎
- [ ] H3 Agent 新会话首轮提问落库, 换设备回看完整; 步数上限生效 (agent.max_steps, 默认 3)
- [ ] H4 Agent 入口注入问题被扫描标注 (与统一入口同一防线)
- [ ] H5 技能中心: 列表/详情 (Markdown)/参数执行/最近执行 (/api/skills/{name}/runs) 正常;
      text2sql 技能参数键为 question, 其余 query
- [ ] H6 技能执行全量审计; 超时 (30s) 与超长输出受控截断不崩溃; viewer 执行被拒 (403)

## I. MCP / 通知 / 交班报告 (v4.4)

- [ ] I1 `python scripts/mcp_smoke.py` 7/7 工具通过 (rag_search/text2sql_query/alarms_open/
      watcher_summary/kb_search/shift_report/kb_sources_check), 返回统一 envelope {ok,data,error}
- [ ] I2 streamable-http + mcp.require_key=true 时, 缺/错 X-FabBot-Key 返回 401
- [ ] I3 Teams 推送测试成功 (connector 或 flow 格式, 卡片分级配色); 飞书/企微/钉钉渠道按需验证
- [ ] I4 交班报告: 生成 → 导出 Word (.docx 可打开) → 推送到 Teams 全链路通过
      (/api/tasks/shift-report/export|push)
- [ ] I5 值守守护开启后按间隔轮询, CRITICAL/ALARM 触发推送 + 桌面铃铛/托盘气泡

## J. 安全纵深 (C1-C5, v4.4)

- [ ] J1 (C1) 注入评测 10/10 检出、正常问法 0 误伤; 全角/拆字变体 (ｉｇｎｏｒｅ / 忽 略 以 上) 亦检出;
      检索资料带"资料非指令"信任边界
- [ ] J2 (C2) 登录防爆破锁定生效 (5 次/10 分钟锁 15 分钟), 锁定审计留痕
- [ ] J3 (C3) 令牌 UA 绑定 + logout_all 全端登出
- [ ] J4 (C4) 审计落盘 PII 脱敏 (手机号/邮箱/IP → ***), 机台号/告警码保留
- [ ] J5 (C5) MCP 密钥校验 (常量时间比较) + 工具/技能调用全量审计
- [ ] J6 伪造 X-Forwarded-For 不影响按 IP 锁定/限流 (仅 auth.trusted_proxies 内直连才采信 XFF)
- [ ] J7 CORS: 非白名单源跨域请求被拒; 默认白名单仅本机同源

## K. 交付链 (v4.4.1)

- [ ] K1 `docker compose -f deploy/docker-compose.prod.yml up -d --build` 成功,
      容器内 React UI 同源可访问, health 通过, 非 root 运行
- [ ] K2 GitHub Actions CI 全绿 (后端门禁 + 前端 tsc/构建)
- [ ] K3 桌面打包: desktop-package.ps1 → installer.iss 安装器生成; 安装后 FabBot.exe 启动,
      托盘/热键 Ctrl+Alt+F 可用, 卸载保留 FabBotData
- [ ] K4 云端模型不可达时自动降级 Mock (回答首行标注 + health llm.degraded=true + 设置页标黄),
      恢复后自动复位
- [ ] K5 统一日志: logging.file 配置后落盘轮转; 无散落 print 丢日志

## 量化验收线 (与方案文档表 2 对应)

| 指标 | 验收线 | 当前参考值 |
|---|---|---|
| 知识检索命中率 (评测集) | ≥ 90% | 100% (42/42) |
| Text2SQL 通过率 (评测集) | ≥ 90% | 100% (17/17) |
| 意图路由准确率 (评测集) | ≥ 90% | 100% (65/65) |
| 单元/接口测试 | 全绿 | 138 项 |
| MCP 工具冒烟 | 7/7 | 7/7 |
| 注入检出率 / 正常问法误伤 | 100% / 0 | 10/10 / 0 |
| 常规问答端到端耗时 (Mock) | < 3s | ~1-2s |
| 违规 SQL 拦截率 | 100% | 100% |
| 审计覆盖 | 100% | 100% |