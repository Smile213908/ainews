# hot-monitor 2.0 实施进度表

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 撰写日期 | 2026-08-05 |
| 撰写视角 | 全栈技术负责人（面向排期与执行） |
| 依据文档 | 《PRD 2.0》《技术选型文档》《重构方案》《项目代码分析报告》 |
| 总工期 | **约 17 个工作日（含缓冲）**，2026-08-06（周四）启动 → 2026-08-28（周五）上线 |

---

## 一、需求点与技术要点理解（排期的依据）

### 1.1 四个必须修复的高危问题（P1–P4）

| # | 问题 | 落到哪个任务 |
|---|---|---|
| P1 | 无鉴权，无法公网部署 | M1-T3 API Key 中间件 + WS 握手校验 |
| P2 | AI 调用量无硬约束 | M2-T6 配额前置（Stage 6，≤25 次/关键词/轮） |
| P3 | 定时任务并发重入、搜索同步阻塞 | M2-T7 Redis 分布式锁；M4-T1 搜索异步任务化 |
| P4 | 源失效静默、热度口径双份 | M2-T2 SourceHealth + SelectorDriftError；M1-T2 预计算列 `hot_score`/`importance_rank` |

### 1.2 影响排期的关键技术决策

1. **契约先行**：M1 第 2 天冻结 SQLModel 模型与 OpenAPI 初稿——之后后端流水线（M2）与前端（M3）可并行开发，这是压缩总工期的关键路径。
2. **预计算列消灭内存排序**：`hot_score`/`importance_rank` 落库时写入 + 信息流复合索引 `ix_hotspot_feed`，是 M1 数据模型的核心改动，后续所有列表接口受益。
3. **采集器插件化**：6 个源共用 `Collector` Protocol + 统一 HttpClient（UA 池/限流/错误分类），先搭框架再逐个平移，单源失败隔离与告警天然获得。
4. **AI 层 fallback 链**：structured output → 正则提取 → 字段钳制 → 重试队列（R-205），是 M2 中工作量最集中、风险最高的部分，单独占 1.5 天。
5. **灰度切换不停工**：M2 期间新系统只落库不通知，与 1.0 并行 ≥2 轮对比一致后切流——灰度不占排期日历，但占 M2 出口标准。

### 1.3 范围纪律（防止蔓延）

严格执行 PRD §3.2：多用户 UI、日报邮件、全文检索、热点聚类、移动端 **一律进 backlog**。 schema 只预留 `owner_id`，不做任何账号体系 UI。

---

## 二、里程碑总览

| 里程碑 | 内容 | 工期 | 日期（工作日） | 出口标准 |
|---|---|---|---|---|
| M0 | 工程准备 | 1 天 | 08-06（四） | 依赖可起、CI 绿灯、两端空壳可跑 |
| M1 | 后端骨架 | 4 天 | 08-07（五）– 08-12（三） | 只读 API + 鉴权生效；迁移脚本抽验通过；**API 契约冻结** |
| M2 | 监控流水线 | 5 天 | 08-13（四）– 08-19（三） | 新系统独立完成全量检查；AI 调用量可审计且不超上限；灰度对比一致 |
| M3 | 前端重构 | 4 天 | 08-14（五）– 08-19（三）※与 M2 并行 | 功能对等 1.0；LCP ≤2.5s；筛选 URL 化 |
| M4 | 增强与收尾 | 3 天 | 08-20（四）– 08-24（一） | 搜索异步化；源健康面板；docker-compose 一键部署 |
| — | 联调缓冲 + Go/No-Go | 4 天 | 08-25（二）– 08-28（五） | 上线检查单全绿，正式发布 |

> **并行策略**：M1 结束时 OpenAPI 契约冻结，M2（后端流水线）与 M3（前端）随即并行。若只有 1 人开发，按 M2 → M3 串行执行，总工期 +2 天（08-28 前仍可控，缓冲自行消化）。

---

## 三、逐日任务分解

### M0 工程准备（08-06，1 天）

| # | 任务 | 产出 | 依赖 |
|---|---|---|---|
| M0-T1 | backend 初始化：uv + pyproject（fastapi/sqlmodel/httpx/redis/apscheduler4/structlog/openai/aiosmtplib），ruff + mypy + pre-commit | `backend/` 可运行空壳 FastAPI | — |
| M0-T2 | frontend 初始化：Next.js 15 + TS + Tailwind 4 + shadcn/ui + TanStack Query | `frontend/` 可运行空壳 | — |
| M0-T3 | 开发依赖容器化：PG 16 + Redis 7 的 docker-compose（仅依赖，不含应用） | 本地 `docker compose up db redis` 可用 | — |
| M0-T4 | CI 骨架：后端 pytest/ruff/mypy、前端 tsc/eslint/build 两条流水线 | GitHub Actions 绿灯 | T1/T2 |

### M1 后端骨架（08-07 – 08-12，4 天）

| # | 任务 | 关键细节 | 对应规则 |
|---|---|---|---|
| M1-T1（D1） | SQLModel 数据模型 + Alembic 初始迁移 | Keyword/Hotspot/Notification/Setting/**SourceHealth**；`raw_payload` JSONB；预留 `owner_id`；CHECK 约束 relevance 0–100 | 重构方案 §3.1 |
| M1-T2（D1） | 预计算列与索引 | 落库钩子写 `hot_score`/`importance_rank`；复合索引 `ix_hotspot_feed(created_at, importance_rank, hot_score)` | R-401/R-402 |
| M1-T3（D2） | API Key 鉴权中间件 + 配置校验 | `X-API-Key` header；WS query param 校验；pydantic-settings 启动缺失即报错 | FR-7.1，修复 P1 |
| M1-T4（D2） | 只读 API：hotspots 分页（全 DB 排序）+ stats + keywords 列表（含热点计数） | 5 种排序全部 `ORDER BY` + 真分页；时间范围/来源/重要性/关键词/真实性筛选参数 | FR-2.1/2.4/2.5 |
| M1-T5（D3） | 写 API：关键词 CRUD + toggle + 通知 CRUD | 重复关键词 409；删除关键词不级联热点；通知已读/清空 | FR-1、FR-4.3 |
| M1-T6（D3） | **OpenAPI 契约冻结** + openapi-typescript 生成首版类型 | 生成产物入库，CI diff 检查 | ADR-8 |
| M1-T7（D4） | SQLite→PG 迁移脚本 | 逐表迁移 + `hot_score`/`importance_rank` 回填；抽验 100 条一致性 | 重构方案 §3.3 |
| M1-T8（D4） | pytest 基线：scoring/排序/鉴权单测 | 纯函数优先 | 选型 §8.4 |

**出口**：旧前端（如有需要）指向新后端可用；迁移数据抽验通过；契约冻结，M2/M3 开工。

### M2 监控流水线（08-13 – 08-19，5 天）

| # | 任务 | 关键细节 | 对应规则 |
|---|---|---|---|
| M2-T1（D1） | collectors 框架 | `Collector` Protocol + registry；统一 HttpClient（UA 池/每源限流/timeout 15s/错误分类）；`SelectorDriftError` | R-103 |
| M2-T2（D1） | SourceHealth 机制 | 每源成功/失败落表；`/api/sources/health` 只读 API | FR-6.3，修复 P4 |
| M2-T3（D2–D3） | 6 源采集器逐个实现 | HN（Algolia API，最稳，先打通）→ 微博热搜（双向包含）→ B 站（buvid3 + UP 主检测）→ Bing → 搜狗（selectolax）→ Twitter（twitterapi.io，质量过滤 + Top/Latest 双轨）；每源配 fixture 测试 | R-103~R-107 |
| M2-T4（D3–D4） | AI 层 | Provider 抽象（OpenAI SDK 指 OpenRouter）；structured output + Pydantic；降级链（正则→钳制→重试队列）；内容哈希缓存（30 天）；查询扩展（缓存 7 天 + 规则法 fallback） | R-201/203/205/206/207 |
| M2-T5（D4） | pipeline 8 阶段编排 | 账号检测→扩展→6 源 gather→清洗→批量查重（修 N+1）→**配额前置**→AI Semaphore(3)→过滤落库 | R-202，修复 P2 |
| M2-T6（D5） | Redis 分布式锁 + APScheduler 4 | `SET NX EX 1800` + 看门狗；手动触发 409 + 进度；30 分钟 cron | R-101/R-102，修复 P3 |
| M2-T7（D5） | 邮件通知 + WS 推送通道 | aiosmtplib + Jinja2（自动转义）；仅 high/urgent；原生 WS + Redis Pub/Sub，信封 `{event, data}` | R-301/302，FR-5 |

**出口**：新系统独立完成一轮全量检查；**灰度**：只落库不通知，与 1.0 并行 ≥2 轮，同关键词双边产出过滤判定一致性 ≥90% 后切流。

### M3 前端重构（08-14 – 08-19，4 天，与 M2 并行）

| # | 任务 | 关键细节 | 对应规则 |
|---|---|---|---|
| M3-T1（D1） | 工程基座与视觉延续 | 暗色主题 layout；Aceternity 特效迁移（Spotlight/Beams/Meteors）；shadcn/ui 标准控件；API key 经 BFF Route Handler 转发（不下发浏览器） | PRD §7.4，选型 §8.1 |
| M3-T2（D1–D2） | Dashboard RSC 首屏 | 统计概览 SSR 直出；hotspot-card 纯渲染组件（AI 摘要标注、热度分用后端归一化值、可疑标）；热度等级标签由后端分值驱动 | FR-2.1/2.2，R-403 |
| M3-T3（D2–D3） | 信息流交互 | 筛选条件全进 URL searchParams（刷新保持/可分享）；TanStack Query（staleTime 30s）分页重取；全部展开/折叠；删除二次确认 | FR-2.3/2.4/2.5/2.7 |
| M3-T4（D3） | 关键词管理页 | RSC 列表 + Client 表单；激活/暂停；创建即订阅 WS 房间 | FR-1 |
| M3-T5（D4） | 实时与通知 | `use-hotspot-socket` hook（指数退避 1s→30s、重连全量刷新、隐藏暂停心跳）；通知铃铛 + 角标 + 下拉面板；toast 零打扰 | FR-2.6，FR-4 |
| M3-T6（D4） | 搜索页（同步版先行） | 纯 Client 页 + 复用筛选排序组件，M4 再异步化 | FR-3.1/3.3 |
| M3-T7（D4） | LCP 达标 + Vitest | 首屏 ≤2.5s；空状态设计（引导创建/监控中状态） | PRD §6、§7.5 |

**出口**：功能对等 1.0 前端；筛选 URL 化；LCP 达标。

### M4 增强与收尾（08-20 – 08-24，3 天）

| # | 任务 | 关键细节 | 对应规则 |
|---|---|---|---|
| M4-T1（D1） | 搜索异步任务化 | `POST /api/hotspots/search` 返回 task_id（≤1s）；任务状态机（排队/运行/完成/失败，超时 120s）；WS 推送 + 轮询双通道；一键转监控关键词 | FR-3.2/3.4，修复 P3 |
| M4-T2（D1–D2） | 源健康面板 + 告警 | 6 源状态卡（最近成功/连续失败/最近错误）；连续失败 ≥3 标红 + alert 通知（恢复前去重） | FR-6，R-303 |
| M4-T3（D2） | 结构化日志收尾 | structlog 全链路 `run_id` 注入；每轮检查输出关键词数/各源抓取数/AI 调用数/耗时 | PRD §6 可观测 |
| M4-T4（D2–D3） | docker-compose 全套 + Caddy | web/api/db/redis/caddy 五服务；Next.js standalone 构建；每日 pg_dump 备份卷 | 选型 §9.1 |
| M4-T5（D3） | CI 完善 + 部署文档 | openapi diff 检查、docker build；环境变量前置清单（OpenRouter Key/SMTP/Twitter Key 缺失降级行为） | PRD §9 依赖 |

### 联调缓冲 + Go/No-Go（08-25 – 08-28，4 天）

| 日期 | 内容 |
|---|---|
| 08-25（二） | 端到端联调：加关键词 → 定时检查 → WS 推送 → 邮件；buffer 吸收 M2/M3 延期 |
| 08-26（三） | 性能验证：10 万条热点数据量下列表接口 P95 ≤500ms；LCP 复测；AI 成本审计（缓存命中率、单轮调用数 ≤25） |
| 08-27（四） | **Go/No-Go 检查单**：鉴权全量生效 ✅ / 配额硬上限生效 ✅ / 迁移数据抽验 ✅ / 告警链路实测（手动断一个源，30 分钟内收到 alert）✅ / 回滚预案（旧系统保留 2 周可切回）✅ |
| 08-28（五） | 正式上线；观察首轮 30 分钟周期运行；旧系统进入 2 周只读保留期 |

---

## 四、依赖与关键路径

```
M0 ──→ M1（契约冻结）──┬──→ M2 流水线 ──┐
                       └──→ M3 前端 ────┴──→ M4 ──→ 联调/Go-No-Go ──→ 上线
```

- **关键路径**：M0 → M1 → M2 → M4 → 联调。M3 在契约冻结后与 M2 并行，不占关键路径。
- **硬依赖**：M2-T4（AI 层）依赖 M2-T1（HttpClient 封装风格）；M4-T1（搜索异步）依赖 M2-T6（WS 通道与锁）；M3 全部依赖 M1-T6（契约冻结）。
- **外部依赖**（M0 时就位，否则阻塞对应任务）：OpenRouter API Key（M2-T4）、twitterapi.io Key（M2-T3）、SMTP 授权码（M2-T7）。

## 五、风险缓冲

| 风险 | 影响排期 | 预案 |
|---|---|---|
| 爬虫源反爬升级（搜狗/B 站） | M2-T3 +1 天 | 该源先标记降级上线，Playwright 兜底通道后续补；不阻塞整体 |
| RSC 调试复杂度超预期 | M3 +1 天 | 整页降级 `'use client'` + TanStack Query，仅损失 SSR（选型 §3.1 回退） |
| OpenRouter structured output 不稳定 | M2-T4 +0.5 天 | 降级正则提取 + 钳制（fallback 链本来就是交付物） |
| 灰度对比不一致（<90%） | 联调期 -2 天 | 定位过滤规则差异；最差情况保持 1.0 运行，2.0 延迟切流，不影响旧系统 |

## 六、每日站会检查项（建议）

1. 昨天完成的任务是否过验收标准（不是"代码写完"而是"规则书逐条可对上"）；
2. AI 调用量/成本是否有新的审计数据；
3. 是否有范围蔓延苗头（backlog 项被顺手做了）。
