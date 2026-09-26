import React from 'react';
import { ProjectStateSnapshot } from '../types/state';

interface NavigationProps {
  state: ProjectStateSnapshot;
  activeDrawer: string | null;
  onToggleDrawer: (drawer: string | null) => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  state,
  activeDrawer,
  onToggleDrawer,
}) => {
  const getStatusLabel = () => {
    if (state.current_phase === 'COMPLETE' && state.project_success) return 'VERIFIED';
    if (state.current_phase === 'FAILED') {
      const isInterrupted = ['EXECUTION_INTERRUPTED', 'SERVER_RESTARTED_MID_BUILD', 'USER_CANCELLED'].includes(
        state.failure_classification || ''
      );
      return isInterrupted ? 'INTERRUPTED' : 'FAILED';
    }
    if (state.current_phase === 'BLOCKED') return 'BLOCKED';
    if (!state.is_running) return 'READY';
    if (state.current_phase === 'PLAN') return 'PLANNING';
    if (state.current_phase === 'ARCHITECT') return 'ARCHITECTING';
    if (state.current_phase === 'BUILD') return 'BUILDING';
    if (state.current_phase === 'RUN') return 'RUNNING';
    if (state.current_phase === 'TEST') return 'TESTING';
    if (state.current_phase === 'DEBUG') return 'REPAIRING';
    if (state.current_phase === 'REVIEW') return 'VERIFYING';
    return state.current_phase || 'READY';
  };

  const getStatusColor = () => {
    const s = getStatusLabel();
    if (s === 'VERIFIED' || s === 'RUNNING') return 'bg-emerald-400';
    if (['BUILDING', 'PLANNING', 'ARCHITECTING'].includes(s)) return 'bg-sky-400';
    if (s === 'REPAIRING') return 'bg-amber-400';
    if (s === 'INTERRUPTED' || s === 'FAILED' || s === 'BLOCKED') return 'bg-rose-400';
    return 'bg-slate-400';
  };


  const drawers = ['Workspace', 'Activity', 'Runtime', 'Agents', 'Diagnostics', 'Projects'];

  return (
    <header className="fixed top-0 left-0 right-0 z-40 px-6 py-3 flex items-center justify-between pointer-events-auto select-none">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <span className="font-display text-sm font-bold tracking-[0.25em] text-white">
          SPIDY
        </span>
        <span className="hidden sm:inline-block font-mono text-[9px] tracking-[0.2em] uppercase text-slate-500 pl-2.5 border-l border-white/[0.08]">
          Autonomous Software Engineering
        </span>
      </div>

      {/* Center Drawer Navigation */}
      <nav className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-950/50 border border-white/[0.08] backdrop-blur-md">
        {drawers.map((name) => {
          const isActive = activeDrawer === name;
          return (
            <button
              key={name}
              onClick={() => onToggleDrawer(isActive ? null : name)}
              className={`px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider transition-all duration-150 cursor-pointer ${
                isActive
                  ? 'bg-white/[0.12] text-white font-medium'
                  : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
              }`}
            >
              {name}
            </button>
          );
        })}
      </nav>

      {/* Status Pill */}
      <div className="flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-slate-950/50 border border-white/[0.08] backdrop-blur-md">
        <span className={`w-1.5 h-1.5 rounded-full ${getStatusColor()}`} />
        <span className="font-mono text-[9px] uppercase tracking-widest text-slate-300 font-medium">
          {getStatusLabel()}
        </span>
      </div>
    </header>
  );
};
