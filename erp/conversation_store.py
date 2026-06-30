"""
erp/conversation_store.py — short-lived, in-process memory for multi-turn
ERP write conversations (slot-filling across messages).

Design decisions
-----------------
* In-memory + thread-safe (a single Lock — fine at this volume; ERP write
  conversations are low-frequency compared to read queries). NOT persisted
  to disk/DB: a slot-filling exchange ("create customer Ahmed" -> "code
  AHMED001 type customer") is expected to complete within minutes, so
  losing state on a server restart is an acceptable trade-off for not
  adding a new persistence layer to a feature that's already touching a
  lot of new surface. If this needs to survive restarts later, swap this
  class's internals for a SQLite table (same pattern as auth/models.py)
  without changing its public functions below.
* Keyed by a `conversation_id` the FRONTEND generates and keeps (e.g. one
  per chat thread) — this module doesn't try to infer which messages
  belong together, it just stores whatever the caller hands it under
  that id.
* merge() overwrites a field if the same column is given again — this is
  what lets a user correct a previously given value mid-conversation
  ("actually make the type 'supplier' not 'customer'").
* Idle conversations are evicted after _TTL_SECONDS so this dict can't
  grow unbounded if conversations are abandoned mid-flow.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

_TTL_SECONDS = 30 * 60  # conversations idle longer than this are dropped


@dataclass
class ConversationState:
    conversation_id: str
    entity_name: str | None = None
    operation: str | None = None  # "CREATE" | "UPDATE"
    collected_fields: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ConversationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, ConversationState] = {}

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [cid for cid, s in self._states.items() if now - s.updated_at > _TTL_SECONDS]
        for cid in expired:
            del self._states[cid]
        if expired:
            logger.debug("Evicted %d expired ERP conversation(s)", len(expired))

    def get(self, conversation_id: str) -> ConversationState | None:
        with self._lock:
            self._evict_expired()
            return self._states.get(conversation_id)

    def merge(
        self,
        conversation_id: str,
        *,
        entity_name: str | None,
        operation: str | None,
        new_fields: dict[str, Any],
    ) -> ConversationState:
        """
        Create the conversation if it doesn't exist yet, otherwise merge
        `new_fields` into whatever has already been collected. Returns
        the resulting state (a live reference — callers should treat it
        as read-mostly outside this class).
        """
        with self._lock:
            self._evict_expired()
            state = self._states.get(conversation_id)
            if state is None:
                state = ConversationState(conversation_id=conversation_id)
                self._states[conversation_id] = state

            if entity_name:
                state.entity_name = entity_name
            if operation:
                state.operation = operation
            state.collected_fields.update(new_fields)
            state.updated_at = time.time()

            logger.debug(
                "Conversation %s merged: entity=%s op=%s fields=%s",
                conversation_id, state.entity_name, state.operation, list(state.collected_fields),
            )
            return state

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._states.pop(conversation_id, None)


# Module-level singleton — one store per process, mirrors core/db.py's
# singleton engine pattern.
_store = ConversationStore()


def get_conversation(conversation_id: str) -> ConversationState | None:
    return _store.get(conversation_id)


def merge_conversation(
    conversation_id: str,
    *,
    entity_name: str | None,
    operation: str | None,
    new_fields: dict[str, Any],
) -> ConversationState:
    return _store.merge(conversation_id, entity_name=entity_name, operation=operation, new_fields=new_fields)


def clear_conversation(conversation_id: str) -> None:
    _store.clear(conversation_id)