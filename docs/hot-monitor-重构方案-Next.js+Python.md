# hot-monitor 重构方案：Next.js + Python 前后端分离架构

> 角色视角：AI 产品架构师
> 基线：hot-monitor 现状代码分析（2026-08-05 版分析报告）
> 目标栈：前端 Next.js（App Router）+ 后端 Python（FastAPI）
> 日期：2026-08-05

---

## 一、重构背景与目标

### 1.1 为什么重构

现状系统（Express 5 + React 19 SPA + Prisma/SQLite）功能闭环完整，但存在以下结构性问题，**靠打补丁修不好，需要架构级调整**：

| 类别 | 现状问题 | 根因 |
|---|---|---|
| 安全 | 全部 API 无鉴权，DELETE / 触发接口完全开放 | 架构中无认证层 |
| 任务调度 | node-cron 与手动触发可并发重入，单进程内存态 | 无任务队列与互斥机制 |
| AI 成本 | 配额按"入库成功"计数而非按 AI 调用计数，成本失控 | 流水线阶段划分不清 |
| 代码复用 | 排序/热度公式前后端两份拷贝且口径已分裂 | 无共享契约层 |
| 可维护性 | App.tsx 单文件 1122 行、20 个 useState | 无组件/状态分层 |
| 爬虫稳定性 | cheerio 解析硬编码选择器，源失效即静默返回 `[]` | 无插件化与源健康监控 |
| 数据能力 | SQLite 单文件、importance/hot 需全表内存排序 | 缺预计算列与索引设计 |

### 1.2 为什么选 Next.js + Python

1. **Python 是 AI 与爬虫的主战场**：httpx/asyncio 异步采集、selectolax/lxml 解析、Playwright 渲染兜底、openai/anthropic SDK、Pydantic structured output——采集层和 AI 层用 Python 重写后生态红利最大。现有 `skills/hot-monitor` 的 Python 脚本可直接平移为后端模块，一套采集代码两处复用。
2. **Next.js 补齐前端工程能力**：App Router 的 RSC/SSR 让首屏数据服务端直出（热点列表天然适合 SSR）；Route Handlers 可做 BFF 聚合；生态上 TanStack Query / Zustand / shadcn/ui 解决状态与组件分层。
3. **前后端彻底分离**：Python 后端只做 API + 任务调度 + WebSocket，Next.js 独立部署，两端通过 OpenAPI 契约协作，各自独立伸缩。

### 1.3 重构目标（验收标准）

- 功能对等：覆盖现状 6 大核心能力（关键词管理、多源监控、AI 分析、筛选排序、全网搜索、实时+邮件通知）
- 修复现状全部高危问题：鉴权、任务互斥、AI 成本硬约束、排序口径统一
- 架构可扩展：数据源插件化（新增一个源 ≤ 1 个文件）、AI Provider 可切换、支持多用户预留
- 工程达标：OpenAPI 契约、结构化日志、源健康监控、测试覆盖核心纯函数

---

## 二、目标总体架构

```
┌─────────────────────────────────────────────────────────┐
│  Next.js 前端 (Vercel / 独立部署, :3000)                  │
│  ├─ RSC 首屏 SSR：热点列表/统计直出                        │
│  ├─ Client Components：筛选栏/实时推送/动画                │
│  ├─ TanStack Query：服务端状态缓存与轮询                   │
│  └─ WebSocket hook：订阅关键词房间                         │
└──────────────┬──────────────────────────────────────────┘
               │ HTTPS /api/*  +  WSS /ws
               ▼
┌─────────────────────────────────────────────────────────┐
│  Python 后端 (FastAPI, :8000)                            │
│  ├─ API 层：routers/ (keywords, hotspots, notifications) │
│  ├─ 认证中间件：API Key / JWT                             │
│  ├─ WebSocket 网关：按关键词分房间推送                     │
│  ├─ Pipeline 层：热点检查流水线（asyncio 编排）            │
│  │    ├─ collectors/  ← 数据源插件（Bing/HN/B站/微博...） │
│  │    ├─ ai/          ← Provider 抽象 + structured output│
│  │    └─ notify/      ← WS 推送 + 邮件                    │
│  └─ 任务调度：APScheduler + 互斥锁（Redis SETNX）          │
└──────────────┬───────────────────────┬──────────────────┘
               ▼                       ▼
        PostgreSQL 16              Redis 7
        (SQLModel/SQLAlchemy 2.0)  (任务锁/AI缓存/限流/Pub-Sub)
```

**关键架构决策**：

1. **调度与 Web 同进程但任务隔离**：APScheduler 在 FastAPI 进程内触发，但流水线执行放入 asyncio 任务并通过 **Redis 分布式锁**保证单实例运行（手动触发与定时触发抢同一把锁，抢不到返回 409）。规模扩大后可平滑迁移到 Celery/Dramatiq 独立 worker，接口不变。
2. **Redis 三重角色**：任务互斥锁、AI 分析结果缓存（内容哈希 → 分析结果，跨关键词复用）、查询扩展缓存（替代现状的进程内 Map，重启不丢）。
3. **SQLite → PostgreSQL**：现状热点表字段多、筛选维度多，PG 的复合索引 + JSONB（存原始 payload）更合适；本地开发仍可用 SQLite 跑通（SQLModel 双兼容）。

---

## 三、数据模型设计（Prisma → SQLModel 迁移 + 改进）

### 3.1 模型对照与改进点

```python
# 核心改进用 ★ 标注

class Keyword(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    text: str = Field(unique=True, index=True)
    category: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    hotspots: list["Hotspot"] = Relationship(back_populates="keyword")

class Hotspot(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    title: str
    content: str
    url: str
    source: str                        # 建议改 enum 或字典表
    source_id: str | None = None
    # AI 分析结果
    is_real: bool = True
    relevance: int = 0                 # CHECK 0-100
    relevance_reason: str | None = None
    keyword_mentioned: bool | None = None
    importance: str = "low"            # low/medium/high/urgent
    summary: str | None = None
    # ★ 预计算列：写入时算好，消灭内存排序
    hot_score: float = 0.0             # likes*10 + rt*5 + log10(views)*2
    importance_rank: int = 3           # urgent=0..low=3，直接 ORDER BY
    # 互动指标（同现状，略）
    view_count: int | None = None
    like_count: int | None = None
    # ... retweet/reply/comment/quote/danmaku
    # 作者信息（同现状，略）
    published_at: datetime | None = None  # ★ 加索引
    created_at: datetime = Field(default_factory=utcnow)  # ★ 加索引
    keyword_id: UUID | None = Field(foreign_key="keyword.id")
    # ★ 原始报文留存，便于排查与重分析
    raw_payload: dict | None = Field(default=None, sa_column=Column(JSONB))

    __table_args__ = (
        UniqueConstraint("url", "source"),
        Index("ix_hotspot_feed", "created_at", "importance_rank", "hot_score"),  # ★ 信息流复合索引
    )

class Notification(SQLModel, table=True):
    # ★ 补真正的外键关系（现状是裸 hotspotId 字符串）
    hotspot_id: UUID | None = Field(foreign_key="hotspot.id")
    hotspot: Hotspot | None = Relationship()
    # ... type/title/content/is_read/created_at

class Setting(SQLModel, table=True):   # 保留 KV 表，用于通知阈值/调度间隔等运行时配置
    key: str = Field(primary_key=True)
    value: str

# ★ 新增：采集源健康表（监控用）
class SourceHealth(SQLModel, table=True):
    source: str = Field(primary_key=True)
    last_success_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
```

### 3.2 排序口径统一

热度公式**只保留一份**，定义在后端 `pipeline/scoring.py`：

```python
def calc_hot_score(h) -> float:
    return (h.like_count or 0) * 10 + (h.retweet_count or 0) * 5 \
           + math.log10(max(h.view_count or 1, 1)) * 2
```

- 落库时写入 `hot_score` / `importance_rank` 列，列表接口直接 `ORDER BY`，**消灭全表内存排序**；
- 前端展示的"热度分"由后端在响应中返回归一化值（0–100），前端不再自行计算——口径分裂问题从根上消除。

### 3.3 数据迁移

一次性脚本 `scripts/migrate_sqlite_to_pg.py`：读现有 `dev.db`，逐表写入 PG；迁移时对存量热点**回填** `hot_score` / `importance_rank`。保留原 SQLite 文件作为备份。

---

## 四、核心流水线重构（hotspotChecker → Python）

### 4.1 流水线阶段化设计

现状是一条 200 行函数，重构后拆为**显式的阶段（Stage）**，每个阶段纯函数化、可单测：

```python
# pipeline/hotspot_check.py
async def run_hotspot_check(ctx: PipelineContext) -> CheckReport:
    async with distributed_lock("hotspot_check", ttl=1800):      # ① 互斥（修复重入）
        keywords = await repo.list_active_keywords()
        for kw in keywords:
            await process_keyword(kw, ctx)
            await asyncio.sleep(2)

async def process_keyword(kw: Keyword, ctx) -> KeywordReport:
    # Stage 1: 账号检测（B站UP主 / Twitter 用户）
    account_hits = await account_detector.detect(kw.text)
    # Stage 2: 查询扩展（Redis 缓存，TTL 7 天）
    variants = await query_expander.expand(kw.text)
    # Stage 3: 多源并行采集（asyncio.gather + return_exceptions）
    raw = await collect_all(kw.text, sources=registry.enabled())
    # Stage 4: 清洗（去重 → 新鲜度 → 优先级）
    cleaned = dedupe(raw) | fresh(raw, max_age=7*24h) | prioritize(raw)
    # Stage 5: 库内查重（批量 IN 查询，★修复逐条 SELECT 的 N+1）
    candidates = await repo.filter_existing(cleaned)
    # Stage 6: ★配额前置——先按配额截断，再进 AI（AI 调用量 = 配额上限，成本硬约束）
    budgeted = apply_quota(candidates, twitter=15, other=10)
    # Stage 7: AI 批量分析（Semaphore(3) 限流 + 内容哈希缓存）
    analyzed = await ai_analyzer.analyze_batch(budgeted, kw, variants)
    # Stage 8: 阈值过滤 + 落库 + 分级通知
    for item, analysis in analyzed:
        if not passes_threshold(analysis): continue
        hotspot = await repo.create(item, analysis, kw)
        await notifier.dispatch(hotspot)   # WS 全量 + 邮件仅 high/urgent
```

### 4.2 相对现状的关键修正

| 现状问题 | 重构方案 |
|---|---|
| 配额按入库成功计数，AI 调用量失控 | **配额前置**：查重后立即截断，AI 调用数 ≤ 25/关键词/轮，可在 `Setting` 表配置 |
| 逐条 `findFirst` 查重（N+1） | 一次 `WHERE (url, source) IN (...)` 批量查询 |
| cron 与手动触发可并发 | Redis `SET NX EX` 分布式锁；手动触发时锁被占用返回 `409 Conflict` 并附当前运行状态 |
| AI 失败默认 `isReal=true` 放行 | 失败进入 `pending_analysis` 状态队列，下一轮重试（最多 2 次），不直接放行也不丢弃 |
| 单源失败静默返回 `[]` | 写入 `SourceHealth`，连续失败 ≥ 3 次在通知中心产生 `alert` 类型通知 |
| 关键词串行处理 | 关键词间保持串行（控制外网请求速率），但**单关键词内部全异步**：6 源采集 `asyncio.gather`，AI 分析 `Semaphore(3)` 并发 |

### 4.3 采集层插件化

```python
# collectors/base.py
class Collector(Protocol):
    name: str
    rate_limit: float          # 最小请求间隔（秒）
    async def search(self, query: str) -> list[SearchResult]: ...

# collectors/registry.py —— 新增加一个源 = 新增一个文件 + 注册一行
REGISTRY: dict[str, Collector] = {
    "twitter":    TwitterCollector(),     # 平移 twitterapi.io 逻辑+质量过滤
    "bing":       BingCollector(),        # httpx + selectolax
    "hackernews": HackerNewsCollector(),  # Algolia API
    "sogou":      SogouCollector(),
    "bilibili":   BilibiliCollector(),    # 含 buvid3 规避 + UP主检测
    "weibo":      WeiboHotSearchCollector(),
}
```

- 解析库从 cheerio 换成 **selectolax**（快 10 倍+）或 lxml；选择器失效时抛出 `SelectorDriftError` 并上报 SourceHealth，而不是静默返回空；
- 需要 JS 渲染的源预留 **Playwright** 兜底通道（配置开启，默认关闭省资源）；
- 现状 `skills/hot-monitor/scripts/` 下的 Python 采集脚本**直接平移**为 collectors 初版，TS 版逻辑作为对照参照。

### 4.4 AI 层设计

```python
# ai/provider.py —— Provider 抽象，OpenRouter/DeepSeek/通义可切换
class AIProvider(Protocol):
    async def analyze(self, content: str, keyword: str,
                      prematch: PreMatch) -> AIAnalysis: ...
    async def expand_query(self, keyword: str) -> list[str]: ...

# ai/schemas.py —— Pydantic 强类型输出，替代正则捞 JSON
class AIAnalysis(BaseModel):
    is_real: bool
    relevance: int = Field(ge=0, le=100)
    relevance_reason: str = Field(max_length=200)
    keyword_mentioned: bool
    importance: Literal["low", "medium", "high", "urgent"]
    summary: str = Field(max_length=150)
```

- 优先使用模型的 **JSON mode / structured output**（OpenRouter 支持 `response_format`），Pydantic 校验失败再降级到正则提取 + 字段钳制（保留现状的防御逻辑作为 fallback）；
- **内容哈希缓存**：`sha256(content) → AIAnalysis` 存 Redis（TTL 30 天），同一内容被多个关键词命中时只付一次钱；
- 阈值规则（<50 丢弃、未提及且 <65 丢弃）与 prompt 模板抽到 `ai/rules.py` + `ai/prompts/`，可配置、可 AB。

---

## 五、API 契约设计（FastAPI routers）

| 方法 & 路径 | 说明 | 相对现状变化 |
|---|---|---|
| `GET /api/keywords` | 关键词列表（含热点计数） | 不变 |
| `POST /api/keywords` | 创建 | 加鉴权 |
| `PUT /api/keywords/{id}` / `PATCH /{id}/toggle` / `DELETE /{id}` | 管理 | 加鉴权 |
| `GET /api/hotspots` | 分页列表 | **全部改 DB 排序**（hot_score/importance_rank 列），新增 `sort=hot` 不再全表加载 |
| `GET /api/hotspots/stats` | 统计 | 不变 |
| `POST /api/hotspots/search` | 手动全网搜索 | **改异步任务**：返回 `task_id`，前端轮询 `GET /api/tasks/{id}` 或 WS 推送结果（修复同步等 10 次 AI 调用的超长延迟） |
| `POST /api/check-hotspots` | 手动触发 | 锁占用时返回 409 + 当前进度 |
| `GET /api/notifications` 等 | 通知 CRUD | 不变 |
| `GET /api/sources/health` | ★ 新增：各数据源健康状态 | 可观测性 |
| `WS /ws?keywords=a,b` | WebSocket | 替代 Socket.io：FastAPI 原生 WS + Redis Pub/Sub 广播（多实例可扩展） |
| `GET /api/health` | 健康检查 | 不变 |

**契约协作**：FastAPI 自动生成 OpenAPI → 前端用 `openapi-typescript` 生成 TS 类型，**前后端类型同源**，替代现状手工对齐的 `api.ts` 接口定义。

**鉴权方案**（分层）：
- 短期：单用户场景，全 API 走 `X-API-Key` header（环境变量配置），WS 握手时校验；
- 预留：`users` 表 + JWT（`fastapi-users` 或 Authlib），Keyword 加 `owner_id`，改造成本前置到 schema 设计里。

---

## 六、前端重构（React SPA → Next.js App Router）

### 6.1 目录与渲染策略

```
web/
├── app/
│   ├── layout.tsx              # 暗色主题 + 背景特效（Spotlight/Beams 保留）
│   ├── page.tsx                # Dashboard —— RSC：首屏热点列表/统计 SSR 直出
│   ├── keywords/page.tsx       # 关键词管理 —— RSC + client 表单
│   ├── search/page.tsx         # 全网搜索 —— Client（交互密集）
│   └── api/                    # BFF Route Handlers（可选聚合层）
├── components/
│   ├── hotspot-card.tsx        # ★ 从 App.tsx 拆出
│   ├── hotspot-feed.tsx        # 列表 + 分页 + WS 增量插入
│   ├── filter-sort-bar.tsx     # 迁移现有组件
│   ├── stats-hero.tsx / notification-bell.tsx / keyword-grid.tsx ...
│   └── ui/                     # shadcn/ui + 保留 Aceternity 特效组件
├── hooks/
│   ├── use-hotspot-socket.ts   # WS 订阅/断线重连/房间管理
│   └── use-toast.ts
└── lib/
    ├── api.ts                  # openapi-typescript 生成类型 + fetch 封装
    └── queries.ts              # TanStack Query hooks
```

### 6.2 相对现状的改进

1. **拆分 1122 行 App.tsx**：按 Tab 拆路由、按 UI 区块拆组件，`hotspot-card` 等展示组件保持纯渲染；
2. **首屏 SSR**：Dashboard 列表由 RSC 直接取数渲染，首屏无 loading 闪动；筛选变化走 Client 侧 TanStack Query 重取（`staleTime: 30s`）；
3. **实时推送**：`use-hotspot-socket` hook 收到 `hotspot:new` → 调 `queryClient.invalidateQueries` + 列表头插入，逻辑收敛在一处（现状散落在 App.tsx effect 里）；
4. **状态管理**：筛选条件等客户端状态用 Zustand（跨组件共享）或 URL searchParams（可分享链接）——推荐后者，筛选状态即 URL，天然支持刷新保持与分享；
5. **UI 体系**：保留 Aceternity 特效组件（Spotlight/Meteors/Beams 为纯 CSS/JS，可直接迁移）+ shadcn/ui 补标准控件；热度分等数据**全部使用后端返回值**。

---

## 七、安全与可观测性

| 项 | 方案 |
|---|---|
| 邮件 XSS | Jinja2 模板自动转义渲染邮件 HTML；URL 白名单校验（仅 http/https） |
| 接口鉴权 | API Key 中间件（短期）→ JWT（预留） |
| 限流 | `slowapi`（FastAPI 限流中间件）保护 `/search`、`/check-hotspots` 等重接口 |
| 日志 | `structlog` 结构化日志，流水线每阶段输出 `{keyword, source, count, duration_ms}` |
| 监控 | SourceHealth 表 + `/api/sources/health` 端点 + 连续失败告警通知 |
| 秘钥 | `.env` + pydantic-settings 校验（启动时缺 key 明确报错而非静默降级） |

---

## 八、部署方案

```yaml
# docker-compose.yml（自托管单 VPS 起步）
services:
  web:        # Next.js standalone 构建
    build: ./web
    ports: ["3000:3000"]
  api:        # FastAPI (uvicorn)
    build: ./api
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db, redis]
  db:         # postgres:16 + volume
  redis:      # redis:7
  caddy:      # 反代 + 自动 HTTPS：/ → web，/api,/ws → api
```

- 前端也可部署 Vercel（`NEXT_PUBLIC_API_URL` 指向后端域名），后端 + PG + Redis 仍在 VPS；
- CI：GitHub Actions —— 后端 pytest + ruff，前端 tsc + eslint + build，docker build 推送。

---

## 九、迁移路线图（4 个里程碑，建议 2–3 周）

| 里程碑 | 范围 | 验收 |
|---|---|---|
| **M1 后端骨架**（约 3–4 天） | FastAPI 工程、SQLModel + PG、关键词/热点/通知只读 API、鉴权中间件、SQLite 数据迁移脚本 | 旧前端指向新后端，列表/详情/统计可用 |
| **M2 流水线**（约 4–5 天） | collectors 插件化平移 6 源、AI 层（structured output + 缓存）、pipeline 阶段化 + 分布式锁 + 配额前置、APScheduler 接管 cron、邮件通知 | 关闭旧系统，新系统独立完成一轮全量检查，AI 调用量可审计 |
| **M3 前端重构**（约 4–5 天） | Next.js 工程、三页面迁移、组件拆分、RSC 首屏、TanStack Query、WS hook、openapi 类型生成 | 功能与旧前端对等，首屏 SSR，筛选状态 URL 化 |
| **M4 增强与收尾**（约 2–3 天） | 手动搜索异步任务化、SourceHealth 面板、结构化日志、docker-compose、CI、文档更新 | 一键部署，源故障可感知 |

**灰度策略**：M2 期间新旧系统并行跑（新系统只落库不通知），对比同一关键词两边的热点产出差异，验证过滤规则一致后再切换通知通道。

---

## 十、风险与权衡

| 风险 | 评估 | 应对 |
|---|---|---|
| Socket.io → 原生 WS 的替换 | 失去自动重连/降级，但房间模型简单 | hook 内实现指数退避重连；如需多实例广播已预留 Redis Pub/Sub |
| Python 后端缺 Socket.io 生态 | python-socketio 可选，但原生 WS + 自定义协议更轻 | 协议保持 `{event, data}` JSON 信封 |
| 爬虫逻辑双语言维护窗口期 | M2 期间 TS/Python 两份采集代码并存 | M2 完成后归档 TS server，以 Python 为唯一实现；Agent Skill 包继续复用 collectors |
| 重构范围蔓延 | 多用户、PG 全文检索等诱惑 | 明确 M1–M4 只做功能对等 + 高危修复，增强项入 backlog |
| Playwright 等资源重依赖 | 默认不启用 | 作为 collector 可选 channel，配置开启 |

---

## 十一、重构后保留的"原项目精华"

重构不是推翻——以下设计**原样保留**，它们是原项目最有价值的部分：

1. 两阶段检索架构：Query Expansion（含纯文本 fallback）→ 文本预匹配 → AI 复核；
2. 三级过滤规则：isReal 过滤、relevance ≥ 50、未提及关键词需 ≥ 65；
3. 来源优先级与配额思想（仅修正计数语义）；
4. 账号检测模式（关键词即 UP 主）；
5. 分级通知策略（WS 全量、邮件仅 high/urgent）；
6. Twitter 质量过滤阈值与 Top/Latest 双轨拉取；
7. Agent Skills 双形态交付（Skill 包的采集脚本与后端 collectors 同源）。
