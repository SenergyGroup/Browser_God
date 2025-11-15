import pytest

from agent.schemas.command import (
    Command,
    CommandAction,
    CommandType,
    EnqueueCommandRequest,
    RunCommandRequest,
)


def test_open_url_with_actions_valid():
    command = Command(
        type=CommandType.OPEN_URL,
        payload={
            "url": "https://example.com",
            "actions": [
                {"type": CommandType.WAIT, "payload": {"milliseconds": 500}},
                {
                    "type": CommandType.CAPTURE_JSON_FROM_DEVTOOLS,
                    "payload": {"waitForMs": 1000, "closeTab": True},
                },
            ],
        },
    )

    actions = command.payload["actions"]
    assert isinstance(actions, list)
    assert actions[0]["payload"]["milliseconds"] == 500
    assert actions[1]["payload"] == {"waitForMs": 1000, "closeTab": True}


def test_open_url_requires_url():
    with pytest.raises(ValueError, match="requires a non-empty 'url'"):
        Command(type=CommandType.OPEN_URL, payload={"url": ""})


@pytest.mark.parametrize("actions", ["not-a-list", {"type": "WAIT"}])
def test_open_url_actions_must_be_list(actions):
    with pytest.raises(ValueError, match="actions' must be a list"):
        Command(
            type=CommandType.OPEN_URL,
            payload={"url": "https://example.com", "actions": actions},
        )


def test_open_url_invalid_nested_action():
    payload = {
        "url": "https://example.com",
        "actions": [
            {"type": CommandType.WAIT, "payload": {"milliseconds": -1}},
        ],
    }
    with pytest.raises(ValueError, match="non-negative integer 'milliseconds'"):
        Command(type=CommandType.OPEN_URL, payload=payload)


def test_wait_command_validation():
    command = Command(type=CommandType.WAIT, payload={"milliseconds": 0})
    assert command.payload["milliseconds"] == 0

    with pytest.raises(ValueError, match="non-negative integer"):
        Command(type=CommandType.WAIT, payload={"milliseconds": -5})

    with pytest.raises(ValueError, match="non-negative integer"):
        Command(type=CommandType.WAIT, payload={"milliseconds": "oops"})


def test_capture_json_from_devtools_validation():
    command = Command(
        type=CommandType.CAPTURE_JSON_FROM_DEVTOOLS,
        payload={"waitForMs": 1000, "closeTab": False},
    )
    assert command.payload == {"waitForMs": 1000, "closeTab": False}

    with pytest.raises(ValueError, match="waitForMs' must be a non-negative integer"):
        Command(
            type=CommandType.CAPTURE_JSON_FROM_DEVTOOLS,
            payload={"waitForMs": -1},
        )

    with pytest.raises(ValueError, match="'closeTab' must be a boolean"):
        Command(
            type=CommandType.CAPTURE_JSON_FROM_DEVTOOLS,
            payload={"closeTab": "yes"},
        )


@pytest.mark.parametrize("command_type", [
    CommandType.SCROLL_TO_BOTTOM,
    CommandType.CLICK,
    CommandType.EXTRACT_SCHEMA,
])
def test_generic_command_requires_dict_payload(command_type):
    command = Command(type=command_type, payload={"foo": "bar"})
    assert command.payload == {"foo": "bar"}

    with pytest.raises(ValueError, match="Command payload must be an object"):
        Command(type=command_type, payload="not-a-dict")


def test_command_action_wait_validation():
    with pytest.raises(ValueError, match="WAIT action requires a non-negative"):
        CommandAction(type=CommandType.WAIT, payload={"milliseconds": -10})

    action = CommandAction(type=CommandType.WAIT, payload={"milliseconds": 50})
    assert action.payload["milliseconds"] == 50


def test_run_command_request_to_command():
    request = RunCommandRequest(
        type=CommandType.OPEN_URL,
        payload={"url": "https://example.com"},
    )
    command = request.to_command()
    assert command.id.startswith("agent-")
    assert command.payload == {"url": "https://example.com"}

    request_with_id = RunCommandRequest(
        type=CommandType.WAIT,
        payload={"milliseconds": 100},
        id="agent-custom",
    )
    command_with_id = request_with_id.to_command()
    assert command_with_id.id == "agent-custom"


def test_enqueue_command_request_envelope():
    command = RunCommandRequest(
        type=CommandType.WAIT,
        payload={"milliseconds": 10},
    ).to_command()
    envelope = EnqueueCommandRequest(command=command)
    assert envelope.type == "enqueueCommand"
    assert envelope.command == command
