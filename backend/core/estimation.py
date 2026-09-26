"""Build duration estimation engine for NOVA Code Lab.

Produces realistic non-deterministic duration ranges, complexity ratings, and confidence
scores based on task graph topology, agent count, dependencies, package installation,
and empirical task execution metrics.
"""

from dataclasses import dataclass
import math
import time
from typing import Dict, List, Optional


@dataclass
class EstimationResult:
    min_minutes: int
    max_minutes: int
    range_str: str              # e.g. "~8–12 MIN"
    complexity: str             # "LOW", "MEDIUM", "HIGH"
    confidence: str             # "HIGH", "MEDIUM", "LOW"
    task_count: int
    agent_count: int
    factors: Dict[str, float]


class BuildEstimator:
    """Calculates dynamic pre-build and in-flight time estimations."""

    # Base seconds required per phase/task category
    BASE_SECONDS_PER_CODE_GEN = 18.0
    BASE_SECONDS_PER_INSTALL = 45.0
    BASE_SECONDS_PER_STARTUP = 12.0
    BASE_SECONDS_PER_VERIFY = 15.0
    BASE_SECONDS_PER_DEBUG_RECOVERY = 30.0

    @classmethod
    def estimate_pre_build(
        cls,
        goal: str,
        tech_stack: str,
        tasks: Optional[List] = None,
        agent_names: Optional[List[str]] = None,
    ) -> EstimationResult:
        task_count = len(tasks) if tasks else 0
        agents = set(agent_names or ["Architect", "Developer", "Debugger", "Reviewer", "Tester"])
        agent_count = len(agents)

        # 1. Analyze text heuristics for scope & complexity
        goal_lower = goal.lower()
        is_complex = any(k in goal_lower for k in [
            "3d", "three.js", "webgl", "fullstack", "microservice",
            "database", "realtime", "websocket", "audio", "shader"
        ])
        is_medium = any(k in goal_lower for k in [
            "react", "vite", "vue", "next.js", "fastapi", "express",
            "rest api", "tailwind", "portfolio", "interactive"
        ])
        requires_npm_install = any(k in goal_lower or k in tech_stack.lower() for k in [
            "react", "vite", "next", "vue", "three", "node", "typescript"
        ])

        if is_complex or task_count >= 16:
            complexity = "HIGH"
            base_mult = 1.35
            recovery_buffer = 60.0
        elif is_medium or task_count >= 8:
            complexity = "MEDIUM"
            base_mult = 1.15
            recovery_buffer = 30.0
        else:
            complexity = "LOW"
            base_mult = 0.95
            recovery_buffer = 15.0

        # If tasks have not been generated yet, extrapolate from complexity
        effective_tasks = task_count if task_count > 0 else (22 if complexity == "HIGH" else 12 if complexity == "MEDIUM" else 6)
        
        # 2. Dependency count analysis
        dep_count = 0
        if tasks:
            for t in tasks:
                deps = getattr(t, "dependencies", []) or []
                dep_count += len(deps)
        else:
            dep_count = int(effective_tasks * 0.8)

        # 3. Factor calculations (in seconds)
        sec_per_task = cls.BASE_SECONDS_PER_CODE_GEN * base_mult
        try:
            from backend.core.llm.model_router import get_model_router
            router = get_model_router()
            avg_latencies = [m.avg_latency_ms for m in router.metrics.values() if m.request_count > 0]
            total_retries = sum(m.retry_count for m in router.metrics.values())
            if avg_latencies:
                avg_model_sec = (sum(avg_latencies) / len(avg_latencies)) / 1000.0
                # Scale expected code generation seconds based on empirical model latency
                sec_per_task = max(10.0, avg_model_sec * 2.5) * base_mult
            if total_retries > 0:
                recovery_buffer += min(45.0, total_retries * 5.0)
        except Exception:
            pass

        code_gen_sec = effective_tasks * sec_per_task
        install_sec = cls.BASE_SECONDS_PER_INSTALL if requires_npm_install else 5.0
        startup_sec = cls.BASE_SECONDS_PER_STARTUP
        verify_sec = cls.BASE_SECONDS_PER_VERIFY * (1.5 if is_complex else 1.0)
        dep_overhead = dep_count * 2.5
        
        total_expected_sec = code_gen_sec + install_sec + startup_sec + verify_sec + dep_overhead + recovery_buffer

        # 4. Realistic duration range
        min_sec = total_expected_sec * 0.82
        max_sec = total_expected_sec * 1.25

        min_min = max(1, int(math.floor(min_sec / 60.0)))
        max_min = max(min_min + 1, int(math.ceil(max_sec / 60.0)))

        # Confidence based on whether tasks and dependencies are already resolved
        if tasks and len(tasks) > 0:
            confidence = "HIGH" if len(tasks) > 10 else "MEDIUM"
        else:
            confidence = "MEDIUM" if is_complex else "LOW"

        range_str = f"~{min_min}-{max_min} MIN"

        return EstimationResult(
            min_minutes=min_min,
            max_minutes=max_min,
            range_str=range_str,
            complexity=complexity,
            confidence=confidence,
            task_count=effective_tasks,
            agent_count=agent_count,
            factors={
                "code_gen_sec": code_gen_sec,
                "install_sec": install_sec,
                "startup_sec": startup_sec,
                "verify_sec": verify_sec,
                "dep_overhead": dep_overhead,
                "recovery_buffer": recovery_buffer,
                "total_sec": total_expected_sec,
            },
        )

    @classmethod
    def calculate_remaining_estimate(
        cls,
        pre_build: EstimationResult,
        elapsed_seconds: float,
        completed_tasks: int,
        total_tasks: int,
    ) -> str:
        """Dynamically compute realistic remaining time based on actual progress."""
        if total_tasks <= 0:
            return pre_build.range_str

        progress_ratio = max(0.0, min(1.0, completed_tasks / total_tasks))
        if progress_ratio >= 1.0:
            return "FINALIZING..."

        total_sec = pre_build.factors.get("total_sec", pre_build.max_minutes * 60.0)

        # If we have some completed tasks, blend empirical rate with prior estimate
        if completed_tasks > 0 and elapsed_seconds > 10.0:
            empirical_rate_per_task = elapsed_seconds / completed_tasks
            remaining_tasks = total_tasks - completed_tasks
            projected_remaining_sec = empirical_rate_per_task * remaining_tasks + 30.0  # startup & verify buffer
            blended_remaining_sec = (projected_remaining_sec * 0.7) + (max(0, total_sec - elapsed_seconds) * 0.3)
        else:
            blended_remaining_sec = max(30.0, total_sec - elapsed_seconds)

        min_rem_min = max(1, int(math.floor((blended_remaining_sec * 0.8) / 60.0)))
        max_rem_min = max(min_rem_min + 1, int(math.ceil((blended_remaining_sec * 1.25) / 60.0)))

        return f"~{min_rem_min}–{max_rem_min} MIN"

    @staticmethod
    def format_elapsed(seconds: float) -> str:
        secs = max(0, int(seconds))
        mins = secs // 60
        rem_sec = secs % 60
        return f"{mins:02d}:{rem_sec:02d}"

    @staticmethod
    def format_actual(seconds: float) -> str:
        secs = max(0, int(seconds))
        mins = secs // 60
        rem_sec = secs % 60
        if mins == 0:
            return f"{rem_sec}s"
        return f"{mins}m {rem_sec:02d}s"
