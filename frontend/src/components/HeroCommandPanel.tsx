import React, { useState } from 'react';
import { ArrowUpRight, Sparkles, Square, Activity } from 'lucide-react';
import { ProjectStateSnapshot } from '../types/state';

interface HeroCommandPanelProps {
  onStartBuild: (goal: string, language: string) => void;
  isLoading: boolean;
  onExploreScroll?: () => void;
  isBuilding?: boolean;
  state?: ProjectStateSnapshot;
  onStop?: () => void;
}

const PRESETS = [
  {
    label: 'Interactive 3D Portfolio',
    prompt: 'Build an interactive 3D portfolio website with Three.js, React 18, and smooth cinematic navigation',
    stack: 'React + Three.js',
  },
  {
    label: 'FastAPI Microservice',
    prompt: 'Build a high-performance Python FastAPI service with REST endpoints, health verification, and data validation',
    stack: 'FastAPI',
  },
  {
    label: 'Algorithmic Visualizer',
    prompt: 'Create a procedural WebGL audio-reactive particle environment with GLSL shaders and real-time interaction',
    stack: 'HTML/CSS/JS',
  },
];

export const HeroCommandPanel: React.FC<HeroCommandPanelProps> = ({
  onStartBuild,
  isLoading,
  onExploreScroll,
  isBuilding = false,
  state,
  onStop,
}) => {
  const [prompt, setPrompt] = useState('');
  const [selectedStack, setSelectedStack] = useState('Auto Detect');
  const [isFocused, setIsFocused] = useState(false);
  const [isContracting, setIsContracting] = useState(false);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isLoading || isContracting) return;
    setIsContracting(true);
    setTimeout(() => {
      onStartBuild(prompt.trim(), selectedStack);
    }, 350);
  };

  // If active build is running, render an ultra-compact, non-intrusive build telemetry monitor
  // docked cleanly in the upper corner so the 3D environment has full visual dominance
  if (isBuilding && state) {
    return (
      <div className="w-full max-w-sm ml-6 sm:ml-12 mt-16 pointer-events-auto select-none transition-all duration-500">
        <div className="glass-panel p-4 rounded-xl border border-white/[0.08] backdrop-blur-2xl shadow-subtle">
          {/* Header */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
              <span className="font-mono text-[10px] uppercase tracking-widest text-sky-400 font-semibold">
                {state.current_phase} // RUNNING
              </span>
            </div>
            {onStop && (
              <button
                onClick={onStop}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20 font-mono text-[9px] transition-all cursor-pointer"
                title="Interrupt Build"
              >
                <Square className="w-2 h-2 fill-rose-300" />
                <span>STOP</span>
              </button>
            )}
          </div>

          {/* Goal Title */}
          <p className="font-body text-xs text-white font-medium line-clamp-2 leading-snug mb-3">
            {state.goal || 'Autonomous software engineering build in progress...'}
          </p>

          {/* Active Agent & File Target */}
          <div className="flex flex-col gap-1.5 py-2 border-t border-white/[0.06] font-mono text-[10px]">
            <div className="flex items-center justify-between text-slate-400">
              <span className="uppercase text-slate-500">Agent:</span>
              <span className="text-sky-300 font-medium">{state.active_agent || 'DEVELOPER'}</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span className="uppercase text-slate-500">Target:</span>
              <span className="text-slate-300 truncate max-w-[180px]">
                {state.current_file_target || state.current_task_description}
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="pt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between font-mono text-[9px] text-slate-400 mb-1">
              <span>PROGRESS</span>
              <span className="text-sky-400 font-semibold">{state.progress_percent}%</span>
            </div>
            <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-sky-400 to-emerald-400 transition-all duration-300"
                style={{ width: `${Math.max(state.progress_percent, 5)}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col justify-center min-h-[80vh] px-6 sm:px-10 pointer-events-auto select-none">
      {/* 1. Controlled Editorial Typography */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
          <span className="font-mono text-[9px] uppercase tracking-[0.25em] text-slate-400 font-medium">
            SPIDY // AUTONOMOUS SOFTWARE ENGINEERING
          </span>
        </div>

        <h1 className="font-display text-[clamp(1.8rem,3.2vw,2.8rem)] font-bold tracking-tight text-white leading-tight">
          AI THAT BUILDS <span className="text-gradient-electric">SOFTWARE.</span>
        </h1>

        <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed max-w-lg mt-2.5">
          Describe the system you need. SPIDY plans, synthesizes, verifies, and self-heals
          production code in an isolated runtime environment.
        </p>
      </div>

      {/* 2. Refined Command Interface */}
      <div className="w-full max-w-2xl">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div
            className={`transition-all duration-500 rounded-xl p-4 border ${
              isContracting
                ? 'scale-95 opacity-60 translate-y-2 border-sky-400 shadow-[0_0_30px_rgba(56,189,248,0.4)]'
                : isFocused
                ? 'bg-slate-950/75 border-sky-400/40 shadow-glow-electric'
                : 'bg-slate-950/45 border-white/[0.08] hover:border-white/[0.14]'
            } backdrop-blur-xl`}
          >
            <div className="flex items-center justify-between mb-2 text-slate-400 font-mono text-[10px] uppercase tracking-wider">
              <span className="flex items-center gap-1.5 text-sky-400/90 font-medium">
                <Sparkles className="w-3 h-3 text-sky-400" />
                COMMAND PORTAL
              </span>
              <span className="text-slate-500 hidden sm:inline text-[9px]">
                AUTONOMOUS MULTI-AGENT
              </span>
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Describe software requirement (e.g. 'Build an interactive 3D solar system with Three.js', 'FastAPI microservice with health checks')..."
              rows={2}
              className="w-full bg-transparent text-white placeholder-slate-500 font-mono text-xs sm:text-sm outline-none resize-none leading-relaxed"
            />

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pt-2.5 border-t border-white/[0.06] mt-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] uppercase text-slate-500 tracking-wider">
                  Target Stack:
                </span>
                <select
                  value={selectedStack}
                  onChange={(e) => setSelectedStack(e.target.value)}
                  className="bg-black/60 text-slate-300 border border-white/[0.08] rounded-md px-2 py-0.5 font-mono text-[11px] outline-none focus:border-sky-400/40 transition-colors"
                >
                  <option value="Auto Detect">Auto Detect</option>
                  <option value="React + Three.js">React + Three.js</option>
                  <option value="FastAPI">FastAPI</option>
                  <option value="TypeScript">TypeScript</option>
                  <option value="HTML/CSS/JS">HTML/CSS/JS</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={!prompt.trim() || isLoading || isContracting}
                className={`flex items-center justify-center gap-1.5 px-4 py-1.5 rounded-lg font-mono text-[11px] uppercase tracking-wider font-semibold transition-all duration-200 ${
                  prompt.trim() && !isLoading && !isContracting
                    ? 'bg-sky-400 hover:bg-sky-300 text-slate-950 shadow-[0_0_20px_rgba(56,189,248,0.35)] hover:scale-[1.02] cursor-pointer'
                    : 'bg-white/[0.06] text-slate-500 cursor-not-allowed'
                }`}
              >
                <span>{isContracting ? 'INGESTING...' : isLoading ? 'INITIATING...' : 'BUILD'}</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Preset Chips */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[9px] uppercase tracking-wider text-slate-500 mr-1">
              Presets:
            </span>
            {PRESETS.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setPrompt(preset.prompt);
                  setSelectedStack(preset.stack);
                }}
                className="font-mono text-[10px] tracking-wide px-2.5 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 border border-white/[0.06] hover:border-white/[0.14] transition-all cursor-pointer"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </form>

        {/* Minimal Scroll Indicator */}
        {onExploreScroll && (
          <div
            onClick={onExploreScroll}
            className="mt-6 inline-flex items-center gap-2 text-slate-500 hover:text-sky-400 transition-colors font-mono text-[10px] tracking-[0.2em] uppercase cursor-pointer select-none"
          >
            <span>SCROLL TO EXPLORE ARCHITECTURE</span>
            <span className="animate-bounce">↓</span>
          </div>
        )}
      </div>
    </div>
  );
};
