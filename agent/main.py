"""Entry point for the Browser God local agent."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .README_handler import ReadmeSchemaParser
from .api.routes import router as api_router
from .messaging.bridge import ExtensionBridge
from .messaging.events import EventBroker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Browser God Agent", version="0.1.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_DIR = Path(__file__).resolve().parent
README_PATH = AGENT_DIR.parent / "docs" / "external-agent" / "ReadMe.md"

if not README_PATH.exists():
    raise FileNotFoundError(f"README not found at {README_PATH}")

readme_parser = ReadmeSchemaParser(README_PATH)
event_broker = EventBroker()
extension_bridge = ExtensionBridge(event_broker)


@app.on_event("startup")
async def startup() -> None:
    try:
        readme_parser.load()
        LOGGER.info("Loaded README schema from %s", README_PATH)
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to parse README schema: %s", error)
        raise


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"status": "ok"}


app.include_router(api_router)


__all__ = ["app", "event_broker", "extension_bridge", "readme_parser"]
