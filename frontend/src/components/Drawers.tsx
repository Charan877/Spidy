import React, { useState, useEffect } from 'react';
import { ProjectStateSnapshot } from '../types/state';
import {
  X,
  Folder,
  File,
  FileCode,
  Terminal,
  Activity,
  Cpu,
  ShieldCheck,
  History,
  Users,
  RefreshCw,
  Play,
  Square,
  ExternalLink,
  Copy,
  Check,
  ChevronRight,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  Database,
} from 'lucide-react';
import { ProjectsDrawerContent } from './ProjectsDrawerContent';

interface DrawersProps {
  activeDrawer: string | null;
  onClose: () => void;
  state: ProjectStateSnapshot;
}

export const Drawers: React.FC<DrawersProps> = ({ activeDrawer, onClose, state }) => {
  if (!activeDrawer) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[500px] lg:w-[600px] z-50 glass-panel border-l border-white/[0.08] shadow-2xl flex flex-col pointer-events-auto animate-in slide-in-from-right duration-300">
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/[0.08] bg-slate-950/70">
        <div className="flex items-center gap-2">
          {activeDrawer === 'Workspace' && <Folder className="w-4 h-4 text-sky-400" />}
          {activeDrawer === 'Activity' && <Activity className="w-4 h-4 text-sky-400" />}
          {activeDrawer === 'Runtime' && <Terminal className="w-4 h-4 text-emerald-400" />}
          {activeDrawer === 'Agents' && <Users className="w-4 h-4 text-indigo-400" />}
          {activeDrawer === 'Diagnostics' && <Cpu className="w-4 h-4 text-amber-400" />}
          {activeDrawer === 'Projects' && <History className="w-4 h-4 text-slate-400" />}
          <span className="font-display font-bold text-xs tracking-wider text-white uppercase">
            {activeDrawer}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="flex-1 overflow-y-auto p-5 font-mono text-xs">
        {activeDrawer === 'Workspace' && <WorkspaceContent state={state} />}
        {activeDrawer === 'Activity' && <ActivityContent state={state} />}
        {activeDrawer === 'Runtime' && <RuntimeContent state={state} />}
        {activeDrawer === 'Agents' && <AgentsContent state={state} />}
        {activeDrawer === 'Diagnostics' && <DiagnosticsContent state={state} />}
        {activeDrawer === 'Projects' && <ProjectsDrawerContent />}
      </div>
    </div>
  );
};

// =====================================================================
// 1. Workspace Content: File Tree, File Inspector, Statistics
// =====================================================================
const WorkspaceContent: React.FC<{ state: ProjectStateSnapshot }> = ({ state }) => {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [filesMap, setFilesMap] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fetchFiles = () => {
    setIsLoading(true);
    fetch('/api/files')
      .then((r) => r.json())
      .then((data) => {
        if (data.files) {
          setFilesMap(data.files);
          const firstKey = Object.keys(data.files)[0];
          if (firstKey && !selectedFile) setSelectedFile(firstKey);
        }
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const fileKeys = Object.keys(filesMap);

  const getLanguageBadge = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'py':
        return { label: 'Python', color: 'text-amber-300 bg-amber-400/10 border-amber-400/20' };
      case 'ts':
      case 'tsx':
        return { label: 'TypeScript', color: 'text-sky-300 bg-sky-400/10 border-sky-400/20' };
      case 'js':
      case 'jsx':
        return { label: 'JavaScript', color: 'text-yellow-300 bg-yellow-400/10 border-yellow-400/20' };
      case 'html':
        return { label: 'HTML', color: 'text-orange-300 bg-orange-400/10 border-orange-400/20' };
      case 'css':
        return { label: 'CSS', color: 'text-cyan-300 bg-cyan-400/10 border-cyan-400/20' };
      case 'json':
        return { label: 'JSON', color: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20' };
      default:
        return { label: ext?.toUpperCase() || 'FILE', color: 'text-slate-300 bg-white/5 border-white/10' };
    }
  };

  const copyContent = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (fileKeys.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500 gap-3">
        <Folder className="w-8 h-8 text-slate-600" />
        <p className="text-xs">No files generated yet in workspace.</p>
        <span className="text-[10px] text-slate-600">Submit a build requirement to start generating code.</span>
      </div>
    );
  }

  const selectedContent = selectedFile ? filesMap[selectedFile] || '' : '';
  const lines = selectedContent.split('\n');
  const badge = selectedFile ? getLanguageBadge(selectedFile) : null;

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Workspace Header Stats */}
      <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/60 border border-white/5">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-[10px] text-slate-500 block uppercase">Files</span>
            <span className="font-bold text-white text-xs">{fileKeys.length}</span>
          </div>
          <div className="border-l border-white/10 pl-3">
            <span className="text-[10px] text-slate-500 block uppercase">Language</span>
            <span className="font-bold text-sky-400 text-xs">{state.detected_language || 'Auto'}</span>
          </div>
        </div>
        <button
          onClick={fetchFiles}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 text-[10px] border border-white/5 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* File Tree Buttons */}
      <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1 border border-white/5 rounded-lg bg-black/40">
        {fileKeys.map((f) => {
          const isSelected = selectedFile === f;
          const fBadge = getLanguageBadge(f);
          return (
            <button
              key={f}
              onClick={() => setSelectedFile(f)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] transition-all cursor-pointer ${
                isSelected
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-400/40 font-semibold'
                  : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
              }`}
            >
              <FileCode className="w-3 h-3 text-sky-400 shrink-0" />
              <span className="truncate max-w-[140px]">{f}</span>
            </button>
          );
        })}
      </div>

      {/* File Inspector View */}
      {selectedFile && (
        <div className="flex-1 flex flex-col bg-black/70 rounded-xl border border-white/10 overflow-hidden shadow-inner">
          {/* File Header Bar */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-slate-950/60">
            <div className="flex items-center gap-2 truncate">
              <span className="text-[11px] text-white font-semibold truncate">{selectedFile}</span>
              {badge && (
                <span className={`text-[9px] px-1.5 py-0.5 rounded border font-medium ${badge.color}`}>
                  {badge.label}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] text-slate-500">{lines.length} lines</span>
              <button
                onClick={() => copyContent(selectedContent)}
                className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300 text-[10px] border border-white/5 transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>

          {/* Code Viewer with Line Numbers */}
          <div className="flex-1 overflow-auto flex text-[11px] leading-relaxed p-2 font-mono">
            {/* Line numbers gutter */}
            <div className="select-none text-right pr-3 pl-1 text-slate-600 border-r border-white/5">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            {/* Code text */}
            <div className="pl-3 overflow-x-auto text-slate-300 whitespace-pre">
              {lines.map((line, i) => (
                <div key={i}>{line || ' '}</div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// =====================================================================
// 2. Activity Content: Timeline Stepper, Failure Diagnostics, Event Stream
// =====================================================================
const ActivityContent: React.FC<{ state: ProjectStateSnapshot }> = ({ state }) => {
  const [filter, setFilter] = useState<'all' | 'run' | 'bad' | 'ok'>('all');

  const pipelineStages = [
    'DISCOVER',
    'PLAN',
    'ARCHITECT',
    'BUILD',
    'RUN',
    'TEST',
    'REVIEW',
    'COMPLETE',
  ];

  const currentIdx = pipelineStages.indexOf(state.current_phase);

  const filteredFeed = state.activity_feed.filter((act) => {
    if (filter === 'all') return true;
    return act.level === filter;
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Visual Pipeline Progression Timeline */}
      <div className="p-3 rounded-xl bg-slate-950/60 border border-white/5">
        <span className="text-[10px] text-slate-500 uppercase tracking-widest block mb-2 font-semibold">
          Pipeline Timeline
        </span>
        <div className="flex items-center justify-between gap-1 overflow-x-auto py-1">
          {pipelineStages.map((stage, idx) => {
            const isCurrent = state.current_phase === stage;
            const isPassed = currentIdx > idx || state.project_success;
            return (
              <div key={stage} className="flex flex-col items-center gap-1 min-w-[50px]">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold transition-all ${
                    isCurrent
                      ? 'bg-sky-500 text-white ring-2 ring-sky-400/50'
                      : isPassed
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-white/5 text-slate-600 border border-white/5'
                  }`}
                >
                  {isPassed && !isCurrent ? '✓' : idx + 1}
                </div>
                <span
                  className={`text-[8px] font-mono uppercase tracking-wider text-center ${
                    isCurrent ? 'text-sky-300 font-bold' : isPassed ? 'text-emerald-400' : 'text-slate-600'
                  }`}
                >
                  {stage}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* High-Priority Failure Diagnostic Card */}
      {(state.failure_reason || state.failure_classification) && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 flex flex-col gap-2.5 shadow-xl">
          <div className="flex items-center justify-between border-b border-rose-500/20 pb-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span className="font-mono text-[11px] font-bold tracking-widest uppercase text-rose-400">
                RUNTIME FAILURE DIAGNOSTIC
              </span>
            </div>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-semibold border border-rose-500/30">
              {state.failure_classification || state.runtime_status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 font-mono text-[10px] py-1 bg-black/30 p-2 rounded">
            <div>
              <span className="text-slate-500 block">TARGET PORT</span>
              <span className="text-white font-semibold">{state.runtime_port || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">RECOVERY STATUS</span>
              <span className="text-amber-400 font-semibold">
                {state.recovery_attempts > 0 ? `Attempt ${state.recovery_attempts}` : 'Logged'}
              </span>
            </div>
          </div>

          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">ROOT CAUSE</span>
            <p className="text-rose-200 text-[11px] leading-relaxed font-mono bg-black/50 p-2.5 rounded border border-rose-500/20 mt-1 whitespace-pre-wrap">
              {state.failure_reason}
            </p>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
          Activity Events ({filteredFeed.length})
        </span>
        <div className="flex gap-1">
          {(['all', 'run', 'bad', 'ok'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setFilter(mode)}
              className={`px-2 py-0.5 rounded text-[10px] uppercase transition-colors cursor-pointer ${
                filter === mode
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-400/30 font-semibold'
                  : 'bg-white/5 text-slate-500 hover:text-white border border-white/5'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Activity Event Stream */}
      <div className="flex flex-col gap-2">
        {filteredFeed.slice().reverse().map((act, i) => (
          <div
            key={i}
            className={`flex items-start gap-2.5 p-2.5 rounded-lg border transition-all ${
              act.level === 'bad'
                ? 'bg-rose-950/20 border-rose-500/20 text-rose-300'
                : act.level === 'run'
                ? 'bg-sky-950/20 border-sky-500/20 text-sky-200'
                : act.level === 'dim'
                ? 'bg-black/20 border-white/5 text-slate-500'
                : 'bg-black/30 border-white/5 text-slate-300'
            }`}
          >
            <span className="text-[10px] font-mono text-slate-500 shrink-0 mt-0.5">{act.timestamp}</span>
            <span
              className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0 uppercase ${
                act.level === 'bad'
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  : act.level === 'run'
                  ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                  : act.level === 'dim'
                  ? 'bg-white/5 text-slate-500 border border-white/10'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              }`}
            >
              {act.level === 'bad' ? 'FAIL' : act.level === 'run' ? 'EXEC' : act.level === 'dim' ? 'INFO' : 'DONE'}
            </span>
            <span className="flex-1 text-[11px] leading-relaxed font-mono">
              {act.message}
            </span>
          </div>
        ))}
        {filteredFeed.length === 0 && (
          <div className="text-center py-10 text-slate-500">No events for this filter.</div>
        )}
      </div>
    </div>
  );
};

// =====================================================================
// 3. Runtime Content: Target Cards (Frontend & Backend), Controls, Logs
// =====================================================================
const RuntimeContent: React.FC<{ state: ProjectStateSnapshot }> = ({ state }) => {
  const [controlAction, setControlAction] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  const handleRuntimeControl = async (action: 'restart' | 'stop' | 'start') => {
    setControlAction(action);
    try {
      await fetch('/api/runtime/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
    } catch {}
    setTimeout(() => setControlAction(null), 1200);
  };

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedUrl(url);
    setTimeout(() => setCopiedUrl(null), 1500);
  };

  const targets = state.runtime_targets && state.runtime_targets.length > 0
    ? state.runtime_targets
    : state.runtime_url
    ? [
        {
          type: state.runtime_type === 'api' ? 'api' : 'web',
          name: state.runtime_type === 'api' ? 'API Service' : 'Web Application',
          url: state.runtime_url,
          port: state.runtime_port || 0,
          pid: state.runtime_pid,
          status: state.runtime_status,
          framework: state.project_type,
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      {/* Interactive Runtime Controls */}
      <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-white/5">
        <div>
          <span className="text-[10px] text-slate-500 block uppercase">Lifecycle Status</span>
          <span className="font-bold text-white text-xs flex items-center gap-1.5 mt-0.5">
            <span
              className={`w-2 h-2 rounded-full ${
                state.runtime_status === 'RUNNING'
                  ? 'bg-emerald-400'
                  : state.runtime_status.includes('FAIL')
                  ? 'bg-rose-400'
                  : 'bg-amber-400 animate-pulse'
              }`}
            />
            {state.runtime_status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleRuntimeControl('restart')}
            disabled={controlAction !== null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 text-[10px] font-semibold transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3 h-3 ${controlAction === 'restart' ? 'animate-spin' : ''}`} />
            <span>Restart</span>
          </button>
          <button
            onClick={() => handleRuntimeControl('stop')}
            disabled={controlAction !== null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-semibold transition-colors cursor-pointer"
          >
            <Square className="w-3 h-3" />
            <span>Stop</span>
          </button>
        </div>
      </div>

      {/* Real Multi-Runtime Application Target Cards */}
      <div className="flex flex-col gap-2.5">
        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
          Active Runtime Endpoints ({targets.length})
        </span>

        {targets.map((tgt, idx) => (
          <div
            key={idx}
            className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col gap-2 shadow-md hover:border-white/20 transition-all"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase border ${
                    tgt.type === 'web'
                      ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                      : tgt.type === 'api'
                      ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  }`}
                >
                  {tgt.type.toUpperCase()}
                </span>
                <span className="font-semibold text-white text-xs">{tgt.name}</span>
              </div>
              <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                {tgt.status}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 font-mono text-[10px] bg-black/40 p-2 rounded border border-white/5">
              <div>
                <span className="text-slate-500 block">PORT</span>
                <span className="text-sky-300 font-bold">{tgt.port || 'N/A'}</span>
              </div>
              <div>
                <span className="text-slate-500 block">PID</span>
                <span className="text-slate-300">{tgt.pid || 'N/A'}</span>
              </div>
              <div>
                <span className="text-slate-500 block">STACK</span>
                <span className="text-slate-300 truncate">{tgt.framework || state.project_type}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-slate-400 text-[11px] truncate max-w-[300px]">{tgt.url}</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => copyUrl(tgt.url)}
                  className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300 text-[10px] border border-white/5 transition-colors cursor-pointer"
                >
                  {copiedUrl === tgt.url ? 'Copied' : 'Copy'}
                </button>
                <a
                  href={tgt.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2.5 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[10px] font-semibold transition-colors"
                >
                  <span>Open</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        ))}

        {targets.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-xs">
            No runtime process currently bound. Launch a build to initialize runtimes.
          </div>
        )}
      </div>

      {/* Streaming Terminal Output */}
      <div className="bg-black/90 rounded-xl p-3.5 border border-white/10 flex flex-col gap-2">
        <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
          <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-sky-400" />
            STDOUT / STDERR TERMINAL
          </span>
          <span className="text-[9px] text-slate-500">Live stream</span>
        </div>
        <pre className="text-[11px] text-slate-300 overflow-auto max-h-80 leading-relaxed whitespace-pre-wrap font-mono">
          {state.runtime_logs || 'Awaiting application process execution logs...'}
        </pre>
      </div>
    </div>
  );
};

// =====================================================================
// 4. Agents Inspector Content: Dedicated View for 7 Pipeline Agents
// =====================================================================
const AgentsContent: React.FC<{ state: ProjectStateSnapshot }> = ({ state }) => {
  const agents = [
    {
      id: 'planner',
      name: 'Planner & Architect Agent',
      role: 'Requirements Analysis & Architecture Contracts',
      provider: 'Anthropic Claude / Gemini Pro',
      task: 'Deconstructing user goals into tasks, system schemas, and tech stack.',
    },
    {
      id: 'developer',
      name: 'Developer Agent',
      role: 'Code Generation & Dependency Synthesis',
      provider: 'NVIDIA DeepSeek / Claude Sonnet',
      task: 'Synthesizing application source code, components, and package manifests.',
    },
    {
      id: 'runner',
      name: 'Tester & Runner Agent',
      role: 'Process Supervision & Port Discovery',
      provider: 'SPIDY Local Runtime Engine',
      task: 'Supervising isolated processes, binding ports, and running tests.',
    },
    {
      id: 'debugger',
      name: 'Debugger & Self-Healing Agent',
      role: 'Runtime Anomaly Recovery & Syntax Repair',
      provider: 'Self-Correction Pipeline',
      task: 'Diagnosing runtime stack traces, missing entry points, and repairing code.',
    },
    {
      id: 'reviewer',
      name: 'Reviewer Agent',
      role: 'Code Quality & Security Verification',
      provider: 'LLM Verification Gate',
      task: 'Evaluating generated code against architectural contracts and best practices.',
    },
    {
      id: 'documenter',
      name: 'Documentation Agent',
      role: 'API Specs, Swagger Docs & Guides',
      provider: 'Automated Documenter',
      task: 'Extracting endpoint signatures and writing comprehensive project documentation.',
    },
    {
      id: 'orchestrator',
      name: 'Orchestrator Core',
      role: 'State Machine & Gate Controller',
      provider: 'SPIDY Autonomous Orchestrator',
      task: 'Guiding multi-agent execution with strict prerequisite dependency gates.',
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
        Autonomous Engineering Constellation ({agents.length} Agents)
      </span>

      {agents.map((agent) => {
        const isActive =
          state.active_agent.toLowerCase().includes(agent.id) ||
          state.active_agent.toLowerCase().includes(agent.name.toLowerCase().split(' ')[0]);

        return (
          <div
            key={agent.id}
            className={`p-3.5 rounded-xl border transition-all ${
              isActive
                ? 'bg-sky-950/30 border-sky-400/40 shadow-lg shadow-sky-500/5'
                : 'bg-slate-900/50 border-white/5'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isActive ? 'bg-sky-400 animate-ping' : 'bg-slate-600'
                  }`}
                />
                <span className="font-semibold text-white text-xs">{agent.name}</span>
              </div>
              <span
                className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border ${
                  isActive
                    ? 'bg-sky-500/20 text-sky-300 border-sky-400/30'
                    : 'bg-white/5 text-slate-500 border-white/5'
                }`}
              >
                {isActive ? 'ACTIVE' : 'IDLE'}
              </span>
            </div>

            <div className="text-[10px] text-slate-400 mt-1">{agent.role}</div>

            <div className="mt-2.5 p-2 rounded bg-black/40 border border-white/5 text-[10px] leading-relaxed">
              <span className="text-slate-500 block uppercase text-[8px] font-semibold">Current Responsibility</span>
              <p className="text-slate-300 mt-0.5">
                {isActive ? state.current_task_description || agent.task : agent.task}
              </p>
            </div>

            <div className="flex items-center justify-between text-[9px] text-slate-500 mt-2">
              <span>Provider: <span className="text-slate-300">{agent.provider}</span></span>
              {isActive && state.current_file_target && (
                <span className="text-sky-300 font-semibold truncate max-w-[180px]">
                  Target: {state.current_file_target}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// =====================================================================
// 5. Diagnostics Content: 6 Gates, Model Router Telemetry, Self-Healing
// =====================================================================
const DiagnosticsContent: React.FC<{ state: ProjectStateSnapshot }> = ({ state }) => {
  const [diagData, setDiagData] = useState<any>(null);
  const [dbCopied, setDbCopied] = useState(false);

  useEffect(() => {
    fetch('/api/diagnostics')
      .then((r) => r.json())
      .then((data) => setDiagData(data))
      .catch(() => {});
  }, []);

  return (
    <div className="flex flex-col gap-4">
      {/* 6 Verification Integrity Gates */}
      <div className="bg-slate-950/60 rounded-xl p-4 border border-white/10">
        <span className="text-[10px] text-slate-400 uppercase tracking-widest block mb-3 font-semibold">
          6-Gate Verification Integrity
        </span>
        <div className="grid grid-cols-2 gap-2.5 text-xs">
          {Object.entries(state.verification_gates).map(([gate, passed]) => (
            <div
              key={gate}
              className={`flex items-center justify-between p-2.5 rounded-lg border ${
                passed
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                  : 'bg-black/40 border-white/5 text-slate-500'
              }`}
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className={`w-4 h-4 ${passed ? 'text-emerald-400' : 'text-slate-600'}`} />
                <span className="capitalize font-semibold">{gate} Gate</span>
              </div>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                  passed ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/5 text-slate-600'
                }`}
              >
                {passed ? 'PASS' : 'WAIT'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Persistent SQLite Database Telemetry */}
      {diagData?.database && (
        <div className="bg-slate-950/60 rounded-xl p-4 border border-white/10 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-sky-400" />
              <span className="text-[10px] text-slate-300 uppercase tracking-widest font-semibold">
                SQLite Persistence Engine
              </span>
            </div>
            <span
              className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border ${
                diagData.database.status === 'HEALTHY'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
              }`}
            >
              {diagData.database.status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-black/40 p-2.5 rounded-lg border border-white/5">
            <div>
              <span className="text-slate-500 block uppercase">SCHEMA VERSION</span>
              <span className="text-sky-300 font-bold">v{diagData.database.schema_version}</span>
            </div>
            <div>
              <span className="text-slate-500 block uppercase">STORAGE MODE</span>
              <span className="text-slate-300">WAL / Persistent</span>
            </div>
          </div>

          {diagData.database.db_path && (
            <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-white/5 text-[9px] font-mono">
              <span className="text-slate-400 truncate">{diagData.database.db_path}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(diagData.database.db_path);
                  setDbCopied(true);
                  setTimeout(() => setDbCopied(false), 2000);
                }}
                className="p-1 hover:text-white text-slate-500 transition-colors shrink-0"
                title="Copy Database Path"
              >
                {dbCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          )}

          {diagData.database.counts && (
            <div className="flex flex-col gap-1.5 mt-1">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider font-mono">
                Persistent Table Records
              </span>
              <div className="grid grid-cols-3 gap-2 text-[10px] font-mono">
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">PROJECTS</span>
                  <span className="text-white font-bold">{diagData.database.counts.projects ?? 0}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">BUILDS</span>
                  <span className="text-white font-bold">{diagData.database.counts.builds ?? 0}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">AGENT RUNS</span>
                  <span className="text-white font-bold">{diagData.database.counts.agent_runs ?? 0}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">ACTIVITIES</span>
                  <span className="text-white font-bold">{diagData.database.counts.activities ?? 0}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">RUNTIMES</span>
                  <span className="text-white font-bold">{diagData.database.counts.runtime_sessions ?? 0}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-slate-500 block text-[8px] uppercase">VERIFICATION</span>
                  <span className="text-white font-bold">{diagData.database.counts.verification ?? 0}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Model Router Telemetry */}
      {diagData?.model_router && (
        <div className="bg-slate-950/60 rounded-xl p-4 border border-white/10 flex flex-col gap-2.5">
          <span className="text-[10px] text-slate-400 uppercase tracking-widest block font-semibold">
            Centralized Model Router & Telemetry
          </span>
          <div className="flex flex-col gap-2">
            {diagData.model_router.map((m: any, idx: number) => (
              <div
                key={idx}
                className="bg-black/60 p-2.5 rounded-lg border border-white/5 flex items-center justify-between text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white uppercase">{m.provider}</span>
                    <span className="text-[10px] text-sky-300 font-mono">({m.role})</span>
                  </div>
                  <div className="text-[10px] text-slate-400 truncate max-w-[240px] mt-0.5">{m.model}</div>
                </div>
                <div className="text-right">
                  <span
                    className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase ${
                      m.status === 'READY'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {m.status}
                  </span>
                  <div className="text-[9px] text-slate-500 mt-1 font-mono">
                    {m.latency_ms ? `${m.latency_ms.toFixed(0)}ms` : '0ms'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Smart Recovery Diagnostics */}
      <div className="bg-slate-950/60 rounded-xl p-4 border border-white/10 flex flex-col gap-2">
        <span className="text-[10px] text-slate-400 uppercase tracking-widest block font-semibold">
          Autonomous Self-Healing Statistics
        </span>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
            <span className="text-[9px] text-slate-500 block uppercase">Auto Repairs</span>
            <span className="text-white font-bold text-sm">{state.recovery_attempts}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
            <span className="text-[9px] text-slate-500 block uppercase">Convergence Status</span>
            <span className="text-emerald-400 font-bold text-sm">
              {state.project_success ? 'VERIFIED' : 'PENDING'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
