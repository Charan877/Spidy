import React, { useState, useEffect } from 'react';
import { ProjectStateSnapshot } from '../types/state';
import { ExternalLink, Folder, RotateCcw, CheckCircle, BookOpen, Globe, Terminal, Send, Sparkles } from 'lucide-react';

interface SuccessViewProps {
  state: ProjectStateSnapshot;
  onOpenWorkspace: () => void;
  onReset: () => void;
  onSendMessage?: (message: string) => void;
}

export const SuccessView: React.FC<SuccessViewProps> = ({
  state,
  onOpenWorkspace,
  onReset,
  onSendMessage,
}) => {
  const [showConsole, setShowConsole] = useState(false);
  const [showVerified, setShowVerified] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [followUpText, setFollowUpText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFollowUpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!followUpText.trim() || isSubmitting) return;
    setIsSubmitting(true);
    if (onSendMessage) {
      onSendMessage(followUpText.trim());
    }
  };

  useEffect(() => {
    // 1. Initial 1.2s pause: Camera pulls back, monument stabilizes, data slows
    const tConsole = setTimeout(() => setShowConsole(true), 1200);

    // 2. Pause: Reveal 'BUILT.', then 900ms later reveal 'VERIFIED.'
    const tVerified = setTimeout(() => setShowVerified(true), 2100);

    // 3. Reveal application runtime launch controls
    const tControls = setTimeout(() => setShowControls(true), 2800);

    return () => {
      clearTimeout(tConsole);
      clearTimeout(tVerified);
      clearTimeout(tControls);
    };
  }, []);

  const runtimeType = state.runtime_type || (state.is_web_project ? 'web' : 'cli');
  const targets = state.runtime_targets || [];

  // Extract verified endpoints
  const apiTarget =
    targets.find((t) => t.type === 'api') ||
    (runtimeType === 'api' && state.runtime_url
      ? { url: state.runtime_url, port: state.runtime_port || 9000, name: 'API Service' }
      : null);

  const docsTarget =
    targets.find((t) => t.type === 'docs') ||
    (runtimeType === 'api' && state.runtime_url
      ? { url: `${state.runtime_url.replace(/\/$/, '')}/docs`, port: state.runtime_port || 9000, name: 'API Docs' }
      : null);

  const webTarget =
    targets.find((t) => t.type === 'web') ||
    (runtimeType === 'web' && state.runtime_url
      ? { url: state.runtime_url, port: state.runtime_port || 5173, name: 'Web Application' }
      : null);

  const isFullstack = runtimeType === 'fullstack' || (Boolean(webTarget) && Boolean(apiTarget));
  const isApi = !isFullstack && runtimeType === 'api';
  const isWeb = !isFullstack && (runtimeType === 'web' || Boolean(webTarget));
  const isCliOrLib = !isFullstack && !isApi && !isWeb;

  // Type-specific badge label
  const typeBadgeLabel = isFullstack
    ? 'FULL-STACK CONVERGENCE'
    : isApi
    ? 'API SERVICE VERIFIED'
    : isWeb
    ? 'WEB APPLICATION VERIFIED'
    : 'EXECUTABLE / PACKAGE VERIFIED';

  return (
    <div
      className={`fixed inset-0 flex flex-col justify-end items-center pointer-events-none px-6 pb-12 z-30 select-none transition-opacity duration-700 ${
        showConsole ? 'opacity-100' : 'opacity-0'
      }`}
    >
      {/* 3D background remains completely visible; UI is positioned as an elegant bottom reveal console */}
      <div className="w-full max-w-xl pointer-events-auto text-center flex flex-col items-center p-6 rounded-2xl glass-panel shadow-subtle border border-white/[0.08] backdrop-blur-xl">
        {/* Verification Status Pill */}
        <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-400/25 text-emerald-400 font-mono text-[10px] uppercase tracking-[0.25em] mb-4">
          <CheckCircle className="w-3 h-3 text-emerald-400" />
          <span>{typeBadgeLabel}</span>
        </div>

        {/* Product-Reveal Restrained Headline */}
        <div className="flex items-center justify-center gap-3 mb-2">
          <h1 className="font-display text-[clamp(2.2rem,4.5vw,3.4rem)] font-bold text-white tracking-tight leading-none">
            BUILT.
          </h1>
          <h1
            className={`font-display text-[clamp(2.2rem,4.5vw,3.4rem)] font-bold text-gradient-emerald tracking-tight leading-none transition-all duration-700 ${
              showVerified ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
            }`}
          >
            VERIFIED.
          </h1>
        </div>

        {/* Project Name & Framework Subtitle */}
        <p className="font-mono text-[11px] text-slate-400 mb-4 max-w-sm tracking-wide truncate">
          {state.project_name || 'Autonomous Engineering Pipeline'}
          {state.project_type && (
            <span className="text-slate-500 font-normal"> — {state.project_type}</span>
          )}
        </p>

        {/* Project-Type-Aware Telemetry Metadata */}
        <div className="flex flex-wrap items-center justify-center gap-4 font-mono text-[10px] text-slate-400 mb-5 py-1.5 px-4 rounded-full bg-black/40 border border-white/[0.06]">
          {isFullstack ? (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">FRONTEND:</span>
                <span className="text-sky-300 font-medium">PORT {webTarget?.port || state.runtime_port || 5173}</span>
              </div>
              <span className="text-slate-700">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">BACKEND:</span>
                <span className="text-emerald-300 font-medium">PORT {apiTarget?.port || 8000}</span>
              </div>
            </>
          ) : isApi ? (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">API PORT:</span>
                <span className="text-sky-300 font-medium">{state.runtime_port || 9000}</span>
              </div>
              <span className="text-slate-700">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">PID:</span>
                <span className="text-slate-200">{state.runtime_pid || 'ACTIVE'}</span>
              </div>
            </>
          ) : isWeb ? (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">WEB PORT:</span>
                <span className="text-sky-300 font-medium">{state.runtime_port || 5173}</span>
              </div>
              <span className="text-slate-700">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">PID:</span>
                <span className="text-slate-200">{state.runtime_pid || 'ACTIVE'}</span>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">STATUS:</span>
                <span className="text-emerald-400 font-medium">VERIFIED</span>
              </div>
              <span className="text-slate-700">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-500 uppercase">TARGET:</span>
                <span className="text-slate-200">{state.project_type || 'CLI Application'}</span>
              </div>
            </>
          )}

          <span className="text-slate-700">•</span>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase">SYNTHESIS:</span>
            <span className="text-emerald-400 font-medium">{state.files_count} files</span>
          </div>
          <span className="text-slate-700">•</span>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase">TIME:</span>
            <span className="text-slate-300">{state.formatted_elapsed}</span>
          </div>
        </div>

        {/* Dynamic Project-Type-Aware Action Controls */}
        <div
          className={`flex flex-wrap items-center justify-center gap-3 transition-all duration-700 ${
            showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
          }`}
        >
          {/* 1. Fullstack Actions */}
          {isFullstack && (
            <>
              {webTarget?.url && (
                <a
                  href={webTarget.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-5 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-white text-black hover:bg-sky-200 shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-[1.02] transition-all cursor-pointer"
                >
                  <Globe className="w-3.5 h-3.5" />
                  <span>OPEN APPLICATION</span>
                  <ExternalLink className="w-3 h-3 text-slate-600" />
                </a>
              )}
              {apiTarget?.url && (
                <a
                  href={apiTarget.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-400/30 transition-all cursor-pointer"
                >
                  <Terminal className="w-3.5 h-3.5 text-sky-400" />
                  <span>OPEN API</span>
                  <ExternalLink className="w-3 h-3 text-sky-400/70" />
                </a>
              )}
            </>
          )}

          {/* 2. Single API Service Actions */}
          {isApi && (
            <>
              {apiTarget?.url && (
                <a
                  href={apiTarget.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-5 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-white text-black hover:bg-sky-200 shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-[1.02] transition-all cursor-pointer"
                >
                  <Terminal className="w-3.5 h-3.5" />
                  <span>OPEN API</span>
                  <ExternalLink className="w-3 h-3 text-slate-600" />
                </a>
              )}
              {docsTarget?.url && (
                <a
                  href={docsTarget.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 transition-all cursor-pointer"
                >
                  <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                  <span>OPEN API DOCS</span>
                  <ExternalLink className="w-3 h-3 text-emerald-400/70" />
                </a>
              )}
            </>
          )}

          {/* 3. Single Web Application Actions */}
          {isWeb && webTarget?.url && (
            <a
              href={webTarget.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-6 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold bg-white text-black hover:bg-sky-200 shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-[1.02] transition-all cursor-pointer"
            >
              <Globe className="w-3.5 h-3.5" />
              <span>OPEN APPLICATION</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}

          {/* 4. Common Workspace Button */}
          <button
            onClick={onOpenWorkspace}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full font-mono text-[11px] uppercase tracking-wider font-medium bg-white/[0.06] hover:bg-white/[0.12] text-slate-200 border border-white/[0.1] transition-all cursor-pointer"
          >
            <Folder className="w-3.5 h-3.5" />
            <span>WORKSPACE</span>
          </button>

          {/* Reset / New Build Button */}
          <button
            onClick={onReset}
            className="p-2 rounded-full font-mono text-xs bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border border-white/[0.08] transition-all cursor-pointer"
            title="Start New Build"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* 5. Conversational Follow-Up Command Bar */}
        {onSendMessage && (
          <form
            onSubmit={handleFollowUpSubmit}
            className={`w-full mt-4 pt-3 border-t border-white/[0.06] flex items-center gap-2 transition-all duration-700 ${
              showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
            }`}
          >
            <div className="relative flex-1">
              <input
                type="text"
                value={followUpText}
                onChange={(e) => setFollowUpText(e.target.value)}
                placeholder="Give follow-up instruction (e.g. 'Add 3D lighting', 'Fix login button')..."
                className="w-full bg-black/40 border border-white/[0.1] rounded-full px-4 py-2 font-mono text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-400/50 transition-all"
                disabled={isSubmitting}
              />
              <Sparkles className="absolute right-3 top-2.5 w-3.5 h-3.5 text-sky-400/50 pointer-events-none" />
            </div>
            <button
              type="submit"
              disabled={!followUpText.trim() || isSubmitting}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-sky-500 hover:bg-sky-400 text-black font-mono text-xs font-semibold uppercase tracking-wider transition-all disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            >
              <span>{isSubmitting ? 'SENDING...' : 'UPDATE'}</span>
              <Send className="w-3 h-3" />
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
