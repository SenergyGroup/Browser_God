from __future__ import annotations

import pytest

from agent.README_handler import ReadmeSchemaParser


README_CONTENT = """
# Browser God Extension

```json
{
  "type": "enqueueCommand",
  "command": {
    "id": "agent-123",
    "type": "OPEN_URL",
    "payload": {
      "url": "https://example.com", // comment describing the URL
      "actions": [
        {
          "type": "WAIT",
          "payload": {"milliseconds": 500} // wait half a second
        }
      ]
    }
  }
}
```

Some additional context.

```json
{
  "type": "commandResult",
  "commandId": "agent-123",
  "result": {
    "status": "completed",
    "records": []
  }
}
```

`type` must match one of the service worker command handlers: `OPEN_URL`, `WAIT`, `SCROLL_TO_BOTTOM`
"""


@pytest.fixture
def readme_file(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(README_CONTENT, encoding="utf-8")
    return path


def test_readme_parser_happy_path(readme_file):
    parser = ReadmeSchemaParser(readme_file)
    documentation = parser.load()
    assert documentation.enqueue_command_example["type"] == "enqueueCommand"
    assert documentation.command_result_example["type"] == "commandResult"
    assert documentation.command_types == [
        "OPEN_URL",
        "WAIT",
        "SCROLL_TO_BOTTOM",
    ]

    as_dict = parser.to_dict()
    assert as_dict["source"] == str(readme_file)
    assert as_dict["enqueueCommand"]["command"]["payload"]["url"] == "https://example.com"


def test_readme_parser_refresh(readme_file):
    parser = ReadmeSchemaParser(readme_file)
    first = parser.get_documentation(refresh=True)
    second = parser.get_documentation()
    assert first is second


def test_missing_enqueue_block(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("No JSON here", encoding="utf-8")
    parser = ReadmeSchemaParser(path)
    with pytest.raises(ValueError, match="enqueueCommand JSON block"):
        parser.load()


def test_missing_command_result_block(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(
        """
```json
{"type": "enqueueCommand"}
```
        """.strip(),
        encoding="utf-8",
    )
    parser = ReadmeSchemaParser(path)
    with pytest.raises(ValueError, match="commandResult JSON block"):
        parser.load()
