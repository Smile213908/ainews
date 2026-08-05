/**
 * Dashboard 占位壳（M0）：验证工程可运行。
 * M3 将按重构方案 §6.1 实现 RSC 首屏 SSR + 热点信息流。
 */

const MILESTONES = [
  { id: "M1", title: "后端骨架", desc: "FastAPI + SQLModel + 鉴权 + 迁移", done: true },
  { id: "M2", title: "监控流水线", desc: "6 源采集 · AI 过滤 · 分布式锁", done: false },
  { id: "M3", title: "前端重构", desc: "RSC 首屏 · 筛选 URL 化 · WS 实时", done: false },
  { id: "M4", title: "增强收尾", desc: "搜索异步化 · 源健康 · 一键部署", done: false },
];

export default function DashboardPage() {
  return (
    <main className="relative mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center px-6 py-16">
      {/* 聚光灯背景（Aceternity 风格，纯 CSS 实现） */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-96"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, var(--accent-glow), transparent 70%)",
        }}
      />

      <p className="text-sm tracking-[0.3em] text-[var(--muted)]">HOT-MONITOR 2.0</p>
      <h1 className="mt-4 text-center text-4xl font-bold sm:text-5xl">
        AI 热点雷达
        <span className="text-[var(--accent)]"> · </span>重构进行中
      </h1>
      <p className="mt-4 max-w-xl text-center text-[var(--muted)]">
        你只管订阅关键词，系统替你 7×24 盯着全网，
        只把「真实、相关、重要」的热点推给你。
      </p>

      <div className="mt-12 grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {MILESTONES.map((m) => (
          <div
            key={m.id}
            className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--accent)]">{m.id}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  m.done
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-zinc-500/15 text-zinc-400"
                }`}
              >
                {m.done ? "已完成" : "待开工"}
              </span>
            </div>
            <h2 className="mt-3 font-semibold">{m.title}</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">{m.desc}</p>
          </div>
        ))}
      </div>

      <p className="mt-12 text-xs text-[var(--muted)]">
        后端 API：FastAPI · PostgreSQL · Redis —— 契约对接将在 M3 完成
      </p>
    </main>
  );
}
