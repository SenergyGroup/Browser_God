"""Static reference data describing the extension messaging contract."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


SCHEMA_DOCUMENTATION: Dict[str, Any] = {
    "enqueueCommand": {
        "type": "enqueueCommand",
        "command": {
            "id": "string",
            "type": "OPEN_URL",
            "payload": {
                "url": "https://www.etsy.com/",
                "actions": [
                    {
                        "type": "WAIT",
                        "payload": {"milliseconds": 1500},
                    },
                    {
                        "type": "CAPTURE_JSON_FROM_DEVTOOLS",
                        "payload": {"waitForMs": 2000, "closeTab": True},
                    },
                ],
            },
        },
    },
    "commandResult": {
        "type": "commandResult",
        "commandId": "string",
        "result": {
            "status": "completed",
            "errorCode": None,
            "records": [],
        },
    },
    "commandTypes": [
        "OPEN_URL",
        "WAIT",
        "SCROLL_TO_BOTTOM",
        "CLICK",
        "CAPTURE_JSON_FROM_DEVTOOLS",
        "EXTRACT_SCHEMA",
    ],
    "messages": {
        "getExtensionState": {
            "type": "getExtensionState",
        },
        "toggleAgentControl": {
            "type": "toggleAgentControl",
            "enabled": True,
        },
        "exportData": {
            "type": "exportData",
        },
    },
}


def get_schema_documentation() -> Dict[str, Any]:
    """Return a deep copy of the static schema documentation."""
    return deepcopy(SCHEMA_DOCUMENTATION)


__all__ = ["get_schema_documentation", "SCHEMA_DOCUMENTATION"]
