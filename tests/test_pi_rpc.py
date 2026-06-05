import asyncio

from ospilot.pi.events import PiEvent, event_text
from ospilot.pi.rpc import JsonRpcMessage, PiRpcClient, PiRpcCommand


def test_json_rpc_message_serializes_minimal_request() -> None:
    assert JsonRpcMessage(id=1, method="prompt", params={"prompt": "hi"}).to_json() == '{"jsonrpc":"2.0","id":1,"method":"prompt","params":{"prompt":"hi"}}'


def test_pi_rpc_command_serializes_prompt() -> None:
    assert PiRpcCommand(type="prompt", id=1, message="hi").to_json() == '{"type":"prompt","id":1,"message":"hi"}'


def test_route_message_resolves_pending_response() -> None:
    async def run() -> None:
        client = PiRpcClient()
        future = asyncio.get_running_loop().create_future()
        client._pending["7"] = future

        await client.route_message({"type": "response", "id": 7, "command": "get_state", "success": True, "data": {"ok": True}})

        assert await asyncio.wait_for(future, timeout=1) == {"type": "response", "id": 7, "command": "get_state", "success": True, "data": {"ok": True}}

    asyncio.run(run())


def test_route_message_dispatches_events() -> None:
    async def run() -> None:
        client = PiRpcClient()
        events = []
        client.add_event_handler(lambda event: events.append(event))

        await client.route_message({"event": "message_update", "payload": {"text": "hello"}})

        assert events[0].type == "message_update"
        assert events[0].payload["text"] == "hello"

    asyncio.run(run())


def test_event_text_ignores_reasoning_content_parts() -> None:
    event = PiEvent(
        type="message_end",
        payload={
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "reasoning", "text": "hidden thought"},
                    {"type": "text", "text": "final answer"},
                    {"kind": "thinking", "text": "hidden thinking"},
                ],
            }
        },
    )

    assert event_text(event) == "final answer"
