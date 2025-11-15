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
        r"`type` must match one of the service worker command handlers:\s*((?:`[^`]+`(?:,\s*)?)*)",
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
        for raw_line in snippet.strip().splitlines():
            line = raw_line.rstrip("\n\r")
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("//"):
                continue
            cleaned_line = []
            in_string = False
            escape = False
            i = 0
            while i < len(line):
                char = line[i]
                if char == "\\" and not escape:
                    escape = True
                    cleaned_line.append(char)
                    i += 1
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                if not in_string and char == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    break
                cleaned_line.append(char)
                escape = False
                i += 1
            final = "".join(cleaned_line).rstrip()
            if final:
                cleaned_lines.append(final)
        return "\n" + "\n".join(cleaned_lines) + "\n"

    @classmethod
    def _extract_command_types(cls, text: str) -> List[str]:
        match = cls.COMMAND_TYPES_PATTERN.search(text)
        if not match:
            return []
        raw = match.group(1)
        return [value for value in re.findall(r"`([^`]+)`", raw)]


__all__ = ["ReadmeSchemaParser", "CommandDocumentation"]
