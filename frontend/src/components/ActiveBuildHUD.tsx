import React from 'react';
import { ProjectStateSnapshot } from '../types/state';
import { Square } from 'lucide-react';

interface ActiveBuildHUDProps {
  state: ProjectStateSnapshot;
  onStop: () => void;
}

export const ActiveBuildHUD: React.FC<ActiveBuildHUDProps> = ({ state, onStop }) => {
  const getPhaseName = () => {
    switch (state.current_phase) {
      case 'PLAN':
        return 'PLANNING';
      case 'ARCHITECT':
        return 'ARCHITECTING';
      case 'BUILD':
        return 'BUILDING';
      case 'RUN':
        return 'RUNNING';
      case 'TEST':
        return 'TESTING';
      case 'REVIEW':
      case 'VERIFY':
        return 'VERIFYING';
      case 'DEBUG':
        return 'REPAIRING';
      default:
        return state.current_phase || 'EXECUTING';
    }
  };

  return (
    <div className="fixed inset-x-0 bottom-5 flex justify-center pointer-events-none px-4 z-40">
      <div className="relative pointer-events-auto flex items-center gap-3 px-4 py-1.5 rounded-full bg-slate-950/75 border border-white/[0.08] backdrop-blur-xl shadow-subtle select-none">
        {/* Phase Indicator */}
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-white font-semibold">
            {getPhaseName()}
          </span>
        </div>

        <span className="text-slate-700">•</span>

        {/* Active Agent */}
        <div className="flex items-center gap-1 font-mono text-[10px] text-slate-300">
          <span className="text-slate-500 uppercase">Agent:</span>
          <span className="text-sky-300 font-medium">{state.active_agent || 'DEVELOPER'}</span>
        </div>

        <span className="text-slate-700 hidden sm:inline">•</span>

        {/* Current File or Task */}
        <div className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-slate-400 max-w-xs truncate">
          {state.current_file_target ? (
            <span className="text-slate-300 truncate font-mono">{state.current_file_target}</span>
          ) : (
            <span className="truncate">{state.current_task_description}</span>
          )}
        </div>

        <span className="text-slate-700">•</span>

        {/* Progress percent */}
        <div className="font-mono text-[10px] text-sky-400 font-semibold">
          {state.progress_percent}%
        </div>

        {/* Elapsed */}
        <div className="hidden md:flex font-mono text-[10px] text-slate-500">
          {state.formatted_elapsed}
        </div>

        {/* Stop action */}
        <button
          onClick={onStop}
          className="ml-1 flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20 font-mono text-[9px] transition-all cursor-pointer"
          title="Interrupt Build"
        >
          <Square className="w-2 h-2 fill-rose-300" />
          <span>STOP</span>
        </button>

        {/* Integrated bottom progress line */}
        <div className="absolute inset-x-4 bottom-0 h-[1.5px] bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-sky-400 to-emerald-400 transition-all duration-300"
            style={{ width: `${Math.max(state.progress_percent, 5)}%` }}
          />
        </div>
      </div>
    </div>
  );
};
