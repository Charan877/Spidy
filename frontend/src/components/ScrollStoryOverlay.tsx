import React, { useState, useEffect } from 'react';
import { HeroCommandPanel } from './HeroCommandPanel';
import { ProjectStateSnapshot } from '../types/state';
import { ExternalLink, CheckCircle, AlertTriangle } from 'lucide-react';

interface ScrollStoryOverlayProps {
  state: ProjectStateSnapshot;
  scrollProgress: number; // 0.0 to 1.0
  onStartBuild: (goal: string, language: string) => void;
  isLoading: boolean;
  onScrollToSection: (sectionIndex: number) => void;
  onOpenWorkspace: () => void;
}

const STAGES = [
  { index: 0, tag: '00', title: 'INTRO', sub: 'The Dormant Computational Space' },
  { index: 1, tag: '01', title: 'DESTRUCTURING.', sub: 'Natural intent to verified interface contracts' },
  { index: 2, tag: '02', title: 'TOPOLOGY.', sub: 'Directed acyclic dependency graph emergence' },
  { index: 3, tag: '03', title: 'SYNTHESIS.', sub: 'Parallel multi-file code synthesis on disk' },
  { index: 4, tag: '04', title: 'PROBING.', sub: 'Runtime execution and health validation' },
  { index: 5, tag: '05', title: 'SELF-HEALING.', sub: 'Autonomous fault isolation and hot-swap recovery' },
  { index: 6, tag: '06', title: 'CONVERGENCE.', sub: 'Deterministic six-gate validation matrix' },
  { index: 7, tag: '07', title: 'BUILT.', title2: 'VERIFIED.', sub: 'Stabilized production monument' },
];

export const ScrollStoryOverlay: React.FC<ScrollStoryOverlayProps> = ({
  state,
  scrollProgress,
  onStartBuild,
  isLoading,
  onScrollToSection,
  onOpenWorkspace,
}) => {
  const p = Math.max(0, Math.min(1, scrollProgress));
  const activeIndex = Math.min(7, Math.floor(p * 8));

  // Opacity bell curve strictly preventing text collision between stages
  const getStageOpacity = (stageIndex: number) => {
    const center = stageIndex / 7;
    const dist = Math.abs(p - center);
    if (dist > 0.09) return 0;
    return Math.cos((dist / 0.09) * (Math.PI / 2));
  };

  const isBuilding =
    state.is_running ||
    ['PLAN', 'ARCHITECT', 'BUILD', 'DEBUG', 'TEST', 'RUN', 'REVIEW'].includes(
      state.current_phase
    );

  // Staggered reveal for Result stage
  const [showVerified, setShowVerified] = useState(false);
  useEffect(() => {
    if (activeIndex === 7) {
      const timer = setTimeout(() => setShowVerified(true), 400);
      return () => clearTimeout(timer);
    } else {
      setShowVerified(false);
    }
  }, [activeIndex]);

  return (
    <div className="relative w-full z-10 pointer-events-none">
      {/* 1. Ultra-Minimal Vertical Scrubber Track */}
      <nav className="fixed right-5 top-1/2 -translate-y-1/2 z-40 hidden md:flex flex-col gap-2.5 pointer-events-auto select-none">
        {STAGES.map((s) => {
          const isActive = s.index === activeIndex;
          return (
            <button
              key={s.tag}
              onClick={() => onScrollToSection(s.index)}
              className="flex items-center gap-2 group transition-all cursor-pointer py-0.5"
              title={s.sub}
            >
              <span
                className={`font-mono text-[9px] tracking-widest transition-all duration-300 ${
                  isActive
                    ? 'text-sky-400 font-semibold opacity-100'
                    : 'text-slate-600 group-hover:text-slate-400 opacity-40'
                }`}
              >
                {s.tag}
              </span>
              <span
                className={`h-[1px] rounded-full transition-all duration-300 ${
                  isActive
                    ? 'w-5 bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.8)]'
                    : 'w-2 bg-white/20 group-hover:bg-white/40'
                }`}
              />
            </button>
          );
        })}
      </nav>

      {/* 2. Full-Screen Disciplined Editorial Viewport */}
      <div className="fixed inset-0 w-full h-full pointer-events-none flex items-center justify-center">
        {/* STAGE 00: HERO COMMAND */}
        <div
          style={{ opacity: getStageOpacity(0), pointerEvents: activeIndex === 0 ? 'auto' : 'none' }}
          className="absolute inset-0 flex items-center justify-center p-6 sm:p-10 transition-opacity duration-300"
        >
          <HeroCommandPanel
            onStartBuild={onStartBuild}
            isLoading={isLoading}
            onExploreScroll={() => onScrollToSection(1)}
            isBuilding={isBuilding}
            state={state}
          />
        </div>

        {/* STAGE 01: DESTRUCTURING. (Asymmetrical Left, Unobstructed 3D Center) */}
        <div
          style={{ opacity: getStageOpacity(1), pointerEvents: activeIndex === 1 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-start pl-8 sm:pl-16 lg:pl-24 max-w-lg select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-sky-400/90 mb-2 font-medium">
            01 // LINGUISTIC INTENT
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-white leading-tight">
            DESTRUCTURING.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Requirements ingested into multi-dimensional semantic vectors and interface contracts.
          </p>
        </div>

        {/* STAGE 02: TOPOLOGY. (Asymmetrical Right, Unobstructed 3D Center) */}
        <div
          style={{ opacity: getStageOpacity(2), pointerEvents: activeIndex === 2 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-end pr-8 sm:pr-16 lg:pr-24 max-w-lg ml-auto text-right select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-sky-400/90 mb-2 font-medium">
            02 // ARCHITECTURAL REIFICATION
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-white leading-tight">
            TOPOLOGY.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Directed acyclic dependency graphs materialize into spatial coordinates.
          </p>
        </div>

        {/* STAGE 03: SYNTHESIS. (Asymmetrical Left) */}
        <div
          style={{ opacity: getStageOpacity(3), pointerEvents: activeIndex === 3 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-start pl-8 sm:pl-16 lg:pl-24 max-w-lg select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-sky-400/90 mb-2 font-medium">
            03 // CODE SYNTHESIS
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-white leading-tight">
            SYNTHESIS.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Multi-agent compilation engines writing verified production files directly to disk.
          </p>
        </div>

        {/* STAGE 04: PROBING. (Asymmetrical Right) */}
        <div
          style={{ opacity: getStageOpacity(4), pointerEvents: activeIndex === 4 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-end pr-8 sm:pr-16 lg:pr-24 max-w-lg ml-auto text-right select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-cyan-400 mb-2 font-medium">
            04 // RUNTIME EXECUTION
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-white leading-tight">
            PROBING.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Dynamic free port allocation, real process execution, and HTTP health validation.
          </p>
        </div>

        {/* STAGE 05: SELF-HEALING. (Asymmetrical Left) */}
        <div
          style={{ opacity: getStageOpacity(5), pointerEvents: activeIndex === 5 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-start pl-8 sm:pl-16 lg:pl-24 max-w-lg select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-400 mb-2 font-medium">
            05 // ANOMALY CONTAINMENT
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-amber-400 leading-tight">
            SELF-HEALING.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Runtime exceptions isolated into containment and repaired by hot-swap regeneration.
          </p>
        </div>

        {/* STAGE 06: CONVERGENCE. (Asymmetrical Right) */}
        <div
          style={{ opacity: getStageOpacity(6), pointerEvents: activeIndex === 6 ? 'auto' : 'none' }}
          className="absolute inset-0 flex flex-col justify-center items-end pr-8 sm:pr-16 lg:pr-24 max-w-lg ml-auto text-right select-none transition-opacity duration-300"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-emerald-400 mb-2 font-medium">
            06 // INTEGRITY AUDIT
          </div>
          <h2 className="font-display text-[clamp(2.0rem,3.8vw,3.2rem)] font-bold tracking-tight text-white leading-tight">
            CONVERGENCE.
          </h2>
          <p className="font-body text-xs sm:text-sm text-slate-400 font-normal leading-relaxed mt-2.5">
            Monolithic crystalline alignment as all six verification gates validate simultaneously.
          </p>
        </div>

        {/* STAGE 07: BUILT. / VERIFIED. or FAILED. (Product Reveal: Reflects Authoritative Pipeline State) */}
        {(() => {
          const isFailed =
            ['FAILED', 'BLOCKED'].includes(state.current_phase) ||
            ['FAILED', 'BLOCKED'].includes(state.project_state) ||
            ['FAILED', 'BLOCKED'].includes(state.runtime_status) ||
            Boolean(state.has_failed_required_tasks && state.current_phase !== 'BUILD' && state.current_phase !== 'DISCOVER');

          const isVerifiedSuccess =
            !isFailed &&
            state.current_phase === 'COMPLETE' &&
            state.project_state === 'SUCCESS' &&
            state.project_success &&
            !state.has_failed_required_tasks &&
            (!state.is_web_project || state.is_app_verified);

          return (
            <div
              style={{ opacity: getStageOpacity(7), pointerEvents: activeIndex === 7 ? 'auto' : 'none' }}
              className="absolute inset-x-0 bottom-12 flex flex-col justify-end items-center px-6 text-center select-none transition-opacity duration-300"
            >
              {isFailed ? (
                <>
                  <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-rose-400 font-medium mb-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    <span>PIPELINE VERIFICATION FAILED</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <h2 className="font-display text-[clamp(2.2rem,4.5vw,3.6rem)] font-bold tracking-tight text-white leading-none">
                      BUILD.
                    </h2>
                    <h2 className="font-display text-[clamp(2.2rem,4.5vw,3.6rem)] font-bold tracking-tight text-rose-400 leading-none">
                      HALTED.
                    </h2>
                  </div>

                  <p className="font-body text-xs text-rose-300/80 font-normal mt-2 max-w-md">
                    {state.failure_reason || state.failure_classification || 'Prerequisite verification gates were not satisfied.'}
                  </p>

                  <div className="mt-4 flex items-center justify-center gap-3 pointer-events-auto">
                    <button
                      onClick={onOpenWorkspace}
                      className="flex items-center gap-1.5 px-5 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30 transition-all cursor-pointer"
                    >
                      <span>INSPECT WORKSPACE</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </>
              ) : isVerifiedSuccess ? (
                <>
                  <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-emerald-400 font-medium mb-2">
                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                    <span>SIX-GATE CONVERGENCE VERIFIED</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <h2 className="font-display text-[clamp(2.2rem,4.5vw,3.6rem)] font-bold tracking-tight text-white leading-none">
                      BUILT.
                    </h2>
                    <h2
                      className={`font-display text-[clamp(2.2rem,4.5vw,3.6rem)] font-bold tracking-tight text-gradient-emerald leading-none transition-all duration-500 ${
                        showVerified ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
                      }`}
                    >
                      VERIFIED.
                    </h2>
                  </div>

                  <p className="font-body text-xs text-slate-400 font-normal mt-2 max-w-md">
                    The software pipeline has synthesized and validated. Ready for deployment.
                  </p>

                  <div className="mt-4 flex items-center justify-center gap-3 pointer-events-auto">
                    {state.runtime_url ? (
                      <a
                        href={state.runtime_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1.5 px-5 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-white text-black hover:bg-sky-200 transition-all cursor-pointer shadow-[0_0_20px_rgba(255,255,255,0.3)]"
                      >
                        <span>OPEN APPLICATION</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <button
                        onClick={onOpenWorkspace}
                        className="flex items-center gap-1.5 px-5 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-medium bg-white/[0.08] hover:bg-white/[0.14] text-white border border-white/[0.12] transition-all cursor-pointer"
                      >
                        <span>INSPECT WORKSPACE</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-sky-400 font-medium mb-2">
                    <span>07 // CONVERGENCE GATE</span>
                  </div>
                  <h2 className="font-display text-[clamp(2.2rem,4.5vw,3.6rem)] font-bold tracking-tight text-slate-400 leading-none">
                    STABILIZING...
                  </h2>
                  <p className="font-body text-xs text-slate-500 font-normal mt-2 max-w-md">
                    Awaiting pipeline completion and verification gate satisfaction.
                  </p>
                </>
              )}
            </div>
          );
        })()}
      </div>

      {/* 3. The 800vh Continuous Scroll Track */}
      <div className="h-[800vh] w-full" />
    </div>
  );
};
