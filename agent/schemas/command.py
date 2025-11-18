"""Pydantic models that represent commands exchanged with the extension."""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CommandType(str, Enum):
    OPEN_URL = "OPEN_URL"
    WAIT = "WAIT"
    SCROLL_TO_BOTTOM = "SCROLL_TO_BOTTOM"
    CLICK = "CLICK"
    CAPTURE_JSON_FROM_DEVTOOLS = "CAPTURE_JSON_FROM_DEVTOOLS"
    EXTRACT_SCHEMA = "EXTRACT_SCHEMA"


class CommandAction(BaseModel):
    """Represents a follow-up command executed after the primary action."""

    type: CommandType
    payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(cls, model: "CommandAction") -> "CommandAction":
        action_type = model.type
        payload = model.payload or {}

        if action_type == CommandType.WAIT:
            milliseconds = payload.get("milliseconds")
            if milliseconds is not None and (not isinstance(milliseconds, int) or milliseconds < 0):
                raise ValueError("WAIT action requires a non-negative integer 'milliseconds'")

        model.payload = payload
        return model


class Command(BaseModel):
    """Command payload validated against the README schema."""

    id: str = Field(default_factory=lambda: f"agent-{uuid.uuid4()}")
    type: CommandType
    payload: Dict[str, Any]

    @model_validator(mode="after")
    def validate_payload(cls, model: "Command") -> "Command":
        payload = model.payload or {}
        command_type = model.type

        if command_type == CommandType.OPEN_URL:
            url = payload.get("url")
            if not isinstance(url, str) or not url.strip():
                raise ValueError("OPEN_URL payload requires a non-empty 'url'")
            actions = payload.get("actions")
            if actions is not None:
                if not isinstance(actions, list):
                    raise ValueError("OPEN_URL payload 'actions' must be a list")
                validated_actions: List[CommandAction] = [
                    action if isinstance(action, CommandAction) else CommandAction(**action)
                    for action in actions
                ]
                payload["actions"] = [action.model_dump() for action in validated_actions]
        elif command_type == CommandType.WAIT:
            milliseconds = payload.get("milliseconds")
            if milliseconds is not None and (not isinstance(milliseconds, int) or milliseconds < 0):
                raise ValueError("WAIT payload 'milliseconds' must be a non-negative integer")
        elif command_type == CommandType.CAPTURE_JSON_FROM_DEVTOOLS:
            wait_for = payload.get("waitForMs")
            if wait_for is not None and (not isinstance(wait_for, int) or wait_for < 0):
                raise ValueError("CAPTURE_JSON_FROM_DEVTOOLS 'waitForMs' must be a non-negative integer")
            close_tab = payload.get("closeTab")
            if close_tab is not None and not isinstance(close_tab, bool):
                raise ValueError("CAPTURE_JSON_FROM_DEVTOOLS 'closeTab' must be a boolean")
        elif command_type in {CommandType.SCROLL_TO_BOTTOM, CommandType.CLICK, CommandType.EXTRACT_SCHEMA}:
            # For now we accept arbitrary payloads documented elsewhere.
            if not isinstance(payload, dict):
                raise ValueError("Command payload must be an object")

        model.payload = payload
        return model


class EnqueueCommandRequest(BaseModel):
    """Envelope for enqueueCommand messages."""

    type: Literal["enqueueCommand"] = Field("enqueueCommand")
    command: Command


class ToggleAgentControlRequest(BaseModel):
    enabled: bool


class RunCommandRequest(BaseModel):
    """Simplified request body for POST /run-command."""

    type: CommandType
    payload: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None

    def to_command(self) -> Command:
        payload = dict(self.payload)
        command_id = self.id or f"agent-{uuid.uuid4()}"
        return Command(id=command_id, type=self.type, payload=payload)


__all__ = [
    "Command",
    "CommandAction",
    "CommandType",
    "EnqueueCommandRequest",
    "RunCommandRequest",
    "ToggleAgentControlRequest",
]
