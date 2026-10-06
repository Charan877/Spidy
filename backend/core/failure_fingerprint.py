"""Failure Fingerprinting and Autonomous Loop Detection for SPIDY.

Provides deterministic fingerprinting of task, runtime, and verification failures
to prevent infinite retry loops and detect when repeated attempts cannot alter the outcome.
"""

from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Set


def normalize_error_message(msg: str) -> str:
    """Normalize error messages to extract a stable structural signature.
    
    Strips transient data such as memory addresses, PIDs, temporary paths,
    exact line numbers, timestamps, and randomized tokens.
    """
    if not msg:
        return ""
    text = str(msg).strip()

    # Normalize memory addresses (e.g. at 0x7f8b2c)
    text = re.sub(r"0x[0-9a-fA-F]+", "HEXADDR", text)

    # Normalize Windows/Unix file paths to base filenames
    text = re.sub(r'[A-Za-z]:\\[^:\s\n]+\\([a-zA-Z0-9_.-]+)', r'\1', text)
    text = re.sub(r'/[^:\s\n]+/([a-zA-Z0-9_.-]+)', r'\1', text)

    # Normalize line numbers (e.g. line 42 -> line NUM)
    text = re.sub(r"\bline\s+\d+\b", "line NUM", text, flags=re.IGNORECASE)
    text = re.sub(r":\d+:\d+", ":NUM:NUM", text)
    text = re.sub(r"\b\d+:\d+\b", "NUM:NUM", text)
    text = re.sub(r":\d+", ":NUM", text)

    # Normalize timestamps (e.g. 2026-10-02T15:30:00 or 15:30:00)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b", "TIMESTAMP", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "TIME", text)

    # Normalize PIDs and port numbers in standard formats
    text = re.sub(r"\bPID\s+\d+\b", "PID NUM", text, flags=re.IGNORECASE)
    text = re.sub(r"\bport\s+\d+\b", "port NUM", text, flags=re.IGNORECASE)

    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text[:300]


@dataclass
class FailureFingerprint:
    """Deterministic fingerprint representing an observed engineering failure."""

    operation: str  # e.g. "code_gen", "syntax_compile", "runtime_startup", "browser_verification"
    failure_type: str  # e.g. "SYNTAX_ERROR", "PORT_COLLISION", "MISSING_DEPENDENCY", "CANVAS_BLANK"
    target: str  # e.g. "script.js", "http://localhost:8080", "t-build-1"
    raw_error: str
    normalized_signature: str
    hash_key: str
    timestamp: float = field(default_factory=time.time)

    @property
    def fingerprint_hash(self) -> str:
        return self.hash_key

    def matches(self, other: "FailureFingerprint") -> bool:
        return isinstance(other, FailureFingerprint) and self.hash_key == other.hash_key

    @classmethod
    def create(
        cls,
        operation: str,
        failure_type: str,
        target: str,
        error_msg: str = "",
        error_message: str = "",
        phase: Optional[str] = None,
    ) -> "FailureFingerprint":
        msg = error_msg or error_message or ""
        norm_sig = normalize_error_message(msg)
        norm_target = str(target or "").replace("\\", "/").split("/")[-1].lower()
        key_raw = f"{operation.lower()}|{failure_type.lower()}|{norm_target}|{norm_sig}"
        hash_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()[:16]

        return cls(
            operation=operation,
            failure_type=failure_type,
            target=str(target or ""),
            raw_error=str(msg or "")[:500],
            normalized_signature=norm_sig,
            hash_key=hash_key,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "failure_type": self.failure_type,
            "target": self.target,
            "raw_error": self.raw_error,
            "normalized_signature": self.normalized_signature,
            "hash_key": self.hash_key,
            "timestamp": self.timestamp,
        }


class FailureTracker:
    """Tracks failure history per project/build to detect loops and enforce bounded recovery."""

    def __init__(self, loop_threshold: int = 2):
        self.loop_threshold = loop_threshold
        self.history: List[FailureFingerprint] = []
        self._target_last_error: Dict[str, str] = {}
        self._consecutive_counts: Dict[str, int] = {}
        self._target_hashes: Dict[str, Set[str]] = {}
        self._last_fingerprint: Optional[FailureFingerprint] = None

    @property
    def is_loop_detected(self) -> bool:
        """Check if any active consecutive count meets or exceeds loop_threshold."""
        return any(count >= self.loop_threshold for count in self._consecutive_counts.values())

    def record_failure(
        self,
        fingerprint_or_operation: Any = None,
        failure_type: Optional[str] = None,
        target: Optional[str] = None,
        error_msg: Optional[str] = None,
        error_message: Optional[str] = None,
        phase: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> bool:
        """Record an observed failure. Returns True if a repeated loop is detected."""
        if isinstance(fingerprint_or_operation, FailureFingerprint):
            fp = fingerprint_or_operation
        else:
            op = operation or fingerprint_or_operation or "unknown_op"
            err = error_msg or error_message or ""
            fp = FailureFingerprint.create(
                operation=str(op),
                failure_type=str(failure_type or "UNKNOWN"),
                target=str(target or ""),
                error_msg=err,
                phase=phase,
            )

        self.history.append(fp)
        self._last_fingerprint = fp
        self._target_last_error[fp.target] = fp.raw_error

        clean_t = str(fp.target or "").replace("\\", "/").split("/")[-1].lower()
        self._target_hashes.setdefault(clean_t, set()).add(fp.hash_key)

        prev_count = self._consecutive_counts.get(fp.hash_key, 0)
        new_count = prev_count + 1
        self._consecutive_counts[fp.hash_key] = new_count
        return new_count >= self.loop_threshold

    def check_loop(self, fingerprint: Optional[FailureFingerprint] = None, threshold: Optional[int] = None) -> bool:
        """Return True if the exact same failure fingerprint has occurred >= threshold times consecutively."""
        limit = threshold or self.loop_threshold
        fp = fingerprint or self._last_fingerprint
        if not fp:
            return False
        return self._consecutive_counts.get(fp.hash_key, 0) >= limit

    def record_success(self, target_or_operation: str = "", target: Optional[str] = None) -> None:
        """Clear recorded failures and counts for a successfully completed or recovered target."""
        clean_target = str(target or target_or_operation or "").replace("\\", "/").split("/")[-1].lower()
        if target:
            self._target_last_error.pop(target, None)
        if target_or_operation:
            self._target_last_error.pop(target_or_operation, None)

        hashes_to_clear: Set[str] = set()
        for t, hset in list(self._target_hashes.items()):
            if clean_target and (clean_target in t or t in clean_target):
                hashes_to_clear.update(hset)
                self._target_hashes.pop(t, None)

        for h in hashes_to_clear:
            self._consecutive_counts.pop(h, None)

    def get_last_error(self, target: str) -> Optional[str]:
        """Return the most recent raw error recorded for a target."""
        return self._target_last_error.get(target)

    def get_failure_count(
        self,
        operation_or_type: Optional[str] = None,
        target: Optional[str] = None,
        active_only: bool = False,
    ) -> int:
        """Return count of recorded failures matching the criteria."""
        clean_target = str(target or "").replace("\\", "/").split("/")[-1].lower() if target else None
        if active_only:
            count = 0
            for k, val in self._consecutive_counts.items():
                if not clean_target or clean_target in k:
                    count += val
            return count
        if not operation_or_type and not target:
            return len(self.history)
        count = 0
        for f in self.history:
            op_match = (
                not operation_or_type
                or f.operation.lower() == operation_or_type.lower()
                or f.failure_type.lower() == operation_or_type.lower()
            )
            target_match = (
                not clean_target
                or clean_target in f.target.replace("\\", "/").split("/")[-1].lower()
            )
            if op_match and target_match:
                count += 1
        return count

    def reset(self) -> None:
        """Reset all tracked history."""
        self.history.clear()
        self._target_last_error.clear()
        self._consecutive_counts.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_failures": len(self.history),
            "recent_fingerprints": [f.to_dict() for f in self.history[-10:]],
            "loop_threshold": self.loop_threshold,
        }
