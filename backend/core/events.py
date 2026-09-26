"""Event system for NOVA Code Lab.

Provides structured event broadcasting, activity feeds, and system logging.
"""

from dataclasses import dataclass
import datetime
from typing import Callable, List, Optional


@dataclass
class Event:
    timestamp: str
    message: str
    level: str = "ok"  # ok, run, bad, dim
    source: str = "System"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "level": self.level,
            "source": self.source,
        }


class EventBus:
    """Central event bus for real-time activity tracking."""

    def __init__(self):
        self.listeners: List[Callable[[Event], None]] = []
        self.history: List[Event] = []

    def subscribe(self, listener: Callable[[Event], None]) -> None:
        self.listeners.append(listener)

    def publish(self, message: str, level: str = "ok", source: str = "System") -> Event:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        evt = Event(timestamp=ts, message=message, level=level, source=source)
        self.history.append(evt)
        for listener in self.listeners:
            try:
                listener(evt)
            except Exception:
                pass
        return evt

    def get_recent(self, count: int = 20) -> List[Event]:
        return self.history[-count:]
