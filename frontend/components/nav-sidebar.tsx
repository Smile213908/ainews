/** 左侧赛博导航栏：高亮当前路由，底部系统状态指示。 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "热点信息流", code: "FEED", icon: "◈" },
  { href: "/keywords", label: "关键词管理", code: "KEYS", icon: "⌖" },
  { href: "/search", label: "全网搜索", code: "SCAN", icon: "◎" },
  { href: "/sources", label: "源健康", code: "LINK", icon: "⌁" },
];

export default function NavSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-[var(--card-border)] bg-[rgba(6,10,22,0.85)] backdrop-blur-xl">
      {/* Logo */}
      <Link href="/" className="group flex items-center gap-3 px-5 py-6">
        <span className="cyber-dot flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--accent)]/50 text-lg text-[var(--accent)]">
          ⚡
        </span>
        <span>
          <span className="neon-text block text-base font-bold tracking-wide">
            hot-monitor
          </span>
          <span className="cyber-label block">AI RADAR · v2.0</span>
        </span>
      </Link>

      {/* 导航 */}
      <nav className="mt-2 flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                active
                  ? "border border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--accent)] shadow-[0_0_16px_rgba(0,229,255,0.15)]"
                  : "border border-transparent text-[var(--muted)] hover:border-[var(--card-border)] hover:bg-[var(--card)] hover:text-[var(--foreground)]"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-[var(--accent)] shadow-[0_0_8px_var(--accent)]" />
              )}
              <span className={active ? "text-[var(--accent)]" : "opacity-60"}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              <span className="cyber-label opacity-50 group-hover:opacity-90">
                {item.code}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* 底部状态 */}
      <div className="border-t border-[var(--card-border)] px-5 py-4">
        <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
          <span className="cyber-dot h-1.5 w-1.5 rounded-full bg-emerald-400 text-emerald-400" />
          系统在线
        </div>
        <p className="cyber-label mt-2">PG · REDIS · AI LINKED</p>
      </div>
    </aside>
  );
}
