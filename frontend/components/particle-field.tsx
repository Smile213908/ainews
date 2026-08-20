/** 全局赛博粒子背景：粒子匀速下落，鼠标附近粒子受引力局部跟随晃动。
 *
 * - Canvas 2D + rAF，随 DPR 缩放，窗口 resize 重建；
 * - 尊重 prefers-reduced-motion：命中则不渲染动画层；
 * - 固定定位 + 负 z-index，位于网格背景之上、内容之下，不拦截任何点击。
 */

"use client";

import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  r: number;
  speed: number;
  drift: number; // 横向自然漂移
  alpha: number;
  hue: "cyan" | "magenta";
  ox: number; // 鼠标引力偏移
  oy: number;
};

const MOUSE_RADIUS = 140; // 引力半径
const MOUSE_FORCE = 0.16; // 引力强度（向光标靠拢比例）
const EASE = 0.08; // 晃动缓动

export default function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let particles: Particle[] = [];
    let raf = 0;
    let w = 0;
    let h = 0;
    const mouse = { x: -9999, y: -9999 };

    const spawn = (count: number) => {
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 0.6 + Math.random() * 1.8,
        speed: 0.25 + Math.random() * 0.9,
        drift: (Math.random() - 0.5) * 0.15,
        alpha: 0.15 + Math.random() * 0.5,
        hue: Math.random() < 0.12 ? "magenta" : "cyan",
        ox: 0,
        oy: 0,
      }));
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      spawn(Math.min(Math.floor((w * h) / 14000), 160));
    };

    const onMouse = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    const onLeave = () => {
      mouse.x = -9999;
      mouse.y = -9999;
    };

    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        // 匀速下落 + 轻微横漂，出界回顶部
        p.y += p.speed;
        p.x += p.drift;
        if (p.y > h + 8) {
          p.y = -8;
          p.x = Math.random() * w;
        }
        if (p.x < -8) p.x = w + 8;
        else if (p.x > w + 8) p.x = -8;

        // 鼠标引力：半径内粒子向光标方向偏移，缓动回弹形成"晃动"
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.hypot(dx, dy);
        let tx = 0;
        let ty = 0;
        if (dist < MOUSE_RADIUS && dist > 0.01) {
          const pull = (1 - dist / MOUSE_RADIUS) * MOUSE_FORCE;
          tx = dx * pull;
          ty = dy * pull;
        }
        p.ox += (tx - p.ox) * EASE;
        p.oy += (ty - p.oy) * EASE;

        const x = p.x + p.ox;
        const y = p.y + p.oy;
        const glow = dist < MOUSE_RADIUS ? 1.6 : 1;

        ctx.beginPath();
        ctx.arc(x, y, p.r * glow, 0, Math.PI * 2);
        ctx.fillStyle =
          p.hue === "cyan"
            ? `rgba(0, 229, 255, ${Math.min(p.alpha * glow, 0.85)})`
            : `rgba(255, 45, 120, ${Math.min(p.alpha * glow, 0.8)})`;
        ctx.shadowColor = p.hue === "cyan" ? "rgba(0,229,255,0.8)" : "rgba(255,45,120,0.8)";
        ctx.shadowBlur = 6 * glow;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      raf = requestAnimationFrame(tick);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMouse);
    document.documentElement.addEventListener("mouseleave", onLeave);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouse);
      document.documentElement.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-[5]"
    />
  );
}
