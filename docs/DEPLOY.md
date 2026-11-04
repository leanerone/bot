# Fab Bot 部署手册 (v4.0)

> 适用: 工厂内网试点部署 (办公网段, 50 人以内)。全程不需要公网。

## 1. 环境要求

| 项 | 要求 |
|---|---|
| 服务器 | Windows / Linux 均可, 4 核 8G 起步 (不含 LLM 算力) |
| Python | 3.10+ |
| GPU (可选) | 跑真实 LLM 时按 docs/选型与算力评估.md 配置 |
| 网络 | 用户可访问本机端口 8100; 访问 Domino/中间库按需开通 |

## 2. 快速部署 (Mock 模式, 验证部署正确性)

```bash
git clone https://github.com/leanerone/bot.git fabbot && cd fabbot
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

验证: 浏览器打开 `http://<服务器IP>:8100`, 用 admin / admin123 登录
(**首次登录后立即在管理后台改密码**)。

## 3. 生产化配置清单

1. **改默认密码**: 管理后台 → 用户 → admin 重置密码; 逐一创建真实用户。
2. **接入真实模型**: 修改 `config.yaml` → `llm.mock: false`,
   `base_url` 指向 vLLM 服务 (启动命令见 docs/选型与算力评估.md)。
3. **Embedding**: `rag.embedding.provider: openai`, 指向 BGE-M3 服务 (TEI)。
4. **知识导入**: 将 SOP/手册放入 `data/knowledge/`, Notes 导出 JSON 放入
   `data/notes_export/`, 管理后台 → 知识库 → 全量重建。
5. **生产数据**: `sqlbot.db_path` 指向 IT 侧只读中间库 (改造说明见
   app/sqlbot/text2sql.py 头注释); 禁止直连生产库。
6. **审计留存**: `data/app.db` 与 `data/audit.log` 纳入备份。

## 4. Docker 部署 (推荐)

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

包含: bot 应用容器 (端口 8100) + 数据卷 (data/)。vLLM/Embedding 服务
按 GPU 机器单独部署, 通过 `llm.base_url` 指向。

## 5. 日常运维

- **重启**: `python -m uvicorn app.main:app --port 8100` (建议配 systemd/NSSM)
- **备份**: `deploy/backup.ps1` (Windows) / `deploy/backup.sh` (Linux),
  备份 data/ 全目录, 建议每日定时
- **知识库更新**: 覆盖文档后管理后台重建, 或直接「导入常规文档」(自动去重)
- **健康检查**: `GET /api/health`; 日志看 `data/audit.log` + 管理后台审计页
- **评测回归**: `python eval/run_eval.py` (知识命中率 / SQL 通过率)

## 6. 故障排查

| 现象 | 处理 |
|---|---|
| 登录 401 | 确认账号未被禁用 (管理后台→用户); 忘记密码用另一 admin 重置 |
| 回答提示 LLM 不可用 | `llm.mock` 是否 false 而 vLLM 未启动; `curl http://<vllm>/v1/models` |
| 检索结果差 | 管理后台重建知识库; 检查文档是否扫描件 (先 OCR); `python eval/run_eval.py` 看命中率 |
| SQL 查询报错 | 确认 db_path 指向的库存在且为只读账号; 看 audit 表 status=fail 记录 |

## 7. 安全清单 (上线前逐项确认)

- [ ] admin 默认密码已修改; bootstrap_users 中的示例账号已处理
- [ ] 服务器仅办公网可达, 防火墙限制 8100 访问范围
- [ ] SQL 中间库账号为只读
- [ ] data/ 目录备份与保留策略已配置 (按资安要求)
- [ ] HTTPS: 前置 nginx 反代 + 证书 (deploy/nginx.conf.sample)
