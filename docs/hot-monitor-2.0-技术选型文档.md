# hot-monitor 2.0 技术选型文档

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 撰写日期 | 2026-08-05 |
| 关联文档 | 《hot-monitor 项目代码分析报告》《重构方案》《PRD 2.0》 |
| 文档目的 | 为 2.0 重构的每一个技术决策点提供候选对比、决策结论、理由与回退方案，作为研发实施与 Code Review 的依据 |

---

## 一、选型原则

在逐项选型前，先冻结四条决策原则，后续所有对比按此裁决：

1. **生态匹配优先**：AI + 爬虫场景 Python 生态是不可替代的主战场；前端则跟随 React/Next.js 主流生态，不选小众方案。
2. **简单可演进**：当前是单用户/小团队规模，选型满足当下复杂度，但每个组件必须存在"规模扩大后的标准升级路径"（如 APScheduler → Celery）。
3. **运维成本最小化**：组件总数受控——一个数据库、一个 Redis、不引入消息队列/K8s 等重资产。
4. **契约与类型安全**：链路两端（Python 模型 ↔ TS 类型）必须可自动生成、同源同步，杜绝手工对齐（1.0 的教训）。

---

## 二、选型总览

| 层 | 决策 | 关键备选（落选） |
|---|---|---|
| 前端框架 | **Next.js 15（App Router）+ React 19 + TypeScript** | 保留 Vite SPA、Remix |
| 前端样式/组件 | **Tailwind CSS 4 + shadcn/ui + 保留 Aceternity 特效** | Ant Design、MUI |
| 前端服务端状态 | **TanStack Query v5** | SWR、Redux Toolkit Query |
| 前端客户端状态 | **URL searchParams + 少量 Zustand** | Redux、Jotai |
| 前后端契约 | **OpenAPI（FastAPI 原生）+ openapi-typescript** | tRPC、手写类型 |
| 后端框架 | **FastAPI 0.115+** | Django Ninja、Litestar、Flask |
| ASGI 服务器 | **Granian（或 Uvicorn）** | Hypercorn、Daphne |
| ORM | **SQLModel（SQLAlchemy 2.0 内核）** | 裸 SQLAlchemy、Tortoise ORM |
| 主数据库 | **PostgreSQL 16**（本地开发可用 SQLite） | 继续用 SQLite、MySQL |
| 缓存/锁/广播 | **Redis 7** | 进程内存态、RabbitMQ |
| 任务调度 | **APScheduler 4 + Redis 分布式锁** | Celery、Dramatiq、arq |
| 异步 HTTP | **httpx（AsyncClient）** | aiohttp、requests |
| HTML 解析 | **selectolax（主）+ BeautifulSoup（备）** | lxml、pyquery |
| 浏览器渲染兜底 | **Playwright（可选 channel，默认关闭）** | Selenium、scrapy-playwright |
| AI 接入 | **OpenAI Python SDK（base_url 指向 OpenRouter）** | @openrouter/sdk 的 Python 版、LangChain |
| AI 输出约束 | **structured output（response_format）+ Pydantic 校验** | 正则提取（降级为 fallback） |
| 实时推送 | **FastAPI 原生 WebSocket + Redis Pub/Sub** | python-socketio、SSE |
| 邮件 | **aiosmtplib + Jinja2 模板** | smtplib（阻塞）、yagmail |
| 鉴权 | **API Key 中间件（一期）→ JWT（预留）** | NextAuth、OAuth 全家桶 |
| 日志/配置 | **structlog + pydantic-settings** | loguru、python-dotenv |
| 后端测试 | **pytest + pytest-asyncio + respx（HTTP mock）** | unittest、VCR.py |
| 前端测试 | **Vitest（单测）+ Playwright（E2E，可选）** | Jest、Cypress |
| 部署 | **Docker Compose + Caddy 反代** | Nginx、K8s、Serverless 全家桶 |

---

## 三、前端选型

### 3.1 框架：Next.js 15（App Router）

| 候选 | 优势 | 劣势 |
|---|---|---|
| **Next.js 15 ✅** | RSC 首屏 SSR 直出（热点列表天然适合）；App Router 按页面拆包；Route Handlers 可做 BFF；Vercel 一键部署；生态最大 | 学习成本（RSC 心智模型）；服务端组件与 WS 等客户端逻辑需明确分层 |
| 保留 Vite SPA（1.0 方案） | 零迁移成本 | 首屏全客户端渲染有白屏；路由/数据获取全手工；无法解决 App.tsx 巨型组件问题 |
| Remix | 数据加载模型优秀 | 生态与招聘市场小于 Next.js；RSC 方向与 React 官方路线偏离 |

**决策**：Next.js 15 App Router。渲染策略按页面定：

| 页面 | 策略 | 理由 |
|---|---|---|
| Dashboard `/` | RSC 首屏 SSR + Client 侧增量 | 首屏直出热点列表（LCP 目标 ≤2.5s），WS 推送后客户端接管更新 |
| 关键词管理 `/keywords` | RSC 列表 + Client 表单 | 读多写少 |
| 全网搜索 `/search` | 纯 Client Component | 交互密集、异步任务状态轮询，无 SSR 价值 |

**风险与回退**：RSC 调试复杂度若超预期，可整页降级为 `'use client'` + TanStack Query 客户端取数——仅损失首屏 SSR，功能无损。

### 3.2 服务端状态：TanStack Query v5

| 候选 | 结论 |
|---|---|
| **TanStack Query v5 ✅** | 缓存/失效/轮询/乐观更新一体；`invalidateQueries` 与 WS 推送天然配合（收到 `hotspot:new` → 失效重取 + 头部插入）；DevTools 友好 |
| SWR | 轻量但能力子集，乐观更新与分页缓存管理弱 |
| Redux Toolkit + RTK Query | 对本项目过重；样板代码多 |

关键约定：所有列表查询 `staleTime: 30s`；筛选条件全部进 URL searchParams（useSearchParams），queryKey 与 URL 同步——**刷新保持、可分享、服务端可预取**，同时消灭 1.0 中 20 个 useState 的散乱状态。

### 3.3 样式与组件：Tailwind CSS 4 + shadcn/ui + Aceternity

- **Tailwind 4**：1.0 已用，Oxide 引擎构建快，CSS-first 配置；
- **shadcn/ui**：补标准控件（Dialog 二次确认、DropdownMenu、Toast、Badge）——源码复制进项目、可随意改，与 Tailwind 原生融合；不选 AntD/MUI 是因为主题定制成本高且与暗色科技感风格冲突；
- **Aceternity 特效组件**（Spotlight/BackgroundBeams/Meteors/MovingBorder）：纯 CSS/JS 实现，从 1.0 直接迁移，保持视觉延续（PRD §7.4 要求）；
- 动画沿用 **framer-motion**（1.0 已用，列表入场/布局动画成熟）。

### 3.4 前后端契约：OpenAPI + openapi-typescript

- FastAPI 自动产出 `openapi.json` → CI 中跑 `openapi-typescript` 生成 `api-types.ts` → 前端 fetch 封装直接引用；
- **不选 tRPC**：tRPC 要求前后端同仓 TS，与"Python 后端"前提冲突；
- 生成产物提交进仓库并在 CI 做 diff 检查，契约漂移直接报错。

### 3.5 实时推送客户端

原生 `WebSocket` API + 自研 hook（`use-hotspot-socket`）：指数退避重连（1s→2s→…→30s 封顶）、重连后全量刷新一次、页面隐藏时暂停心跳。**不引入 socket.io-client**——后端已决定用原生 WS（见 §5.4），避免协议错配。

---

## 四、后端框架与运行时

### 4.1 Web 框架：FastAPI

| 候选 | 优势 | 劣势 |
|---|---|---|
| **FastAPI ✅** | 原生 async（采集/AI 全是 IO 密集）；Pydantic 深度集成（请求/响应/AI 输出一套模型）；OpenAPI 自动生成（契约原则的直接兑现）；WebSocket 原生支持；生态与社区最活跃 | 全局依赖注入体系需要团队约定，否则易散 |
| Django + Ninja/DRF | Admin、ORM、全家桶齐全 | 同步基因，async 支持是后补；Admin 对本项目无价值；体量过重 |
| Litestar | 性能更高、设计现代 | 生态/资料/招聘面窄，违背主流原则 |
| Flask | 简单 | 无原生 async、无类型驱动契约，2.0 全部核心诉求都要靠第三方拼装 |

**决策**：FastAPI（≥0.115，Pydantic v2 体系）。

### 4.2 ASGI 服务器：Granian（或 Uvicorn）

- **Uvicorn** 是事实标准、文档示例最多，作为基线；
- **Granian**（Rust 实现）在同机压测中吞吐显著更高且支持 HTTP/WS 一体，作为生产推荐；
- 二者接口等价，启动命令一行切换，**不做强绑定**：Dockerfile 默认 Granian，本地 `fastapi dev`（uvicorn）。

### 4.3 ORM：SQLModel

| 候选 | 结论 |
|---|---|
| **SQLModel ✅** | SQLAlchemy 2.0 内核 + Pydantic 表模型合一：表定义、API schema、AI 输出 schema 风格统一，模型层代码量最小；作者即 FastAPI 作者，协同最佳 |
| 裸 SQLAlchemy 2.0 | 能力全集但样板多，需手工维护 ORM 类 + Pydantic 类两份 |
| Tortoise ORM | Django 风格、轻，但生态与 Alembic 集成成熟度不及 SQLAlchemy 系 |
| prisma-client-py | 非官方主线维护，生态风险高 |

迁移工具：**Alembic**（SQLAlchemy 标准），CI 校验迁移与模型一致。1.0 的 SQLite 历史数据用一次性脚本迁移并回填 `hot_score`/`importance_rank`（重构方案 §3.3）。

### 4.4 主数据库：PostgreSQL 16

| 维度 | 说明 |
|---|---|
| 为什么换掉 SQLite | ① 热点表筛选维度多，需要复合索引（`created_at, importance_rank, hot_score`）；② JSONB 存原始报文（`raw_payload`）便于排查重分析；③ 为并发写（流水线落库 + 用户删除）提供真正的行级锁；④ 全文检索（tsvector）在 backlog，PG 留了路 |
| 为什么不是 MySQL | JSONB、部分索引、窗口函数生态 PG 更顺；团队无 MySQL 既有资产 |
| 开发体验 | SQLModel 双兼容：本地无 Docker 时可 `DATABASE_URL=sqlite:///dev.db` 跑通；CI 与生产一律 PG |

### 4.5 Python 版本与依赖管理

- **Python 3.12**：性能与语法（type 语句、改进的错误信息）均衡，所有目标库均已支持；
- 依赖管理：**uv**（`uv.lock` 锁文件，解析速度远快于 pip/poetry，兼容 `pyproject.toml` 标准）；不选 Poetry（非标准构建后端历史包袱）、不选 pip-tools（手工步骤多）。

---

## 五、异步、任务与实时

### 5.1 任务调度：APScheduler 4 + Redis 分布式锁

| 候选 | 结论 |
|---|---|
| **APScheduler 4（AsyncIOScheduler）✅** | 与 FastAPI 同进程，cron 触发 `run_hotspot_check`；进程内直接调 pipeline，零序列化成本；满足单实例部署现状 |
| Celery + Redis | 分布式任务标准答案，但需额外 worker 进程 + 结果后端，当前规模属于过度设计 |
| Dramatiq / arq | 更轻，但同样引入独立 worker 运维面 |

**互斥设计**（修复 1.0 重入问题）：触发点只做一件事——`SET hotspot_check_lock <run_id> NX EX 1800`，抢到锁才真正执行；手动触发 API 抢不到锁返回 409 + 当前进度。锁的 TTL（30 分钟）大于单轮上限（PRD：单关键词 ≤5 分钟 × 关键词数预估），并配合看门狗续期。

**升级路径**（原则 2 的兑现）：关键词数 >50 或单轮 >30 分钟时，把"触发器"与"执行器"拆开——APScheduler 只投任务到 Redis 队列，独立 worker（arq/Dramatiq）消费。接口边界在设计时已按此预留（`run_hotspot_check(ctx)` 无 web 层依赖）。

### 5.2 Redis 7 的三个角色

| 角色 | Key 设计 | TTL |
|---|---|---|
| 任务互斥锁 | `lock:hotspot_check` | 30min（看门狗续期） |
| AI 结果缓存 | `ai:analysis:{sha256(content)}` → JSON | 30 天 |
| 查询扩展缓存 | `ai:expand:{keyword}` → JSON 数组 | 7 天 |
| WS 多实例广播 | Pub/Sub channel `ws:hotspots` / `ws:notifications` | — |

单容器即可承载，不引入 RabbitMQ/Kafka。

### 5.3 并发模型：asyncio 全链路

- 采集：6 源 `asyncio.gather(return_exceptions=True)`，每源独立 `asyncio.Lock` 实现最小间隔限流（替代 1.0 的 RateLimiter 类）；
- AI 分析：`asyncio.Semaphore(3)` 限制并发（沿用 1.0 的 batchSize=3 经验值，做成配置）；
- 超时纪律：所有外呼 `httpx.Timeout(15s)`，AI 调用 `60s`，整体单关键词有 deadline；
- **不引入多进程**：IO 密集场景 asyncio 足够；CPU 密集操作（HTML 解析）量级小，必要时 `loop.run_in_executor`。

### 5.4 实时推送：原生 WebSocket + Redis Pub/Sub

| 候选 | 结论 |
|---|---|
| **FastAPI 原生 WS ✅** | 需求仅为"服务端 → 客户端广播"（hotspot:new / notification / task 状态），无房间外的复杂语义；FastAPI 原生支持，零额外依赖 |
| python-socketio | 自动重连/房间/降级开箱即用，但协议私有、前后端都被绑定；重连逻辑前端 hook 自己实现成本可控 |
| SSE | 单向推送够用且更简单，但无法承载"客户端订阅关键词列表"的上行语义（需额外 POST），两种通道并存反而复杂 |

协议信封：`{"event": "hotspot:new|notification|task:update", "data": {...}}`。多实例扩展：各实例订阅 Redis channel 再扇出给本机连接——当前单实例也用同一通道，天然兼容未来水平扩容。

---

## 六、采集层（爬虫）选型

### 6.1 HTTP 客户端：httpx

| 候选 | 结论 |
|---|---|
| **httpx ✅** | 同步/异步同一 API；HTTP/2；超时/重试/代理配置现代；FastAPI 生态事实标准 |
| aiohttp | 性能相当，API 繁琐（ClientSession 生命周期管理易踩坑） |
| requests | 无 async，直接排除 |

统一封装 `HttpClient`：UA 池随机、每源最小间隔限流、默认 `timeout=15s`、`follow_redirects=True`、错误分类（网络/状态码/解析）写入 SourceHealth。

### 6.2 HTML 解析：selectolax 主 + BeautifulSoup 备

| 候选 | 结论 |
|---|---|
| **selectolax ✅（主）** | C 实现，解析速度较 BS4 快 10 倍+，CSS 选择器语法；Bing/搜狗等列表页解析性能敏感 |
| **BeautifulSoup4（备）** | 1.0 Agent Skill 的 Python 脚本已用 BS4，平移期零改动；容错性强，适合结构脏的页面 |
| lxml | 性能介于两者之间，API 偏底层 |
| parsel/Scrapy | Scrapy 全家桶对本项目过重（pipeline 只有 6 个源、每源 1-2 个页面） |

约定：选择器失效抛 `SelectorDriftError`（而非静默返回空列表——1.0 的核心教训），统一由 SourceHealth 记录并触发 R-303 告警。

### 6.3 浏览器渲染兜底：Playwright（可选，默认关闭）

- 用途：某源改版为强 JS 渲染或风控升级时的逃生通道（配置 `COLLECTOR_X_CHANNEL=playwright` 切换）；
- 不选 Selenium（API 老旧、无原生 async）；不默认开启（资源重、部署镜像 +300MB，docker 中按需安装浏览器）。

### 6.4 各数据源技术路径确认（继承 1.0 经验）

| 源 | 路径 | 关键技术点（已在 1.0 验证） |
|---|---|---|
| Twitter | twitterapi.io 第三方 API | 高级搜索语法（since/min_faves/-filter:retweets）、Top+Latest 双轨、本地质量过滤（蓝 V 阈值减半） |
| Bing | HTML 爬虫 | UA 池 + 5s 限流 + `li.b_algo` 选择器 |
| HackerNews | Algolia 官方 API | `numericFilters` 限定 24h，最稳定的一个源 |
| 搜狗 | HTML 爬虫 | 相对链接补全、广告位过滤 |
| B 站 | 公开 API | 随机 `buvid3` cookie 规避 412；`search_type=bili_user` 账号检测；`x/space/arc/search` 拉 UP 主视频 |
| 微博 | 热搜榜公开接口 | 双向包含匹配，监控而非搜索 |

---

## 七、AI 层选型

### 7.1 接入方式：OpenAI Python SDK 指向 OpenRouter

| 候选 | 结论 |
|---|---|
| **OpenAI SDK（`base_url=https://openrouter.ai/api/v1`）✅** | 事实标准接口；换 Provider（DeepSeek 官方/通义/自建 vLLM）只改 base_url+key，兑现"Provider 可切换"目标；Python 侧维护质量高于任何第三方封装 |
| OpenRouter 官方 SDK | 1.0 TS 版在用，但 Python 侧生态与文档弱于 OpenAI SDK |
| LangChain/LlamaIndex | 本项目无 RAG/链式编排需求，引入即过度设计；prompt 模板用普通 Python f-string/Jinja2 管理即可 |

模型默认值沿用 `deepseek/deepseek-v3.2`（成本/质量均衡，1.0 已验证），配置项化。

### 7.2 输出约束：structured output + Pydantic

- 首选 `response_format={"type": "json_schema", ...}`（OpenRouter 已支持结构化输出），直接约束模型输出到 `AIAnalysis` schema；
- Pydantic 校验失败 → 降级路径：正则提取 JSON（保留 1.0 防御逻辑）→ 字段钳制（relevance 钳 0–100、importance 白名单）→ 仍失败则进重试队列（R-205）；
- 温度 0.2、输入截断 2000 字符、maxTokens 500（分析）/300（扩展）——全部沿用 1.0 调好的参数并配置化。

### 7.3 成本控制三件套的实现归属

| 机制 | 实现位置 |
|---|---|
| 配额前置（≤25 次/关键词/轮） | pipeline Stage 6（重构方案 §4.1） |
| 内容哈希缓存 | Redis `ai:analysis:*`，analyze 前查、后写 |
| 查询扩展缓存 | Redis `ai:expand:*`，替代 1.0 进程内 Map（重启不丢、多实例共享） |

---

## 八、横切关注点

### 8.1 鉴权：API Key（一期）→ JWT（预留）

- 一期：环境变量 `API_KEYS=k1,k2` → FastAPI 依赖项校验 `X-API-Key` header；WS 握手 query param 校验；前端把 key 存于服务端环境变量，经 BFF Route Handler 转发（**key 不下发浏览器**）；
- 预留：`users` 表 + Keyword.owner_id 已在 schema 设计内；二期接 `fastapi-users`（JWT）时 API 层依赖项可整体替换，业务路由零改动。

### 8.2 配置与日志

- **pydantic-settings**：启动时校验全部环境变量（OPENROUTER_API_KEY、SMTP_*、DATABASE_URL、REDIS_URL、API_KEYS），缺失即启动失败并打印缺失清单——修正 1.0"静默降级"行为；
- **structlog**：JSON 结构化日志，注入 `run_id`/`keyword`/`source` 上下文字段，单轮检查全过程可按 `run_id` 追溯（PRD §6 可观测要求）。

### 8.3 邮件：aiosmtplib + Jinja2

- `smtplib` 阻塞，pipeline 是 async 的——必须 aiosmtplib（或 `run_in_executor` 包 smtplib，前者更干净）；
- Jinja2 模板渲染邮件 HTML，**自动转义**（修复 1.0 邮件 XSS 隐患）；模板文件独立存放，可预览测试。

### 8.4 测试

| 层 | 工具 | 覆盖重点 |
|---|---|---|
| 后端单测 | **pytest + pytest-asyncio** | scoring/过滤阈值/配额逻辑/查询扩展 fallback（对应 1.0 已验证的"测纯函数"策略） |
| 后端 HTTP mock | **respx**（httpx 专用 mock） | collectors 用录制好的 HTML/JSON fixture 测解析，选择器漂移可测出 |
| 后端集成 | testcontainers（PG+Redis）或 docker compose 起依赖 | 迁移脚本、鉴权中间件、锁竞争 |
| 前端单测 | **Vitest** | 工具函数、hook 逻辑 |
| E2E（可选） | **Playwright** | 核心链路：加关键词 → 手动触发 → 看到热点 |

### 8.5 代码质量工具

- 后端：**ruff**（lint+format 一体，替代 black+isort+flake8）、**mypy**（strict 渐进）；
- 前端：**eslint 9 + typescript-eslint**、Prettier；
- Git 钩子：**pre-commit**（后端 ruff/mypy、前端 lint-staged）；
- CI：GitHub Actions——后端 pytest + ruff + mypy，前端 tsc + eslint + build，openapi-typescript diff 检查，docker build。

---

## 九、部署与基础设施

### 9.1 容器化与编排：Docker Compose

| 服务 | 镜像/构建 | 说明 |
|---|---|---|
| web | Next.js standalone 多阶段构建 | 输出独立 node 产物，镜像 ~150MB |
| api | python:3.12-slim + uv 安装 + granian | 默认不含 Playwright 浏览器（按需构建变体） |
| db | postgres:16-alpine + named volume | 每日 `pg_dump` 备份挂载卷（cron 容器或宿主机 cron） |
| redis | redis:7-alpine + AOF 持久化 | AI 缓存丢失可重建，锁与 Pub/Sub 需短暂可用性 |
| caddy | caddy:2 | 自动 HTTPS；`/` → web:3000，`/api`、`/ws` → api:8000 |

### 9.2 反向代理：Caddy 而非 Nginx

自动证书、配置 10 行 vs Nginx 的样板量；WS 反代无需额外 upgrade 头配置。团队若已有 Nginx 资产可平替——无功能差异。

### 9.3 前端部署的两条路径

- **路径 A（推荐起步）**：全部上 VPS，docker compose 一体部署；
- **路径 B**：web 上 Vercel（免费额度 + 全球 CDN），api/db/redis 留 VPS——需要处理跨域与 WS 直连后端域名，适合流量增长后。

---

## 十、关键版本锁定建议

| 组件 | 版本 | 备注 |
|---|---|---|
| Python | 3.12.x | uv 管理 |
| Node.js | 20 LTS | Next.js 15 要求 ≥18.18 |
| Next.js / React | 15.x / 19.x | App Router |
| FastAPI / Pydantic | ≥0.115 / v2.x | |
| SQLModel | ≥0.0.22 | SQLAlchemy 2.0 内核 |
| PostgreSQL / Redis | 16 / 7 | alpine 镜像 |
| httpx / selectolax | ≥0.27 / ≥0.3 | |
| openai (Python) | ≥1.x | base_url 指 OpenRouter |
| TanStack Query | v5 | |
| Tailwind CSS | 4.x | @tailwindcss/vite 或 PostCSS |
| APScheduler | 4.x（AsyncIOScheduler） | 注意 4.x 与 3.x API 不兼容，直接上 4 |
| Granian | ≥1.x | 生产；本地 uvicorn |

> 版本在 M1 开工时以 `uv.lock` / `package-lock.json` 实际锁定为准，本表给出的是选型约束（主版本线），不是死值。

---

## 十一、风险与回退矩阵

| 选型 | 主要风险 | 回退方案 |
|---|---|---|
| Next.js RSC | 服务端/客户端组件边界踩坑拖慢 M3 | 整页降级 `'use client'`，只损失 SSR |
| SQLModel | 个别高级查询表达力不足 | 该处直接下钻 SQLAlchemy Core/裸 SQL（同一引擎共存） |
| APScheduler 同进程 | web 进程重启会中断在跑任务 | 锁 TTL 自动释放，下一轮 cron 补跑；规模到位后迁 arq/Dramatiq |
| 原生 WS（无 socket.io） | 弱网重连体验需自研 | hook 内指数退避 + 重连全量刷新；极端情况换回 python-socketio（协议信封不变） |
| selectolax | 个别脏 HTML 容错不如 BS4 | 该 collector 单独切回 BeautifulSoup（基类已抽象） |
| OpenRouter 结构化输出不稳定 | 模型侧 schema 遵从度漂移 | 降级正则提取 + Pydantic 钳制（fallback 链已实现） |
| Caddy | 团队熟悉度低 | 平替 Nginx，仅配置工作量差异 |
| Redis 单点 | 宕机导致锁/缓存/广播失效 | AOF + 容器自动重启；缓存可重建、锁有 TTL、WS 广播短暂中断可接受 |

---

## 十二、决策记录摘要（ADR 速查）

| # | 决策 | 一句话理由 |
|---|---|---|
| ADR-1 | 前端迁 Next.js App Router | SSR 首屏 + 强制组件分层，根治巨型 SPA |
| ADR-2 | 后端迁 FastAPI | async 全链路 + Pydantic 契约，AI/爬虫生态主战场 |
| ADR-3 | SQLite → PostgreSQL | 复合索引 + JSONB + 并发写，消灭全表内存排序 |
| ADR-4 | 引入 Redis 三角色 | 一把钥匙开三把锁：任务互斥、AI 缓存、WS 广播 |
| ADR-5 | APScheduler 同进程 + 分布式锁 | 最小运维满足互斥诉求，worker 化路径预留 |
| ADR-6 | OpenAI SDK 指 OpenRouter | Provider 切换零代码，structured output 免费获得 |
| ADR-7 | 原生 WebSocket + 自研重连 | 推送语义简单，不为重连引入协议绑定 |
| ADR-8 | OpenAPI 生成 TS 类型 | 前后端类型同源，消灭手工对齐 |
| ADR-9 | selectolax 主、BS4 备 | 性能与容错的分层，选择器漂移显式告警 |
| ADR-10 | Docker Compose + Caddy | 单 VPS 一键部署，自动 HTTPS，K8s 留待真正的规模信号 |
