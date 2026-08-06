import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 多阶段构建输出独立 node 产物（技术选型 §9.1，镜像 ~150MB）
  output: "standalone",
};

export default nextConfig;
