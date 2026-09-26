import React, { useState, useEffect } from 'react';
import {
  DbProject,
  DbBuild,
  DbAgentRun,
  DbActivity,
  DbRuntimeSession,
  DbVerificationGate,
  HistoryItem,
} from '../types/state';
import {
  Folder,
  History,
  Terminal,
  Activity,
  Users,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
  AlertTriangle,
  Clock,
  HardDrive,
  Calendar,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

type ViewMode = 'projects' | 'history' | 'project-detail' | 'build-detail';

export const ProjectsDrawerContent: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);
  const [previousView, setPreviousView] = useState<ViewMode>('projects');

  // Navigation helpers
  const openProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    setPreviousView(viewMode);
    setViewMode('project-detail');
  };

  const openBuild = (buildId: string, fromView: ViewMode = viewMode) => {
    setSelectedBuildId(buildId);
    setPreviousView(fromView);
    setViewMode('build-detail');
  };

  const goBack = () => {
    if (viewMode === 'build-detail') {
      setViewMode(previousView);
      setSelectedBuildId(null);
    } else if (viewMode === 'project-detail') {
      setViewMode('projects');
      setSelectedProjectId(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Toggle Bar (visible only in main views) */}
      {(viewMode === 'projects' || viewMode === 'history') && (
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-black/40 border border-white/[0.06]">
            <button
              onClick={() => setViewMode('projects')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-all ${
                viewMode === 'projects'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 font-semibold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Folder className="w-3.5 h-3.5" />
              Projects
            </button>
            <button
              onClick={() => setViewMode('history')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-all ${
                viewMode === 'history'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 font-semibold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <History className="w-3.5 h-3.5" />
              Build History
            </button>
          </div>
        </div>
      )}

      {/* View Routers */}
      {viewMode === 'projects' && <ProjectsListView onSelectProject={openProject} />}
      {viewMode === 'history' && <AllBuildsHistoryView onSelectBuild={(bId) => openBuild(bId, 'history')} />}
      {viewMode === 'project-detail' && selectedProjectId && (
        <ProjectDetailView
          projectId={selectedProjectId}
          onBack={goBack}
          onSelectBuild={(bId) => openBuild(bId, 'project-detail')}
        />
      )}
      {viewMode === 'build-detail' && selectedBuildId && (
        <BuildDetailView buildId={selectedBuildId} onBack={goBack} />
      )}
    </div>
  );
};

// =====================================================================
// 1. Projects List View (GET /api/projects)
// =====================================================================
const ProjectsListView: React.FC<{ onSelectProject: (id: string) => void }> = ({ onSelectProject }) => {
  const [projects, setProjects] = useState<DbProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = () => {
    setLoading(true);
    setError(null);
    fetch('/api/projects')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load projects');
        return res.json();
      })
      .then((data) => {
        setProjects(data.projects || []);
      })
      .catch((err) => {
        setError(err.message || 'Unable to load project history.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-slate-400 text-[10px] uppercase tracking-wider">
        <span>Persistent Projects ({projects.length})</span>
        <button
          onClick={fetchProjects}
          disabled={loading}
          className="p-1 hover:text-white transition-colors"
          title="Refresh Projects"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && (
        <div className="flex flex-col gap-2.5 py-6">
          {[1, 2].map((i) => (
            <div key={i} className="p-4 rounded-xl bg-slate-900/40 border border-white/5 animate-pulse flex flex-col gap-2">
              <div className="h-4 bg-white/10 rounded w-1/2" />
              <div className="h-3 bg-white/5 rounded w-3/4" />
              <div className="h-8 bg-white/5 rounded w-full mt-2" />
            </div>
          ))}
        </div>
      )}

      {error && !loading && (
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 flex flex-col items-center gap-2 text-center my-4">
          <AlertTriangle className="w-5 h-5 text-rose-400" />
          <span className="font-semibold text-xs">Unable to load project history.</span>
          <button
            onClick={fetchProjects}
            className="px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-[10px] uppercase font-bold tracking-wider transition-all mt-1"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && projects.length === 0 && (
        <div className="p-8 rounded-xl bg-slate-950/40 border border-white/5 flex flex-col items-center justify-center text-center gap-2.5 my-6">
          <Folder className="w-8 h-8 text-slate-600" />
          <span className="text-white font-semibold text-xs">No projects yet</span>
          <span className="text-slate-500 text-[10px] max-w-[240px]">
            Projects are automatically registered and preserved in SQLite when builds are initiated.
          </span>
        </div>
      )}

      {!loading && !error && projects.map((project) => (
        <div
          key={project.project_id}
          onClick={() => onSelectProject(project.project_id)}
          className="group p-4 rounded-xl bg-slate-900/60 border border-white/10 hover:border-sky-500/40 hover:bg-slate-900/90 transition-all cursor-pointer flex flex-col gap-2.5"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-white font-bold text-xs group-hover:text-sky-300 transition-colors block">
                {project.name || project.project_id}
              </span>
              {project.description ? (
                <span className="text-slate-400 text-[10px] line-clamp-2 mt-0.5">
                  {project.description}
                </span>
              ) : (
                <span className="text-slate-500 text-[10px] italic mt-0.5 block">No description provided</span>
              )}
            </div>
            <span
              className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border shrink-0 ${
                project.status === 'COMPLETED' || project.status === 'SUCCESS'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : project.status === 'BUILDING' || project.status === 'RUNNING'
                  ? 'bg-sky-500/20 text-sky-300 border-sky-500/30 animate-pulse'
                  : project.status === 'FAILED'
                  ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                  : 'bg-slate-800 text-slate-400 border-white/10'
              }`}
            >
              {project.status}
            </span>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 rounded bg-sky-950/40 text-sky-400 border border-sky-500/20 text-[9px] font-mono">
              {project.detected_stack || 'Fullstack'}
            </span>
            <span className="px-2 py-0.5 rounded bg-black/40 text-slate-400 border border-white/5 text-[9px] font-mono flex items-center gap-1">
              <History className="w-2.5 h-2.5 text-slate-500" />
              {project.build_count || 0} {project.build_count === 1 ? 'Build' : 'Builds'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[9px] font-mono text-slate-400 bg-black/40 p-2 rounded border border-white/5">
            <div>
              <span className="text-slate-500 block">CREATED</span>
              <span className="text-slate-300 truncate block">{formatDate(project.created_at)}</span>
            </div>
            <div>
              <span className="text-slate-500 block">UPDATED</span>
              <span className="text-slate-300 truncate block">{formatDate(project.updated_at)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// =====================================================================
// 2. All Builds History View (GET /api/history)
// =====================================================================
const AllBuildsHistoryView: React.FC<{ onSelectBuild: (id: string) => void }> = ({ onSelectBuild }) => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = () => {
    setLoading(true);
    setError(null);
    fetch('/api/history')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load history');
        return res.json();
      })
      .then((data) => {
        setHistory(data.history || []);
      })
      .catch((err) => {
        setError(err.message || 'Unable to load project history.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-slate-400 text-[10px] uppercase tracking-wider">
        <span>Historical Builds ({history.length})</span>
        <button
          onClick={fetchHistory}
          disabled={loading}
          className="p-1 hover:text-white transition-colors"
          title="Refresh History"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && (
        <div className="flex flex-col gap-2.5 py-6">
          {[1, 2].map((i) => (
            <div key={i} className="p-4 rounded-xl bg-slate-900/40 border border-white/5 animate-pulse flex flex-col gap-2">
              <div className="h-4 bg-white/10 rounded w-1/2" />
              <div className="h-3 bg-white/5 rounded w-3/4" />
            </div>
          ))}
        </div>
      )}

      {error && !loading && (
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 flex flex-col items-center gap-2 text-center my-4">
          <AlertTriangle className="w-5 h-5 text-rose-400" />
          <span className="font-semibold text-xs">Unable to load project history.</span>
          <button
            onClick={fetchHistory}
            className="px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-[10px] uppercase font-bold tracking-wider transition-all mt-1"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && history.length === 0 && (
        <div className="p-8 rounded-xl bg-slate-950/40 border border-white/5 flex flex-col items-center justify-center text-center gap-2.5 my-6">
          <History className="w-8 h-8 text-slate-600" />
          <span className="text-white font-semibold text-xs">No build history yet</span>
          <span className="text-slate-500 text-[10px] max-w-[240px]">
            Build executions and verification results will be logged here.
          </span>
        </div>
      )}

      {!loading && !error && history.map((item, idx) => (
        <div
          key={item.build_id || idx}
          onClick={() => onSelectBuild(item.build_id || item.project_id)}
          className="group p-4 rounded-xl bg-slate-900/60 border border-white/10 hover:border-sky-500/40 hover:bg-slate-900/90 transition-all cursor-pointer flex flex-col gap-2"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-[10px] text-sky-400 font-mono block uppercase">
                {item.project_name || item.project_id}
              </span>
              <span className="text-white font-semibold text-xs group-hover:text-sky-300 transition-colors line-clamp-2 mt-0.5">
                {item.goal || 'Autonomous Software Build'}
              </span>
            </div>
            <span
              className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border shrink-0 ${
                item.status === 'COMPLETED' || item.status === 'SUCCESS'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : item.status === 'RUNNING' || item.status === 'BUILDING'
                  ? 'bg-sky-500/20 text-sky-300 border-sky-500/30 animate-pulse'
                  : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
              }`}
            >
              {item.status}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 font-mono text-[9px] text-slate-400 bg-black/40 p-2 rounded border border-white/5 mt-1">
            <div>
              <span className="text-slate-500 block">DURATION</span>
              <span className="text-slate-300">{item.actual_duration_str || 'N/A'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">STACK</span>
              <span className="text-slate-300 truncate block">{item.tech_stack || 'Fullstack'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">DATE</span>
              <span className="text-slate-300 truncate block">{formatDate(item.timestamp)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// =====================================================================
// 3. Project Detail View (GET /api/projects/{project_id})
// =====================================================================
const ProjectDetailView: React.FC<{
  projectId: string;
  onBack: () => void;
  onSelectBuild: (buildId: string) => void;
}> = ({ projectId, onBack, onSelectBuild }) => {
  const [project, setProject] = useState<DbProject | null>(null);
  const [builds, setBuilds] = useState<DbBuild[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchDetail = () => {
    setLoading(true);
    setError(null);
    fetch(`/api/projects/${projectId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Project not found');
        return res.json();
      })
      .then((data) => {
        setProject(data.project);
        setBuilds(data.builds || []);
      })
      .catch((err) => {
        setError(err.message || 'Unable to load project details.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDetail();
  }, [projectId]);

  const copyWorkspacePath = () => {
    if (project?.workspace_path) {
      navigator.clipboard.writeText(project.workspace_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header with Back button */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 transition-colors font-mono cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" />
          Back to Projects
        </button>
        <button
          onClick={fetchDetail}
          disabled={loading}
          className="p-1 text-slate-400 hover:text-white transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && (
        <div className="p-8 text-center text-slate-400 text-xs">
          Loading project details...
        </div>
      )}

      {error && !loading && (
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 text-center my-4">
          <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-rose-400" />
          <span className="font-semibold text-xs block">{error}</span>
          <button
            onClick={fetchDetail}
            className="mt-3 px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-[10px] uppercase font-bold"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && project && (
        <div className="flex flex-col gap-4">
          {/* Project Summary Card */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-white/10 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="text-[10px] text-slate-500 font-mono block uppercase">PROJECT</span>
                <span className="text-white font-bold text-sm block mt-0.5">{project.name}</span>
              </div>
              <span
                className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border ${
                  project.status === 'COMPLETED' || project.status === 'SUCCESS'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    : 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                }`}
              >
                {project.status}
              </span>
            </div>

            {project.description && (
              <p className="text-slate-300 text-xs leading-relaxed">{project.description}</p>
            )}

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-black/40 p-2.5 rounded-lg border border-white/5">
              <div>
                <span className="text-slate-500 block uppercase">DETECTED STACK</span>
                <span className="text-sky-300 font-semibold">{project.detected_stack || 'Fullstack'}</span>
              </div>
              <div>
                <span className="text-slate-500 block uppercase">TOTAL BUILDS</span>
                <span className="text-slate-200">{builds.length}</span>
              </div>
              <div>
                <span className="text-slate-500 block uppercase">CREATED</span>
                <span className="text-slate-400">{formatDate(project.created_at)}</span>
              </div>
              <div>
                <span className="text-slate-500 block uppercase">UPDATED</span>
                <span className="text-slate-400">{formatDate(project.updated_at)}</span>
              </div>
            </div>

            {/* Workspace Path */}
            {project.workspace_path && (
              <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-white/5 text-[9px] font-mono">
                <div className="flex items-center gap-1.5 truncate text-slate-400">
                  <HardDrive className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span className="truncate">{project.workspace_path}</span>
                </div>
                <button
                  onClick={copyWorkspacePath}
                  className="p-1 hover:text-white text-slate-500 transition-colors shrink-0"
                  title="Copy Path"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            )}

            {/* Resume Project Action */}
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`/api/projects/${projectId}/resume`, { method: 'POST' });
                  if (res.ok) {
                    window.location.reload();
                  }
                } catch (e) {
                  alert('Failed to resume project');
                }
              }}
              className="w-full mt-1 py-2 px-3 rounded-lg font-mono text-[10px] font-semibold uppercase tracking-wider bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/40 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>RESUME PROJECT & ACTIVATE IN SPIDY</span>
            </button>
          </div>

          {/* Build History Section */}
          <div className="flex flex-col gap-2.5">
            <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
              Build History ({builds.length})
            </span>

            {builds.length === 0 && (
              <div className="p-6 rounded-xl bg-black/40 border border-white/5 text-center text-slate-500 text-xs">
                No builds recorded for this project yet.
              </div>
            )}

            {builds.map((b) => (
              <div
                key={b.build_id}
                onClick={() => onSelectBuild(b.build_id)}
                className="group p-3.5 rounded-xl bg-slate-900/60 border border-white/10 hover:border-sky-500/40 hover:bg-slate-900/90 transition-all cursor-pointer flex flex-col gap-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-white font-semibold text-xs group-hover:text-sky-300 transition-colors line-clamp-2">
                    {b.requirement || 'Build Task'}
                  </span>
                  <span
                    className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border shrink-0 ${
                      b.status === 'COMPLETED' || b.status === 'SUCCESS'
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        : b.status === 'RUNNING'
                        ? 'bg-sky-500/20 text-sky-300 border-sky-500/30 animate-pulse'
                        : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {b.status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 font-mono text-[9px] text-slate-400 bg-black/40 p-2 rounded border border-white/5">
                  <div>
                    <span className="text-slate-500 block">DURATION</span>
                    <span className="text-slate-300">{formatSeconds(b.duration)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">ESTIMATE</span>
                    <span className="text-slate-300">{b.estimated_duration || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">STARTED</span>
                    <span className="text-slate-300 truncate block">{formatDate(b.started_at)}</span>
                  </div>
                </div>

                {b.final_result && (
                  <div className="text-[10px] text-slate-400 truncate bg-slate-950/40 p-1.5 rounded border border-white/5">
                    <span className="text-slate-500 font-mono">Result: </span>
                    {b.final_result}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// =====================================================================
// 4. Build Detail View (GET /api/builds/{build_id})
// =====================================================================
const BuildDetailView: React.FC<{
  buildId: string;
  onBack: () => void;
}> = ({ buildId, onBack }) => {
  const [buildData, setBuildData] = useState<{
    build: DbBuild;
    activities: DbActivity[];
    agent_runs: DbAgentRun[];
    runtimes: DbRuntimeSession[];
    verification: DbVerificationGate[];
  } | null>(null);
  const [activeTab, setActiveTab] = useState<'BUILD' | 'AGENTS' | 'ACTIVITY' | 'RUNTIME' | 'VERIFICATION'>('BUILD');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBuild = () => {
    setLoading(true);
    setError(null);
    fetch(`/api/builds/${buildId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Build telemetry record not found');
        return res.json();
      })
      .then((data) => {
        setBuildData(data);
      })
      .catch((err) => {
        setError(err.message || 'Unable to load build details.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBuild();
  }, [buildId]);

  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 transition-colors font-mono cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <span className="font-mono text-[10px] text-slate-400 uppercase truncate max-w-[200px]">
          {buildId}
        </span>
        <button
          onClick={fetchBuild}
          disabled={loading}
          className="p-1 text-slate-400 hover:text-white transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && (
        <div className="p-8 text-center text-slate-400 text-xs">
          Loading build telemetry...
        </div>
      )}

      {error && !loading && (
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 text-center my-4">
          <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-rose-400" />
          <span className="font-semibold text-xs block">{error}</span>
          <button
            onClick={fetchBuild}
            className="mt-3 px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-[10px] uppercase font-bold"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && buildData && (
        <div className="flex flex-col gap-3">
          {/* Sub Navigation Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 border-b border-white/[0.06] text-[10px] font-mono uppercase tracking-wider">
            {(['BUILD', 'AGENTS', 'ACTIVITY', 'RUNTIME', 'VERIFICATION'] as const).map((tab) => {
              const count =
                tab === 'AGENTS'
                  ? buildData.agent_runs.length
                  : tab === 'ACTIVITY'
                  ? buildData.activities.length
                  : tab === 'RUNTIME'
                  ? buildData.runtimes.length
                  : tab === 'VERIFICATION'
                  ? buildData.verification.length
                  : null;
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-2.5 py-1 rounded transition-all whitespace-nowrap cursor-pointer ${
                    activeTab === tab
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 font-semibold'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tab} {count !== null && <span className="opacity-60">({count})</span>}
                </button>
              );
            })}
          </div>

          {/* TAB 1: BUILD OVERVIEW */}
          {activeTab === 'BUILD' && (
            <div className="flex flex-col gap-3">
              <div className="p-4 rounded-xl bg-slate-950/60 border border-white/10 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] text-slate-500 font-mono block uppercase">REQUIREMENT</span>
                    <span className="text-white font-bold text-xs mt-1 block leading-relaxed">
                      {buildData.build.requirement}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border shrink-0 ${
                      buildData.build.status === 'COMPLETED' || buildData.build.status === 'SUCCESS'
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        : buildData.build.status === 'RUNNING'
                        ? 'bg-sky-500/20 text-sky-300 border-sky-500/30 animate-pulse'
                        : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {buildData.build.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-black/40 p-2.5 rounded-lg border border-white/5">
                  <div>
                    <span className="text-slate-500 block uppercase">DURATION</span>
                    <span className="text-slate-200">{formatSeconds(buildData.build.duration)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase">ESTIMATE</span>
                    <span className="text-slate-200">{buildData.build.estimated_duration || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase">STARTED AT</span>
                    <span className="text-slate-400 truncate block">{formatDate(buildData.build.started_at)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase">COMPLETED AT</span>
                    <span className="text-slate-400 truncate block">
                      {buildData.build.completed_at ? formatDate(buildData.build.completed_at) : 'In progress'}
                    </span>
                  </div>
                </div>

                {buildData.build.final_result && (
                  <div className="bg-black/60 p-2.5 rounded-lg border border-white/5">
                    <span className="text-[9px] text-slate-500 uppercase font-mono block mb-1">Final Result</span>
                    <p className="text-slate-300 text-xs">{buildData.build.final_result}</p>
                  </div>
                )}

                {buildData.build.failure_reason && (
                  <div className="bg-rose-950/20 p-2.5 rounded-lg border border-rose-500/30">
                    <span className="text-[9px] text-rose-400 uppercase font-mono block mb-1 font-semibold">
                      Failure Reason
                    </span>
                    <p className="text-rose-300 text-xs">{buildData.build.failure_reason}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: AGENTS */}
          {activeTab === 'AGENTS' && (
            <div className="flex flex-col gap-2.5">
              {buildData.agent_runs.length === 0 && (
                <div className="p-6 rounded-xl bg-black/40 border border-white/5 text-center text-slate-500 text-xs">
                  No agent execution runs recorded for this build.
                </div>
              )}

              {buildData.agent_runs.map((agent) => (
                <div
                  key={agent.run_id}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-indigo-400" />
                      <span className="text-white font-bold text-xs">{agent.agent_name}</span>
                      {agent.task_id && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-black/40 text-slate-400 font-mono">
                          {agent.task_id}
                        </span>
                      )}
                    </div>
                    <span
                      className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border ${
                        agent.status === 'SUCCESS'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : agent.status === 'WORKING'
                          ? 'bg-sky-500/20 text-sky-300 border-sky-500/30 animate-pulse'
                          : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                      }`}
                    >
                      {agent.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 font-mono text-[9px] text-slate-400 bg-black/40 p-2 rounded border border-white/5">
                    <div>
                      <span className="text-slate-500 block">DURATION</span>
                      <span className="text-slate-200">{formatSeconds(agent.duration)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">STARTED</span>
                      <span className="text-slate-300 truncate block">{formatDate(agent.started_at)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">COMPLETED</span>
                      <span className="text-slate-300 truncate block">
                        {agent.completed_at ? formatDate(agent.completed_at) : 'Active'}
                      </span>
                    </div>
                  </div>

                  {agent.error_message && (
                    <div className="text-[10px] text-rose-300 bg-rose-950/20 p-2 rounded border border-rose-500/30">
                      {agent.error_message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* TAB 3: ACTIVITY TIMELINE */}
          {activeTab === 'ACTIVITY' && (
            <div className="flex flex-col gap-2">
              {buildData.activities.length === 0 && (
                <div className="p-6 rounded-xl bg-black/40 border border-white/5 text-center text-slate-500 text-xs">
                  No activity logs recorded.
                </div>
              )}

              <div className="relative pl-4 border-l border-white/10 flex flex-col gap-2.5 my-1">
                {buildData.activities.map((act) => (
                  <div key={act.activity_id} className="relative flex flex-col gap-1">
                    {/* Timeline bullet */}
                    <div className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-slate-900 border border-sky-400" />
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[9px] text-slate-500">{formatTime(act.timestamp)}</span>
                      {act.agent && (
                        <span className="font-mono text-[9px] px-1 rounded bg-white/5 text-sky-300">
                          {act.agent}
                        </span>
                      )}
                      <span className="font-mono text-[8px] uppercase tracking-wider text-slate-500 px-1 rounded bg-black/40">
                        {act.event_type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 font-mono leading-relaxed pl-0.5">{act.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: RUNTIME */}
          {activeTab === 'RUNTIME' && (
            <div className="flex flex-col gap-3">
              {buildData.runtimes.length === 0 && (
                <div className="p-6 rounded-xl bg-black/40 border border-white/5 text-center text-slate-500 text-xs">
                  No runtime sessions executed for this build.
                </div>
              )}

              {buildData.runtimes.map((rt) => (
                <div
                  key={rt.runtime_id}
                  className="p-4 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col gap-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-emerald-400" />
                        <span className="text-white font-bold text-xs">
                          {rt.framework || 'Application Runtime'}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
                        PID: {rt.pid || 'N/A'} • Port: {rt.port || 'N/A'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase border ${
                          rt.status === 'RUNNING'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : 'bg-slate-800 text-slate-400 border-white/10'
                        }`}
                      >
                        {rt.status}
                      </span>
                    </div>
                  </div>

                  {rt.url && (
                    <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-white/5 font-mono text-xs">
                      <span className="text-emerald-400 truncate">{rt.url}</span>
                      <a
                        href={rt.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[9px] uppercase font-bold tracking-wider transition-all"
                      >
                        Open <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-[9px] font-mono text-slate-400 bg-black/40 p-2 rounded border border-white/5">
                    <div>
                      <span className="text-slate-500 block">STARTED</span>
                      <span className="text-slate-300 truncate block">{formatDate(rt.started_at)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">STOPPED</span>
                      <span className="text-slate-300 truncate block">
                        {rt.stopped_at ? formatDate(rt.stopped_at) : 'Still Running'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 5: VERIFICATION */}
          {activeTab === 'VERIFICATION' && (
            <div className="flex flex-col gap-3">
              <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold block">
                6-Gate Convergence Matrix (Persisted Results)
              </span>

              {/* Standard 6-gate list mapped with persisted records */}
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                {['build', 'process', 'port', 'server', 'http', 'application'].map((gateName) => {
                  const match = buildData.verification.find(
                    (v) => v.gate_name.toLowerCase() === gateName.toLowerCase()
                  );
                  const isPassed = match?.status === 'PASSED';
                  const isFailed = match?.status === 'FAILED';

                  return (
                    <div
                      key={gateName}
                      className={`p-3 rounded-xl border flex flex-col gap-1.5 ${
                        isPassed
                          ? 'bg-emerald-950/20 border-emerald-500/30'
                          : isFailed
                          ? 'bg-rose-950/20 border-rose-500/30'
                          : 'bg-black/40 border-white/5'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <ShieldCheck
                            className={`w-4 h-4 ${
                              isPassed
                                ? 'text-emerald-400'
                                : isFailed
                                ? 'text-rose-400'
                                : 'text-slate-600'
                            }`}
                          />
                          <span className="capitalize font-bold text-white text-xs">{gateName} Gate</span>
                        </div>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                            isPassed
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : isFailed
                              ? 'bg-rose-500/20 text-rose-300'
                              : 'bg-white/5 text-slate-600'
                          }`}
                        >
                          {isPassed ? 'PASS' : isFailed ? 'FAIL' : 'WAIT'}
                        </span>
                      </div>

                      {match?.message && (
                        <p className="text-[10px] text-slate-300 font-mono leading-tight">{match.message}</p>
                      )}

                      {match?.timestamp && (
                        <span className="text-[8px] text-slate-500 font-mono">{formatTime(match.timestamp)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// =====================================================================
// Utility formatting helpers
// =====================================================================
function formatDate(isoStr?: string | null): string {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${mins}`;
  } catch {
    return isoStr;
  }
}

function formatTime(isoStr?: string | null): string {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    const secs = String(d.getSeconds()).padStart(2, '0');
    return `${hours}:${mins}:${secs}`;
  } catch {
    return isoStr;
  }
}

function formatSeconds(secs?: number | null): string {
  if (secs === null || secs === undefined || isNaN(secs)) return 'N/A';
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}m ${s}s`;
}
