import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // M4 部署时启用 standalone 输出（Docker 多阶段构建，技术选型 §9.1）
  // output: "standalone",
};

export default nextConfig;
