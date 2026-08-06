import { HotspotStats, SOURCE_LABELS } from "@/lib/api";

/** 统计概览（FR-2.1）：RSC 首屏 SSR 直出 */
export default function StatsHero({ stats }: { stats: HotspotStats }) {
  const cards = [
    { label: "累计热点", value: stats.total, accent: false },
    { label: "今日新增", value: stats.today_new, accent: true },
    { label: "紧急热点", value: stats.urgent_count, accent: false, danger: true },
  ];

  return (
    <section className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {cards.map((c) => (
          <div
            key={c.label}
            className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5"
          >
            <p className="text-xs text-[var(--muted)]">{c.label}</p>
            <p
              className={`mt-2 text-3xl font-bold ${
                c.danger && c.value > 0
                  ? "text-red-400"
                  : c.accent
                    ? "text-[var(--accent)]"
                    : ""
              }`}
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
              className="rounded-full border border-[var(--card-border)] px-3 py-1"
            >
              {SOURCE_LABELS[src] ?? src} · {count}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
