import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "hot-monitor 2.0 · AI 热点雷达",
  description: "关键词级全网热点监控：真实、相关、重要的热点才会推给你",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">
        <Providers>
          <header className="sticky top-0 z-30 border-b border-[var(--card-border)] bg-[var(--background)]/80 backdrop-blur">
            <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3 text-sm">
              <Link href="/" className="font-bold text-[var(--accent)]">
                🔥 hot-monitor
              </Link>
              <Link href="/" className="text-[var(--muted)] hover:text-[var(--foreground)]">
                热点信息流
              </Link>
              <Link
                href="/keywords"
                className="text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                关键词管理
              </Link>
              <Link
                href="/search"
                className="text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                全网搜索
              </Link>
            </nav>
          </header>
          <div
            aria-hidden
            className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-96"
            style={{
              background:
                "radial-gradient(ellipse 60% 50% at 50% 0%, var(--accent-glow), transparent 70%)",
            }}
          />
          {children}
        </Providers>
      </body>
    </html>
  );
}
