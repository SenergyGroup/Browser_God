"""Entry point for the Browser God local agent."""
from __future__ import annotations

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .messaging.bridge import ExtensionBridge
from .messaging.events import EventBroker

# Ensure logs directory exists
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # project root
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "agent.log"), encoding="utf-8"),
    ],
)

LOGGER = logging.getLogger("agent")  # project-wide logger name

app = FastAPI(title="Browser God Agent", version="0.1.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

event_broker = EventBroker()
extension_bridge = ExtensionBridge(event_broker)


@app.on_event("startup")
async def startup_event() -> None:
    LOGGER.info("Browser God Agent starting up")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    LOGGER.info("Browser God Agent shutting down")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    LOGGER.info("Health check called")
    return {"status": "ok"}


app.include_router(api_router)


__all__ = ["app", "event_broker", "extension_bridge"]
