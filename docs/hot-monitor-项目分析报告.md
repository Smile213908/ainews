# AI 热点监控工具（hot-monitor）项目代码分析报告

> 分析对象：`E:\workDoc\ai_news\hot-monitor`
> 项目来源：程序员鱼皮教学项目（yupi-hot-monitor），Express 5 + React 19 + OpenRouter + Socket.io 全栈应用
> 分析日期：2026-08-05

---

## 一、项目概览

### 1.1 一句话定位

一个**关键词驱动的多源热点聚合监控系统**：用户配置监控关键词后，系统每 30 分钟自动从 Twitter、Bing、HackerNews、搜狗、B 站、微博热搜等 8+ 数据源抓取内容，用大模型做真假识别、相关性打分和智能摘要，通过 WebSocket 实时推送 + 邮件通知用户。同时把搜索能力抽离为独立的 **Agent Skills 技能包**（Python 脚本版），供 Cursor / Claude Code 等 AI 编程工具复用。

### 1.2 目录结构

```
hot-monitor/
├── client/                 # React 19 + Vite 7 + Tailwind CSS 4 前端
│   └── src/
│       ├── App.tsx         # 单页主应用（1122 行，3 个 Tab）
│       ├── components/     # FilterSortBar + Aceternity 风格 UI 特效组件
│       ├── services/       # api.ts（REST 封装）、socket.ts（WebSocket 封装）
│       └── utils/          # sortHotspots（与服务端同构）、relativeTime
├── server/                 # Express 5 + Prisma + SQLite 后端
│   ├── prisma/             # schema + 3 个迁移（演化痕迹清晰）
│   └── src/
│       ├── index.ts        # 入口：HTTP + Socket.io + cron 定时任务
│       ├── jobs/hotspotChecker.ts   # 核心：热点检查流水线
│       ├── routes/         # keywords / hotspots / notifications / settings
│       ├── services/       # ai / twitter / search / chinaSearch / email
│       └── __tests__/      # vitest 单测（排序、AI 相关性）
├── skills/hot-monitor/     # Agent Skills 技能包（Python 脚本 + SKILL.md）
└── docs/                   # 需求、API 集成、本地运行文档
```

### 1.3 技术栈一览

| 层 | 技术 | 版本要点 |
|---|---|---|
| 前端 | React 19、Vite 7、Tailwind CSS 4、framer-motion、lucide-react、socket.io-client | 全套最新主版本，UI 走 Aceternity 特效风（Spotlight / Beams / Meteors） |
| 后端 | Express 5、Socket.io 4、node-cron 4、Prisma 6 + SQLite | ESM（`"type": "module"`），tsx watch 开发 |
| AI | @openrouter/sdk，模型 `deepseek/deepseek-v3.2` | 统一网关接入，成本低 |
| 采集 | axios + cheerio（爬虫）、twitterapi.io（第三方 Twitter API）、B 站/微博公开 API、HN Algolia API | 官方 API 与 HTML 爬虫混用 |
| 通知 | nodemailer（SMTP）+ Socket.io 房间推送 | 双通道 |
| 测试 | vitest | 覆盖排序与 AI 相关性逻辑 |

---

## 二、业务分析

### 2.1 业务模型

核心实体只有 4 张表（`server/prisma/schema.prisma`），模型极简：

- **Keyword**：监控关键词，支持 `category` 分类和 `isActive` 激活/暂停开关。`text` 唯一约束。
- **Hotspot**：抓到的热点。字段设计是本项目最"重"的部分——除标题/正文/URL/来源外，还存了 AI 分析结果（`isReal`、`relevance`、`relevanceReason`、`keywordMentioned`、`importance`、`summary`）、多平台互动指标（点赞/转发/浏览/回复/评论/引用/弹幕）和作者信息（名称/头像/粉丝/认证）。`@@unique([url, source])` 做落库去重。
- **Notification**：站内通知，挂 `hotspotId` 外键（逻辑外键，未建 Prisma relation）。
- **Setting**：KV 配置表（目前基本未用，属预留）。

### 2.2 核心业务流程（hotspotChecker.ts）

这是整个系统的心脏，一次 `runHotspotCheck` 的执行链路：

```
激活关键词 → 账号检测 → AI 查询扩展 → 6 源并行抓取 → 去重 → 新鲜度过滤
→ 来源优先级排序 → 配额控制 → 库内查重 → AI 分析 → 多级阈值过滤
→ 落库 → 通知（DB + WebSocket + 邮件）
```

关键业务规则逐条解读：

1. **账号检测优先**（`detectAndFetchAccount`）：先判断关键词是不是某个 B 站 UP 主（精确匹配用户名，或粉丝 > 1000 且名字包含关键词），是则直接拉取该 UP 主最新 10 条视频并赋予最高优先级。这是一个很聪明的产品设计——"监控某人"和"监控某话题"用同一个入口解决了。
2. **Query Expansion（查询扩展）**：用 AI 把关键词扩展成 5–15 个变体（大小写、连字符、中英文、别称），并有纯文本 fallback（`extractCoreTerms`：按空格/连字符拆分 + 两两组合）。结果用 Map 缓存，同一关键词进程内只调一次 AI。目的是提高后续文本预匹配的召回率。
3. **6 源并行 + 容错**：`Promise.allSettled` 并行请求 Twitter / Bing / HN / 搜狗 / B 站 / 微博热搜，单源失败不影响整体，每源打印抓取数量，可观测性好。
4. **三级数据清洗**：
   - URL 归一化去重（去尾斜杠、统一 www）；
   - 新鲜度过滤：丢弃 7 天前的内容（无时间的搜索引擎结果放行）；
   - 来源优先级排序：Twitter > 微博 > B 站 > HN > 搜狗 > Bing > Google > DDG。
5. **配额控制**：Twitter 最多处理 15 条，其他来源共享 10 条配额。这既控制了 AI 调用成本，又体现了"Twitter 是第一信源"的业务判断。
6. **AI 分析 + 三层过滤**：
   - `isReal = false` → 丢弃（标题党/假新闻/软文）；
   - `relevance < 50` → 丢弃；
   - **关键词未直接提及 且 relevance < 65** → 丢弃（防止"同领域沾边"内容漏入）。
7. **分级通知**：所有新热点写 Notification 表 + WebSocket 推送到 `keyword:{text}` 房间和全局 `notification` 事件；只有 `high`/`urgent` 级才发邮件——避免邮件轰炸。

### 2.3 值得注意的业务设计取舍

- **微博源的实现方式**：不是搜索微博内容，而是拉取微博**热搜榜**再与关键词做双向包含匹配。成本极低（一个免登录公开接口），但只能发现"已经上热搜"的话题，是监控而非搜索。
- **Twitter 走第三方 API**（twitterapi.io）：官方 API 贵且受限，教学项目用第三方聚合服务是务实选择；同时自建了一套质量过滤（排除回复、点赞 ≥ 10、转发 ≥ 5、浏览 ≥ 500、粉丝 ≥ 100，蓝 V 阈值减半）+ 质量分排序（likes×2 + RT×3 + views/100 + 蓝 V +50），用 Twitter 高级搜索语法（`-filter:retweets since:YYYY-MM-DD min_faves:10`）做 Top/Latest 双轨拉取。
- **前后端各有一套热度公式且不一致**：服务端 `calcHotScore = likes×10 + RT×5 + log10(views)×2`；前端 `calcHeatScore` 另外引入回复/评论/引用并 log 压缩到 0–100 做"爆/热/温"标签。两者用途不同（排序 vs 展示），但口径分裂是维护隐患（详见 §5）。
- **成本意识贯穿始终**：配额限制、AI 输入截断 2000 字符、`maxTokens` 限制（扩展 300 / 分析 500）、temperature 0.2 提高一致性、扩展结果缓存、每关键词间 sleep 2s——这是一个"知道 LLM 调用要花钱"的项目。

---

## 三、技术要点分析

### 3.1 架构形态

经典**前后端分离 SPA + 单体后端**：

```
React SPA (5173) ──/api,/socket.io 代理──> Express (3001) ──> SQLite (Prisma)
                                              │
                                              ├─ node-cron: */30 * * * * 触发检查
                                              ├─ Socket.io: keyword 房间定向推送
                                              └─ nodemailer: SMTP 邮件
```

Vite dev server 把 `/api` 和 `/socket.io`（`ws: true`）代理到 3001，前端 socket 直接连 `window.location.origin`，开发与生产同构，无需跨域配置。

### 3.2 后端亮点

1. **Express 5 + 纯 ESM**：`"type": "module"`，import 带 `.js` 后缀，tsx watch 开发体验顺滑。Express 5 自动捕获 async 路由错误，但项目仍手写 try/catch——风格保守但一致。
2. **Prisma + SQLite 零依赖起步**：`prisma db push` 即可跑起来；3 个 migration 文件记录了演化过程（init → 增加热点明细字段 → 增加 keywordMentioned），schema 与迁移同步，工程习惯良好。
3. **爬虫层的工程化处理**：
   - 每个数据源独立 `RateLimiter`（Bing 5s / Google 10s / DDG 3s / 搜狗 3s / B 站 2s / 微博 3s），防止触发反爬；
   - UA 池随机轮换；
   - B 站请求构造随机 `buvid3` cookie 规避 412 风控；
   - DuckDuckGo 的 `uddg=` 重定向 URL 解包、搜狗相对链接补全——细节到位；
   - 所有搜索函数失败返回 `[]` 而非抛错，配合 `Promise.allSettled` 实现"部分可用"。
4. **AI 调用的防御性设计**：
   - 无 API Key 时优雅降级（查询扩展退回规则法、分析退回默认分数），系统仍能跑通全流程；
   - 用正则 `\{[\s\S]*\}` / `\[[\s\S]*\]` 从 LLM 输出中捞 JSON，而不是假设模型严格输出 JSON；
   - 解析结果逐字段校验/钳制（relevance 钳到 0–100，importance 白名单校验），防止脏数据入库。
5. **WebSocket 房间模型**：客户端 `subscribe` 关键词列表 → 服务端 `socket.join('keyword:'+kw)` → 新热点定向 `io.to(room).emit`，另有全局 `notification` 广播。前端收到 `hotspot:new` 后既即时插入列表头部又触发全量刷新，体验与一致性兼顾。

### 3.3 前端亮点

1. **单文件 1122 行的 App.tsx**：教学项目的典型取舍——三个 Tab（dashboard / keywords / search）全放一个组件，约 20 个 `useState`。可读性尚可（注释分区清晰），但已逼近可维护性边界。
2. **数据流清晰**：`loadData` 用 `useCallback` 依赖 `dashboardFilters + currentPage`，筛选/分页变化自动重取；WebSocket 事件进来后插入头部 + toast + 延迟全量刷新。
3. **前后端同构的排序模块**：`client/src/utils/sortHotspots.ts` 与 `server/src/utils/sortHotspots.ts` 是同一份逻辑的两份拷贝（服务端用于 importance/hot 这两种 Prisma 无法表达的内存排序）。同构思路对，但用了复制而非共享包——教学项目可接受，生产应抽 shared package。
4. **UI 工程**：Tailwind 4 + framer-motion 入场动画 + Aceternity 特效组件（背景光束、流星雨、聚光灯），暗色科技感主题，热度条/重要性徽章/AI 摘要/相关性理由折叠等展示细节丰富。lucide 图标语义化（⚡=点赞、👁=浏览）。
5. **轻量 API 层**：`api.ts` 统一 `request<T>` 封装 fetch，错误从 body 提取 message 抛出；类型定义（Keyword/Hotspot/Notification/Stats）与服务端 schema 手工对齐。

### 3.4 Agent Skills 技能包

`skills/hot-monitor/` 是把业务能力"去服务化"的二次封装：

- 三个 Python 脚本（`search_web.py` / `search_china.py` / `search_twitter.py`）复刻了 TS 版的采集逻辑，统一输出 JSON 到 stdout，失败输出 `[]`；
- `SKILL.md` 遵循 Agent Skills 规范（frontmatter name/description），把"分析"这一步从调外部 LLM API 改为**由宿主 AI（Claude/Cursor 里的模型）自己完成**，并附 `analysis-guide.md` 评估框架和报告模板；
- 设计理念很先进：**数据脚本化 + 智能 Agent 化**，技能包零依赖（只需 requests + beautifulsoup4）、零数据库，可被任意支持 Skills 的 AI 工具加载。

这是本项目区别于普通教程项目的最大亮点：同一套业务能力同时以 SaaS 形态和 Agent 技能形态交付。

---

## 四、测试与文档

- **测试**：vitest 两个测试文件，覆盖 `sortHotspots`（重要性排序语义、hot 分数）和 AI 相关性过滤逻辑。覆盖率不高但选点精准——测的正是"规则复杂、最易回归"的纯函数。
- **文档**：docs/ 下有 REQUIREMENTS、API_INTEGRATION、LOCAL_SETUP 三份文档，README 含快速运行指引；代码内中文注释密度高（尤其业务规则处都有"为什么这么做"的说明，如热度公式的设计理由）。

---

## 五、问题与风险分析（代码评审视角）

### 5.1 正确性隐患

1. **`/api/hotspots` 内存排序导致分页错位**（hotspots.ts:70-108）：`importance`/`hot` 排序时改为全量取出再 `slice(skip, skip+limit)`——功能正确但**全表加载**，数据量大后会撑爆内存；且 `total` 与排序无关尚可，但当筛选+内存排序+分页组合时性能堪忧。
2. **手动搜索接口的 AI 分析是串行 Promise.all 但只取前 10 条**（hotspots.ts:223），`results.slice(0, 10)` 之后 `Promise.all` 并发打满，对 OpenRouter 可能触发限流；且 10 次 AI 调用由一次 HTTP 请求同步等待，接口延迟可达数十秒（无超时控制）。
3. **配额计数存在语义偏差**（hotspotChecker.ts:132-148）：`continue` 跳过的已存在热点**不计入配额**（配额按"成功入库"计数），所以新热点少时会消耗大量 AI 分析调用直到填满配额——AI 成本不受配额约束，只受结果数约束。建议把配额判断移到"AI 分析前、查重后"。
4. **前端热度公式与服务端排序公式不一致**（§2.3），用户在"按热度排序"时看到的 ⚡ 标签顺序可能与服务端排序顺序不吻合，造成困惑。
5. **`searchGoogle` / `searchDuckDuckGo` 已成死代码**：实现了但 `searchAll` 和 checker 均未调用（Google 反爬太强，教学实践中弃用），保留在 priorityMap 和 types 中易误导。
6. **Twitter 回复过滤正则过严**（twitter.ts:26）：`/^@\w+\s/` 要求 @ 后必须跟空格，`@user,` `@user:` 等变体会漏过；且该正则无法识别"回复但非 @ 开头"的推文（依赖 type 字段，而 type 来自第三方 API，可靠性未知）。

### 5.2 安全与健壮性

1. **邮件 HTML 模板未转义**（email.ts）：`hotspot.title`、`summary` 直接插入 HTML。抓取内容来自公网，若标题含 `<script>`/`<img onerror>`，邮件客户端中可能 XSS。同理前端 React 默认转义 OK，但 `hotspot.url` 直接做 href，若抓到 `javascript:` 协议的 URL 有风险（目前各源已用 `startsWith('http')` 过滤，B 站/微博为拼接 URL，基本可控）。
2. **无鉴权**：所有 API（含 DELETE 热点/关键词、`POST /check-hotspots` 触发爬虫+AI 调用）完全开放。仅限本机自用；一旦暴露端口，任何人都能删数据、烧 AI 额度。
3. **定时任务无锁**：30 分钟 cron 与手动触发可并发执行，且上一轮未跑完新一轮会叠加（关键词多、AI 慢时一轮可能超过 30 分钟）。同一热点并发入库靠 `@@unique([url,source])` 兜底，但 Prisma 唯一冲突会抛错进 catch（有兜住，只是日志会脏）。建议加 running flag。
4. **AI 分析失败时默认放行**（ai.ts:209-217）：catch 里 fallback `isReal: true`，分析挂掉反而让低质内容入库——"失败时偏开放"在内容审核场景值得商榷（成本与质量的取舍，但应显式标注）。
5. **SQLite 单文件 + 无备份策略**：教学够用；`publishedAt` 存储依赖各源时间解析，搜狗/Bing 结果无发布时间，长期积累后"时间筛选"对这部分数据失真。
6. **膨胀的扩展缓存无淘汰**：`expansionCache` 是进程内 Map，关键词多了只增不减（实际量级可忽略，但属不规范）。

### 5.3 工程化改进建议

| 优先级 | 建议 |
|---|---|
| 高 | 给 `/api` 加简单鉴权（如 API Key header）；手动搜索接口加超时与并发上限（ai.ts 已有 `batchAnalyze` 限流 3 并发，但路由里没用它） |
| 高 | cron 任务加互斥锁，防止重入 |
| 中 | 配额判断移到查重后、AI 调用前，真正锁住 AI 成本 |
| 中 | 前后端排序/热度公式抽成共享包（pnpm workspace + shared package），消灭双份拷贝与口径分裂 |
| 中 | importance/hot 排序改为落库时预计算分值列（如 `hotScore`），用数据库排序代替内存排序 |
| 低 | 删除或标注 searchGoogle/searchDuckDuckGo 死代码；`Setting` 表和 `sendDigestEmail` 目前未接线，要么实现要么删除 |
| 低 | App.tsx 按 Tab 拆分组件；通知与热点建立真正的 Prisma relation |

---

## 六、额外观察

1. **简历/面试视角的闪光点**（可作为面试讲解素材）：
   - Query Expansion + 预匹配 + AI 复核的**两阶段检索**架构（先提高召回，再保证精度）是 RAG/搜索系统的经典范式；
   - "关键词未提及且相关性 <65 过滤"这条规则体现了对 LLM 幻觉/宽松判断的工程补偿；
   - 爬虫层的限流、UA 池、buvid3 风控规避是真实踩坑经验的沉淀；
   - 一套能力双形态交付（Web 应用 + Agent Skill）契合当前 AI 工程化趋势。
2. **代码中的演化痕迹**：migration 时间线（0205 init → 0225 两次字段增补）、`hotspotChecker` 里的"第 1.5 步"注释、email 里已实现但未被调用的 `sendDigestEmail`——能看到需求是在使用中迭代的，真实项目的样貌。
3. **与本工作区（AI新闻聚合）的关系**：hot-monitor 的 `skills/hot-monitor` 技能包与当前工作区主题高度相关，其多源采集脚本（Bing/HN/搜狗/B 站/微博）和分析框架可直接复用。

---

## 七、总结

hot-monitor 是一个**完成度高、工程意识好的教学级全栈项目**。业务上抓住了"关键词监控 → 多源聚合 → AI 过滤 → 分级触达"的完整闭环，规则设计（配额、三级过滤、优先级、分级通知）体现了真实的产品思考；技术上 AI 调用的防御性设计、爬虫层的反爬处理、WebSocket 房间推送、Agent Skills 二次封装都是超出教程平均水平的实践。主要短板集中在**无鉴权、定时任务可重入、AI 成本控制不彻底、前后端逻辑双份拷贝**这几个点——都属于从"教学演示"走向"生产可用"需要补的课。
