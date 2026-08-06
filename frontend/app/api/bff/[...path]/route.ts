/**
 * BFF 代理（技术选型 §8.1）：浏览器 → /api/bff/* → 后端 API（注入 API Key）。
 * API Key 只存在于服务端环境变量，不下发浏览器。
 */

import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.API_BASE_URL ?? "http://localhost:8000";
const KEY = process.env.API_KEY ?? "";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const url = `${BASE}/api/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "X-API-Key": KEY };
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const hasBody = !["GET", "HEAD", "DELETE"].includes(req.method);
  const resp = await fetch(url, {
    method: req.method,
    headers,
    body: hasBody ? await req.text() : undefined,
    cache: "no-store",
  });

  if (resp.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "Content-Type": resp.headers.get("content-type") ?? "application/json" },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
