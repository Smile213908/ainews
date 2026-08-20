import type { Metadata } from "next";
import "./globals.css";
import NavSidebar from "@/components/nav-sidebar";
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
          {/* 赛博网格氛围背景 */}
          <div aria-hidden className="cyber-grid-bg pointer-events-none fixed inset-0 -z-10" />
          <NavSidebar />
          <div className="pl-60">{children}</div>
        </Providers>
      </body>
    </html>
  );
}
