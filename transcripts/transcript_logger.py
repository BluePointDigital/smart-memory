"""Transcript append helpers for Smart Memory v3.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .transcript_models import TranscriptMessage, TranscriptMessageInput, TranscriptSession
from .transcript_store import TranscriptStore


@dataclass(frozen=True)
class TranscriptAppendResult:
    session: TranscriptSession
    messages: list[TranscriptMessage]


class TranscriptLogger:
    def __init__(self, transcript_store: TranscriptStore | None = None) -> None:
        self.transcript_store = transcript_store or TranscriptStore()

    def append_message(
        self,
        *,
        session_id: str | None,
        role: str,
        source_type: str,
        content: str,
        created_at: datetime | None = None,
        tool_name: str | None = None,
        parent_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        label: str = "",
    ) -> TranscriptAppendResult:
        payload = TranscriptMessageInput(
            session_id=session_id,
            role=role,
            source_type=source_type,
            content=content,
            created_at=created_at,
            tool_name=tool_name,
            parent_message_id=parent_message_id,
            metadata=metadata or {},
            label=label,
        )
        message = self.transcript_store.append_message(payload)
        session = self.transcript_store.get_session(message.session_id)
        assert session is not None
        return TranscriptAppendResult(session=session, messages=[message])

    def append_interaction(
        self,
        *,
        session_id: str | None,
        user_message: str,
        assistant_message: str = "",
        created_at: datetime | None = None,
        source_type: str = "conversation",
        metadata: dict[str, Any] | None = None,
        label: str = "",
    ) -> TranscriptAppendResult:
        messages: list[TranscriptMessage] = []
        append_user = self.append_message(
            session_id=session_id,
            role="user",
            source_type=source_type,
            content=user_message,
            created_at=created_at,
            metadata=metadata,
            label=label,
        )
        messages.extend(append_user.messages)
        resolved_session = append_user.session

        if assistant_message.strip():
            append_assistant = self.append_message(
                session_id=resolved_session.session_id,
                role="assistant",
                source_type=source_type,
                content=assistant_message,
                created_at=created_at,
                parent_message_id=messages[-1].message_id,
                metadata=metadata,
                label=label,
            )
            messages.extend(append_assistant.messages)

        return TranscriptAppendResult(session=resolved_session, messages=messages)
