import { HotspotStats, SOURCE_LABELS } from "@/lib/api";

/** 统计概览（FR-2.1）：RSC 首屏 SSR 直出 —— 赛博霓虹数据卡 */
export default function StatsHero({ stats }: { stats: HotspotStats }) {
  const cards = [
    { label: "累计热点", code: "TOTAL", value: stats.total, color: "var(--accent)" },
    { label: "今日新增", code: "TODAY", value: stats.today_new, color: "#4ade80" },
    { label: "紧急热点", code: "URGENT", value: stats.urgent_count, color: "var(--neon-pink)" },
  ];

  return (
    <section className="space-y-4">
      <div className="grid grid-cols-3 gap-5">
        {cards.map((c) => (
          <div key={c.label} className="cyber-panel rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="text-xs text-[var(--muted)]">{c.label}</p>
              <span className="cyber-label">{c.code}</span>
            </div>
            <p
              className="mt-3 font-mono text-4xl font-bold"
              style={{
                color: c.color,
                textShadow: `0 0 18px ${c.color === "var(--accent)" ? "var(--accent-glow)" : c.color + "55"}`,
              }}
            >
              {c.value}
            </p>
          </div>
        ))}
      </div>
      {Object.keys(stats.by_source).length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs text-[var(--muted)]">
          {Object.entries(stats.by_source).map(([src, count]) => (
            <span
              key={src}
              className="rounded-full border border-[var(--card-border)] bg-[var(--card)] px-3 py-1"
            >
              {SOURCE_LABELS[src] ?? src} · <span className="text-[var(--accent)]">{count}</span>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
