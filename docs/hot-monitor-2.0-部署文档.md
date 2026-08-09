# hot-monitor 2.0 部署文档

> 关联：《PRD 2.0》§6 部署需求、《技术选型》§9

## 一、前置清单（PRD §9 依赖）

| 项 | 必需性 | 缺失行为 |
|---|---|---|
| API_KEYS | **必填** | 后端拒绝启动并明确报错 |
| Docker + Docker Compose | 部署必需 | — |
| AI_API_KEY（+AI_BASE_URL/AI_MODEL） | 可选 | AI 分析走降级模式，界面标注"未经 AI 审核"（R-207）；OpenAI 兼容三元组，默认接官方 |
| TWITTER_API_KEY | 可选 | Twitter 源跳过（SourceHealth 不计故障） |
| SMTP_* / MAIL_TO | 可选 | 邮件静默跳过，不影响主流程（FR-5.1） |

## 二、一键部署（单 VPS）

```bash
git clone https://github.com/Smile213908/ainews.git
cd ainews

cp .env.example .env   # 编辑填写 API_KEYS 等
docker compose --profile prod up -d --build
```

服务拓扑：

```
Caddy(:80/:443) ── /api,/ws ──→ api (FastAPI/Granian :8000)
                ── /        ──→ web (Next.js standalone :3000)
api ──→ db (PostgreSQL 16)    api ──→ redis (Redis 7 AOF)
```

- 首次启动 api 容器自动执行 `alembic upgrade head`（建表/迁移）
- 检查周期默认 30 分钟，可在 `PUT /api/settings/check_interval_minutes` 运行时调整

## 三、从 1.0 迁移历史数据

```bash
docker compose --profile prod exec api \
  uv run --no-sync python scripts/migrate_sqlite_to_pg.py \
  --source "sqlite:////data/1.0-dev.db"     # 先把 1.0 的 dev.db 拷入容器或挂载卷
```

- 迁移自动回填 `hot_score` / `importance_rank` 预计算列
- 建议先 `--dry-run` 看统计，原 SQLite 文件保留备份

## 四、本地开发（无 Docker）

```bash
# 后端（SQLite + 内存锁降级，免任何依赖）
cd backend && uv sync && uv run fastapi dev app/main.py

# 前端
cd frontend && npm install && npm run dev
```

## 五、运维要点

| 项 | 位置 |
|---|---|
| 数据源健康 | 前端 `/sources` 页 或 `GET /api/sources/health` |
| 单轮检查追溯 | 结构化日志按 `run_id` 过滤（生产输出 JSON：`LOG_JSON=1`） |
| 数据备份 | `docker compose exec db pg_dump -U hotmonitor hotmonitor > backup.sql` |
| 回滚预案 | 1.0 旧系统保留 2 周，DNS/端口切回即可（PRD 上线检查单） |

## 六、Go/No-Go 检查单（上线前逐项打勾）

- [ ] 鉴权全量生效（无 Key 访问 /api/* 全部 401，WS 握手 4401）
- [ ] 配额硬上限生效（单关键词单轮 AI 调用 ≤25，日志可审计）
- [ ] 迁移数据抽验通过（抽 100 条热点比对字段）
- [ ] 告警链路实测（手动停一个源的网络，30 分钟内收到 alert 通知）
- [ ] 回滚预案就绪（旧系统保留可切回）
