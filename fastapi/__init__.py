"""Minimal FastAPI stub used for testing without the real dependency."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class WebSocketDisconnect(Exception):
    pass


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class APIRouter:
    def __init__(self) -> None:
        self.routes: Dict[str, List[Callable[..., Any]]] = {
            "get": [],
            "post": [],
            "websocket": [],
        }

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes["get"].append(func)
            return func

        return decorator

    def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes["post"].append(func)
            return func

        return decorator

    def websocket(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes["websocket"].append(func)
            return func

        return decorator


class FastAPI:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.middlewares: List[tuple[Type[Any], Dict[str, Any]]] = []
        self.routers: List[APIRouter] = []
        self.routes: Dict[str, Callable[..., Any]] = {}

    def add_middleware(self, middleware: Type[Any], **options: Any) -> None:
        self.middlewares.append((middleware, options))

    def include_router(self, router: APIRouter) -> None:
        self.routers.append(router)

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes[path] = func
            return func

        return decorator


class WebSocket:
    async def accept(self) -> None:  # pragma: no cover - stub only
        raise NotImplementedError

    async def receive_text(self) -> str:  # pragma: no cover - stub only
        raise NotImplementedError

    async def send_text(self, data: str) -> None:  # pragma: no cover - stub only
        raise NotImplementedError

    async def send_json(self, data: Any) -> None:  # pragma: no cover - stub only
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - stub only
        raise NotImplementedError


__all__ = [
    "APIRouter",
    "Depends",
    "FastAPI",
    "HTTPException",
    "WebSocket",
    "WebSocketDisconnect",
]
