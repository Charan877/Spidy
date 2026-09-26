import React, { useState, useEffect, useRef } from 'react';
import { World3D } from './three/World3D';
import { Navigation } from './components/Navigation';
import { ScrollStoryOverlay } from './components/ScrollStoryOverlay';
import { ActiveBuildHUD } from './components/ActiveBuildHUD';
import { SuccessView } from './components/SuccessView';
import { FailureView } from './components/FailureView';
import { Drawers } from './components/Drawers';
import { ProjectStateSnapshot } from './types/state';

const INITIAL_STATE: ProjectStateSnapshot = {
  project_name: 'SPIDY Project',
  goal: '',
  detected_language: 'Python',
  selected_language: 'Auto Detect',
  effective_language: 'Python',
  architecture_summary: '',
  tech_stack: [],
  clarifying_questions: [],
  clarification_answers: {},
  user_approved: false,
  current_phase: 'DISCOVER',
  project_state: 'IDLE',
  active_agent: 'Orchestrator',
  active_agent_status: 'READY',
  current_task_description: 'Awaiting requirement prompt...',
  current_file_target: '',
  tasks: [],
  tasks_completed: 0,
  tasks_total: 0,
  progress_percent: 0,
  activity_feed: [],
  errors: [],
  is_running: false,
  project_generation_status: 'NOT_STARTED',
  is_project_generated: false,
  recovery_attempts: 0,
  project_type: 'General Software Project',
  is_web_project: false,
  runtime_status: 'NOT_STARTED',
  runtime_command: '',
  runtime_pid: null,
  runtime_port: null,
  runtime_url: null,
  runtime_logs: '',
  is_app_verified: false,
  verification_gates: {
    build: false,
    process: false,
    port: false,
    server: false,
    http: false,
    application: false,
  },
  project_success: false,
  failure_reason: null,
  failure_classification: null,
  elapsed_seconds: 0,
  formatted_elapsed: '00:00',
  estimated_duration_str: '~8–12 MIN',
  estimated_remaining_str: '~8–12 MIN',
  estimated_complexity: 'HIGH',
  estimated_confidence: 'MEDIUM',
  actual_duration_str: null,
  files_count: 0,
  files_list: [],
};

export const App: React.FC = () => {
  const [state, setState] = useState<ProjectStateSnapshot>(() => {
    if (typeof window === 'undefined') return INITIAL_STATE;
    const params = new URLSearchParams(window.location.search);
    const qPhase = params.get('phase');
    if (qPhase) {
      return {
        ...INITIAL_STATE,
        current_phase: qPhase,
        project_state: qPhase === 'COMPLETE' ? 'FINISHED' : (qPhase === 'DISCOVER' ? 'IDLE' : 'RUNNING'),
        is_running: !['DISCOVER', 'COMPLETE', 'FAILED'].includes(qPhase),
        project_success: qPhase === 'COMPLETE',
        is_app_verified: qPhase === 'COMPLETE',
        verification_gates: qPhase === 'COMPLETE' ? {
          build: true,
          process: true,
          port: true,
          server: true,
          http: true,
          application: true,
        } : INITIAL_STATE.verification_gates,
        runtime_status: qPhase === 'COMPLETE' ? 'HEALTHY' : (qPhase === 'BUILD' ? 'STARTING' : INITIAL_STATE.runtime_status),
        runtime_port: qPhase === 'COMPLETE' ? 9000 : INITIAL_STATE.runtime_port,
        runtime_url: qPhase === 'COMPLETE' ? 'http://localhost:9000' : INITIAL_STATE.runtime_url,
      };
    }
    return INITIAL_STATE;
  });

  const [activeDrawer, setActiveDrawer] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Synchronously initialize scrollProgress from ?scroll= if provided
  const [scrollProgress, setScrollProgress] = useState<number>(() => {
    if (typeof window === 'undefined') return 0;
    const params = new URLSearchParams(window.location.search);
    const qScroll = params.get('scroll');
    return qScroll !== null ? Math.max(0, Math.min(1, parseFloat(qScroll))) : 0;
  });

  const wsRef = useRef<WebSocket | null>(null);

  // Calculate smooth scroll progress (0.0 to 1.0) when not locked by ?scroll=
  useEffect(() => {
    const hasQueryScroll = new URLSearchParams(window.location.search).has('scroll');
    if (hasQueryScroll) return; // Do not overwrite query-locked scroll

    const handleScroll = () => {
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight > 0) {
        const p = Math.max(0, Math.min(1, window.scrollY / docHeight));
        setScrollProgress(p);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Connect to backend WebSocket
  useEffect(() => {
    const hasQueryPhase = new URLSearchParams(window.location.search).has('phase');
    let reconnectTimer: any;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: 'GET_STATE' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'STATE_UPDATE' && data.state) {
            if (!hasQueryPhase) {
              setState(data.state);
              if (!data.state.is_running) {
                setIsLoading(false);
              }
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connectWebSocket, 2000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    // Polling fallback
    const pollInterval = setInterval(() => {
      if (hasQueryPhase) return;
      fetch('/api/state')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.project_state) {
            setState(data);
            if (!data.is_running) {
              setIsLoading(false);
            }
          }
        })
        .catch(() => {});
    }, 2500);

    return () => {
      clearTimeout(reconnectTimer);
      clearInterval(pollInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleStartBuild = async (goal: string, language: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, language }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.error || 'Failed to start build');
        setIsLoading(false);
      }
    } catch (e) {
      alert('Network error connecting to SPIDY server.');
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (message: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, project_id: state.project_id }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.error || 'Failed to send instruction');
        setIsLoading(false);
      }
    } catch (e) {
      alert('Network error connecting to SPIDY server.');
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      await fetch('/api/stop', { method: 'POST' });
    } catch {}
  };

  const handleReset = async () => {
    try {
      await fetch('/api/stop', { method: 'POST' });
      setActiveDrawer(null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {}
  };

  const handleScrollToSection = (sectionIndex: number) => {
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const targetY = (sectionIndex / 7) * docHeight;
    window.scrollTo({ top: targetY, behavior: 'smooth' });
  };

  // State conditions: Authoritative Completion Gate
  const isInterrupted =
    ['FAILED', 'BLOCKED'].includes(state.current_phase) ||
    ['FAILED', 'BLOCKED'].includes(state.project_state) ||
    ['FAILED', 'BLOCKED'].includes(state.runtime_status) ||
    Boolean(state.has_failed_required_tasks && state.current_phase !== 'BUILD' && state.current_phase !== 'DISCOVER');

  const isSuccess =
    !isInterrupted &&
    state.current_phase === 'COMPLETE' &&
    state.project_state === 'SUCCESS' &&
    state.project_success &&
    !state.has_failed_required_tasks &&
    (!state.is_web_project || state.is_app_verified);

  const isActiveBuild =
    state.is_running &&
    [
      'PLAN',
      'ARCHITECT',
      'BUILD',
      'RUN',
      'TEST',
      'DEBUG',
      'REVIEW',
      'DOCUMENT',
    ].includes(state.current_phase) &&
    !isSuccess &&
    !isInterrupted;

  return (
    <div className="relative min-h-screen bg-[#040711] text-white selection:bg-cyan-500/30">
      {/* 1. FIXED BACKGROUND 3D COMPUTATIONAL ENVIRONMENT */}
      <World3D
        state={state}
        scrollProgress={scrollProgress}
        onSelectAgent={() => setActiveDrawer('Activity')}
      />

      {/* 2. MINIMAL FLOATING TOP NAVIGATION */}
      <Navigation
        state={state}
        activeDrawer={activeDrawer}
        onToggleDrawer={setActiveDrawer}
      />

      {/* 3. SCROLL-DRIVEN 7-SECTION STORYTELLING OVERLAY */}
      <ScrollStoryOverlay
        state={state}
        scrollProgress={scrollProgress}
        onStartBuild={handleStartBuild}
        isLoading={isLoading}
        onScrollToSection={handleScrollToSection}
        onOpenWorkspace={() => setActiveDrawer('Workspace')}
      />

      {/* 4. ACTIVE BUILD HUD (Floats above scene when build in progress) */}
      {isActiveBuild && <ActiveBuildHUD state={state} onStop={handleStop} />}

      {/* 5. SUCCESS CELEBRATION MODAL (If verified and at completion) */}
      {isSuccess && (
        <SuccessView
          state={state}
          onOpenWorkspace={() => setActiveDrawer('Workspace')}
          onReset={handleReset}
          onSendMessage={handleSendMessage}
        />
      )}

      {/* 6. FAILURE / RECOVERY OVERLAY */}
      {isInterrupted && (
        <FailureView
          state={state}
          onOpenDiagnostics={() => setActiveDrawer('Diagnostics')}
          onReset={handleReset}
        />
      )}

      {/* 7. SLIDE-OUT PROGRESSIVE DISCLOSURE DRAWERS */}
      <Drawers
        activeDrawer={activeDrawer}
        onClose={() => setActiveDrawer(null)}
        state={state}
      />
    </div>
  );
};
export default App;
