/** 粒子特效设置：右下角悬浮按钮 → 弹出面板，滑杆实时调节密度/引力。
 *
 * 配置持久化到 localStorage（particle-config），并通过 CustomEvent
 * 「particle-config」通知 ParticleField 即时生效，无需刷新。
 */

"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_PARTICLE_CONFIG,
  ParticleConfig,
  loadParticleConfig,
} from "@/components/particle-field";

export default function ParticleSettings() {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<ParticleConfig>(DEFAULT_PARTICLE_CONFIG);

  // 挂载后读本地配置（避免 SSR/CSR 不一致）
  useEffect(() => {
    setConfig(loadParticleConfig());
  }, []);

  const apply = (next: ParticleConfig) => {
    setConfig(next);
    try {
      localStorage.setItem("particle-config", JSON.stringify(next));
    } catch {
      /* ignore */
    }
    window.dispatchEvent(new CustomEvent("particle-config", { detail: next }));
  };

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {open && (
        <div className="absolute bottom-12 right-0 w-64 rounded-xl border border-[var(--accent)]/25 bg-[rgba(6,10,22,0.95)] p-4 shadow-[0_0_32px_rgba(0,229,255,0.18)] backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="cyber-label">Particles // FX</span>
            <button
              onClick={() => apply(DEFAULT_PARTICLE_CONFIG)}
              className="text-xs text-[var(--muted)] hover:text-[var(--accent)]"
            >
              重置
            </button>
          </div>

          <label className="block text-xs text-[var(--muted)]">
            <span className="flex justify-between">
              <span>粒子密度</span>
              <span className="font-mono text-[var(--accent)]">
                {config.density === 0 ? "关闭" : config.density}
              </span>
            </span>
            <input
              type="range"
              min={0}
              max={300}
              step={10}
              value={config.density}
              onChange={(e) => apply({ ...config, density: Number(e.target.value) })}
              className="mt-1.5 w-full accent-[var(--accent)]"
            />
          </label>

          <label className="mt-3 block text-xs text-[var(--muted)]">
            <span className="flex justify-between">
              <span>引力强度</span>
              <span className="font-mono text-[var(--accent)]">
                {Math.round(config.force * 250)}%
              </span>
            </span>
            <input
              type="range"
              min={0}
              max={0.4}
              step={0.01}
              value={config.force}
              onChange={(e) => apply({ ...config, force: Number(e.target.value) })}
              className="mt-1.5 w-full accent-[var(--accent)]"
            />
          </label>

          <p className="mt-3 text-[10px] leading-relaxed text-[var(--muted)]">
            密度调 0 可关闭特效；引力控制鼠标附近粒子的吸附幅度
          </p>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="粒子特效设置"
        title="粒子特效设置"
        className={`neon-btn flex h-10 w-10 items-center justify-center rounded-full text-base ${
          open ? "shadow-[0_0_20px_rgba(0,229,255,0.45)]" : ""
        }`}
      >
        ✦
      </button>
    </div>
  );
}
