"""Utilities for parsing the external agent README schema."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class CommandDocumentation:
    """Structured representation of the README schema details."""

    enqueue_command_example: Dict[str, Any]
    command_result_example: Dict[str, Any]
    command_types: List[str]


class ReadmeSchemaParser:
    """Parse the external agent README file for schema metadata."""

    COMMAND_TYPES_PATTERN = re.compile(
        r"`type` must match one of the service worker command handlers:\s*`([^`]+)`",
        re.IGNORECASE,
    )

    def __init__(self, readme_path: Path) -> None:
        self._readme_path = readme_path
        self._raw_text: str | None = None
        self._documentation: CommandDocumentation | None = None

    @property
    def readme_path(self) -> Path:
        return self._readme_path

    def load(self) -> CommandDocumentation:
        """Load and parse the README file, caching the structured output."""
        text = self._readme_path.read_text(encoding="utf-8")
        self._raw_text = text

        enqueue_example = self._extract_json_block(text, "enqueueCommand")
        result_example = self._extract_json_block(text, "commandResult")
        command_types = self._extract_command_types(text)

        documentation = CommandDocumentation(
            enqueue_command_example=enqueue_example,
            command_result_example=result_example,
            command_types=command_types,
        )
        self._documentation = documentation
        return documentation

    def get_documentation(self, refresh: bool = False) -> CommandDocumentation:
        """Return cached documentation, reloading from disk when requested."""
        if refresh or self._documentation is None:
            return self.load()
        return self._documentation

    def to_dict(self, refresh: bool = False) -> Dict[str, Any]:
        """Return the parsed documentation as a JSON-serialisable dict."""
        doc = self.get_documentation(refresh=refresh)
        return {
            "enqueueCommand": doc.enqueue_command_example,
            "commandResult": doc.command_result_example,
            "commandTypes": doc.command_types,
            "source": str(self._readme_path),
        }

    @classmethod
    def _extract_json_block(cls, text: str, heading: str) -> Dict[str, Any]:
        pattern = re.compile(
            rf"```json\s*{{\s*\"type\":\s*\"{heading}[^`]*?```",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            raise ValueError(f"Could not locate {heading} JSON block in README")
        block = match.group(0)
        cleaned = cls._strip_json_comments(block.split("```json", 1)[1].rsplit("```", 1)[0])
        return json.loads(cleaned)

    @staticmethod
    def _strip_json_comments(snippet: str) -> str:
        cleaned_lines = []
        for line in snippet.strip().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if "//" in line:
                line = line.split("//", 1)[0].rstrip()
            cleaned_lines.append(line)
        return "\n" + "\n".join(cleaned_lines) + "\n"

    @classmethod
    def _extract_command_types(cls, text: str) -> List[str]:
        match = cls.COMMAND_TYPES_PATTERN.search(text)
        if not match:
            return []
        raw = match.group(1)
        parts = [p.strip() for p in raw.split("`, `")]
        return [part.replace("`", "") for part in parts if part]


__all__ = ["ReadmeSchemaParser", "CommandDocumentation"]
