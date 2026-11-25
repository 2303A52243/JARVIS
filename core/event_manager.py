"""Thread-safe Pub/Sub Event Manager for JARVIS.

Decouples the AI brain, voice subsystem, background monitors, and PySide6 UI.
Allows asynchronous background threads to notify UI components cleanly.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(str, Enum):
    """Event topics dispatched across JARVIS subsystems."""
    SYSTEM_LOG = "system_log"
    METRIC_UPDATE = "metric_update"
    VOICE_STATE_CHANGED = "voice_state_changed"
    VOICE_TRANSCRIPTION = "voice_transcription"
    VOICE_SPEAKING_START = "voice_speaking_start"
    VOICE_SPEAKING_FINISH = "voice_speaking_finish"
    CHAT_USER_MESSAGE = "chat_user_message"
    CHAT_AI_TOKEN = "chat_ai_token"
    CHAT_AI_RESPONSE = "chat_ai_response"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    TOOL_FAILED = "tool_failed"
    PERMISSION_REQUEST = "permission_request"
    EMERGENCY_STOP = "emergency_stop"
    CONFIG_RELOADED = "config_reloaded"


class EventManager:
    """Central thread-safe publish-subscribe dispatcher."""

    _instance: Optional[EventManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Any], None]]] = defaultdict(list)
        self._sub_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EventManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """Register a callback to be notified when event_type is published."""
        with self._sub_lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """Remove a previously registered callback."""
        with self._sub_lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event_type: EventType, data: Any = None) -> None:
        """Dispatch an event to all subscribed listeners safely."""
        with self._sub_lock:
            handlers = list(self._subscribers.get(event_type, []))

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                # Log or print error without raising to prevent one failing subscriber
                # from crashing other handlers
                print(f"[EventManager Error] Dispatch error on {event_type.value}: {e}")


def get_event_manager() -> EventManager:
    """Helper to access the event manager singleton."""
    return EventManager.get_instance()
