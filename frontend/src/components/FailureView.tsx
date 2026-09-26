import React from 'react';
import { ProjectStateSnapshot } from '../types/state';
import { AlertTriangle, Wrench, RotateCcw } from 'lucide-react';

interface FailureViewProps {
  state: ProjectStateSnapshot;
  onOpenDiagnostics: () => void;
  onReset: () => void;
}

export const FailureView: React.FC<FailureViewProps> = ({
  state,
  onOpenDiagnostics,
  onReset,
}) => {
  const isInterrupted = ['EXECUTION_INTERRUPTED', 'SERVER_RESTARTED_MID_BUILD', 'USER_CANCELLED'].includes(
    state.failure_classification || ''
  );
  const classification = state.failure_classification || (isInterrupted ? 'EXECUTION_INTERRUPTED' : 'EXECUTION_FAILURE');
  const headline = isInterrupted ? 'BUILD INTERRUPTED.' : 'BUILD FAILED.';
  const subhead = isInterrupted ? 'Pipeline Interrupted' : 'Pipeline Failure';
  const reason =
    state.failure_reason || 'Verification check did not satisfy prerequisite conditions.';

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-4 z-20">
      <div className="w-full max-w-lg glass-panel rounded-2xl p-6 pointer-events-auto text-center flex flex-col items-center shadow-2xl border-rose-500/30">
        <div className="w-12 h-12 rounded-full bg-rose-500/20 border border-rose-400/40 flex items-center justify-center mb-4 text-rose-400">
          <AlertTriangle className="w-6 h-6" />
        </div>

        <div className="font-mono text-xs uppercase tracking-[0.2em] text-rose-400 mb-1">
          {subhead}
        </div>

        <h2 className="font-display text-3xl font-extrabold text-white tracking-tight mb-2">
          {headline}
        </h2>

        <div className="font-mono text-sm text-rose-300 font-semibold mb-2">
          {classification}
        </div>


        {/* Diagnostic Metadata Grid */}
        <div className="w-full bg-slate-950/80 rounded-xl p-3.5 border border-rose-500/20 text-left mb-4 space-y-2">
          <div className="grid grid-cols-2 gap-2 pb-2 border-b border-white/5 font-mono text-[10px]">
            <div>
              <span className="text-slate-500 uppercase">Target Port:</span>{' '}
              <span className="text-white font-semibold">{state.runtime_port || 'None / Not Bound'}</span>
            </div>
            <div>
              <span className="text-slate-500 uppercase">Status:</span>{' '}
              <span className="text-rose-400 font-semibold">{state.runtime_status || 'INTERRUPTED'}</span>
            </div>
            {state.runtime_command && (
              <div className="col-span-2 truncate">
                <span className="text-slate-500 uppercase">Command:</span>{' '}
                <span className="text-slate-300">{state.runtime_command}</span>
              </div>
            )}
          </div>

          {/* Verification Gates Checklist */}
          {state.verification_gates && (
            <div className="flex items-center gap-1.5 pt-1">
              <span className="text-[9px] font-mono text-slate-500 uppercase mr-1">Gates:</span>
              {Object.entries(state.verification_gates).map(([gate, passed]) => (
                <span
                  key={gate}
                  className={`text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase ${
                    passed
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-400 font-semibold'
                  }`}
                >
                  {gate}: {passed ? 'OK' : 'FAIL'}
                </span>
              ))}
            </div>
          )}

          {/* Root cause / Error details */}
          <div className="pt-1">
            <span className="text-[10px] font-mono uppercase text-rose-400/80 font-bold block mb-1">
              Root Cause Diagnostics:
            </span>
            <pre className="font-mono text-[10.5px] text-rose-200/90 whitespace-pre-wrap break-all bg-black/60 p-2.5 rounded border border-rose-500/20 max-h-32 overflow-y-auto leading-relaxed">
              {reason}
            </pre>
          </div>
        </div>

        <div className="font-mono text-xs text-slate-400 mb-6">
          Recovery attempts:{' '}
          <span className="text-white font-semibold">{state.recovery_attempts} / 3</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 w-full">
          <button
            onClick={onOpenDiagnostics}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-500 to-amber-500 hover:from-rose-600 hover:to-amber-600 text-white font-mono text-xs uppercase tracking-wider font-semibold shadow-lg shadow-rose-500/25 transition-all"
          >
            <Wrench className="w-4 h-4" />
            <span>VIEW DIAGNOSTICS & RECOVERY</span>
          </button>

          <button
            onClick={onReset}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-slate-300 font-mono text-xs uppercase tracking-wider transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span>RESET</span>
          </button>
        </div>
      </div>
    </div>
  );
};
