"""Manual command console for Browser God agent ↔ extension integration."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict

import httpx
import websockets

from .schemas.command import CommandType

LOGGER = logging.getLogger(__name__)


def _to_websocket_url(http_url: str) -> str:
    if http_url.startswith("https://"):
        return "wss://" + http_url[len("https://") :]
    if http_url.startswith("http://"):
        return "ws://" + http_url[len("http://") :]
    return http_url


class ManualConsole:
    """Tiny interactive console that mirrors agent endpoints."""

    def __init__(self, agent_base_url: str) -> None:
        self.agent_base_url = agent_base_url.rstrip("/")
        self.events_url = f"{_to_websocket_url(self.agent_base_url)}/events"
        self.client = httpx.AsyncClient(base_url=self.agent_base_url, timeout=30)
        self._running = True

    async def __aenter__(self) -> "ManualConsole":
        return self

    async def __aexit__(self, *exc: Any) -> None:  # noqa: ANN401
        self._running = False
        await self.client.aclose()

    async def run(self) -> None:
        """Start the console input loop and event listener."""

        event_task = asyncio.create_task(self._event_listener())
        try:
            await self._command_loop()
        finally:
            self._running = False
            event_task.cancel()
            try:
                await event_task
            except asyncio.CancelledError:
                pass

    async def _command_loop(self) -> None:
        self._print_help()
        while self._running:
            try:
                raw = await asyncio.to_thread(input, "agent> ")
            except (EOFError, KeyboardInterrupt):
                print("Exiting console")
                break

            command = raw.strip()
            if not command:
                continue
            if command in {"exit", "quit"}:
                break
            if command == "help":
                self._print_help()
                continue
            if command == "state":
                await self._show_state()
                continue
            if command.startswith("ai_task "):
                await self._run_ai_task(command)
                continue
            if command.startswith("toggle"):
                await self._toggle(command)
                continue
            if command.startswith("run "):
                await self._run_command_from_text(command)
                continue
            if command.startswith("open "):
                await self._open_url(command)
                continue
            print("Unknown command. Type 'help' for options.")

    async def _run_command_from_text(self, command: str) -> None:
        parts = command.split(maxsplit=2)
        if len(parts) < 2:
            print("Usage: run <COMMAND_TYPE> {optional JSON payload}")
            return
        command_type = parts[1]
        payload: Dict[str, Any] = {}
        if len(parts) == 3:
            try:
                payload = json.loads(parts[2])
            except json.JSONDecodeError as error:
                print(f"Invalid JSON payload: {error}")
                return
        await self._send_command(command_type, payload)

    async def _open_url(self, command: str) -> None:
        parts = command.split(maxsplit=1)
        if len(parts) != 2:
            print("Usage: open <url>")
            return
        url = parts[1]
        payload = {"url": url}
        await self._send_command("OPEN_URL", payload)

    async def _toggle(self, command: str) -> None:
        tokens = command.split()
        if len(tokens) != 2 or tokens[1] not in {"on", "off"}:
            print("Usage: toggle <on|off>")
            return
        enabled = tokens[1] == "on"
        try:
            response = await self.client.post("/toggle-agent-control", json={"enabled": enabled})
            response.raise_for_status()
            data = response.json()
            print(f"Agent control {'enabled' if enabled else 'disabled'}: {data}")
        except Exception as error:  # noqa: BLE001
            print(f"Toggle failed: {error}")

    async def _show_state(self) -> None:
        try:
            response = await self.client.get("/state")
            response.raise_for_status()
            print(json.dumps(response.json(), indent=2))
        except Exception as error:  # noqa: BLE001
            print(f"Failed to fetch state: {error}")

    async def _run_ai_task(self, command: str) -> None:
        parts = command.split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            print('Usage: ai_task "<search topic>"')
            return

        topic = parts[1].strip().strip('"')
        search_terms = await self._generate_search_terms(topic)
        if not search_terms:
            print("Failed to generate search terms")
            return

        LOGGER.info(
            "Generated %s search terms: %s. Sending to extension.",
            len(search_terms),
            search_terms,
        )
        payload = {"searchTerms": search_terms}
        await self._send_command(CommandType.EXECUTE_SEARCH_TASK.value, payload)

    async def _generate_search_terms(self, topic: str) -> list[str]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Missing OPENAI_API_KEY environment variable")
            return []

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        system_prompt = (
            "You generate concise Etsy search queries. Return ONLY a JSON array of 5-10 short, "
            "diverse search terms relevant to the provided topic."
        )
        user_prompt = f"Topic: {topic}\nReturn only the JSON array."

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 256
                    }
                )
                response.raise_for_status()
                content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as error:  # noqa: BLE001
            print(f"LLM request failed: {error}")
            return []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            try:
                cleaned = content[content.index("[") : content.rindex("]") + 1]
                parsed = json.loads(cleaned)
            except Exception:  # noqa: BLE001
                print("LLM response was not valid JSON")
                return []

        search_terms = [term.strip() for term in parsed if isinstance(term, str) and term.strip()]
        return search_terms[:10]

    async def _send_command(self, command_type: str, payload: Dict[str, Any]) -> None:
        body = {"type": command_type, "payload": payload}
        try:
            response = await self.client.post("/run-command", json=body)
            response.raise_for_status()
            data = response.json()
            print(
                "Queued command %s (%s): %s"
                % (command_type, data.get("commandId"), data.get("result"))
            )
        except Exception as error:  # noqa: BLE001
            print(f"Command failed: {error}")

    async def _event_listener(self) -> None:
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self.events_url) as websocket:
                    print(f"[events] connected to {self.events_url}")
                    backoff = 1
                    async for raw in websocket:
                        self._handle_event(raw)
            except asyncio.CancelledError:
                return
            except Exception as error:  # noqa: BLE001
                if not self._running:
                    return
                print(f"[events] disconnected: {error}. reconnecting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)

    def _handle_event(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[events] {raw}")
            return

        event_type = event.get("type") or event.get("envelope")
        print(f"[events] {event_type}: {json.dumps(event, indent=2)}")

    def _print_help(self) -> None:
        print(
            """
Available commands:
  state                 Show extension state via /state
  toggle <on|off>       Enable or disable agent control
  ai_task "<topic>"       Generate search terms and run EXECUTE_SEARCH_TASK
  open <url>            Queue a basic OPEN_URL command
  run <TYPE> {json}     Queue any command with optional JSON payload
  help                  Show this help message
  exit|quit             Close the console

Examples:
  run WAIT {"milliseconds": 1000}
  run OPEN_URL {"url": "https://example.com", "actions": [{"type": "WAIT", "payload": {"milliseconds": 500}}]}
  run CAPTURE_JSON_FROM_DEVTOOLS {"tabId": 123, "waitForMs": 2000}
"""
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Manual Browser God command console")
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8000",
        help="Base URL where the FastAPI agent is running",
    )
    args = parser.parse_args()

    async with ManualConsole(args.agent_url) as console:
        await console.run()


if __name__ == "__main__":
    asyncio.run(main())
