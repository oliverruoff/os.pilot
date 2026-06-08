import asyncio

from ospilot.app import OSPilotApp, _merge_stream_text, _tool_status_text
from ospilot.pi.events import PiEvent, event_text, event_thinking_text, final_answer_text
from ospilot.pi.rpc import JsonRpcMessage, PiRpcClient, PiRpcCommand, _subprocess_startup_kwargs


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


def test_event_text_prefers_structured_final_content_over_generic_assistant_text() -> None:
    event = PiEvent(
        type="message_end",
        payload={
            "assistantMessageEvent": {
                "text": "I need to provide the concise answer.",
                "content": [
                    {"type": "reasoning", "text": "I need to provide the concise answer."},
                    {"type": "text", "text": "Done."},
                ],
            }
        },
    )

    assert event_text(event) == "Done."


def test_event_text_ignores_reasoning_delta_dict() -> None:
    event = PiEvent(type="message_update", payload={"delta": {"type": "reasoning", "text": "hidden thought"}})

    assert event_text(event) == ""


def test_event_text_ignores_reasoning_payload_text() -> None:
    event = PiEvent(type="message_update", payload={"type": "reasoning", "text": "hidden thought"})

    assert event_text(event) == ""


def test_merge_stream_text_deduplicates_partial_overlap() -> None:
    assert _merge_stream_text("Updated the final-response hand", "handling.\n\nTests passed.") == "Updated the final-response handling.\n\nTests passed."


def test_tool_status_text_replaces_empty_json_payload() -> None:
    assert _tool_status_text("{}", "ospilot_get_active_context") == "Running get active context..."


def test_tool_status_text_replaces_empty_finished_payload() -> None:
    assert _tool_status_text("{}", "ospilot_get_active_context", finished=True) == "Finished get active context."


def test_tool_status_text_preserves_real_status_text() -> None:
    assert _tool_status_text("Looking at your screen...", "ospilot_capture_screenshot_current_mouse_monitor") == "Looking at your screen..."


def test_message_end_replaces_duplicated_stream_buffer() -> None:
    app = OSPilotApp.__new__(OSPilotApp)
    app._active_prompt = False
    app._stream_buffer = "Done.Done."
    app._last_output = app._stream_buffer

    app._apply_pi_event("message_end", "assistant\nDone.")

    assert app._last_output == "Done."


def test_event_thinking_text_extracts_reasoning_content_parts() -> None:
    event = PiEvent(
        type="message_update",
        payload={
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "reasoning", "text": "thinking through it"},
                    {"type": "text", "text": "final answer"},
                    {"kind": "thought", "text": " and checking"},
                ],
            }
        },
    )

    assert event_thinking_text(event) == "thinking through it and checking"


def test_event_text_extracts_string_delta() -> None:
    event = PiEvent(type="message_update", payload={"delta": "Hi"})

    assert event_text(event) == "Hi"


def test_final_answer_text_strips_leading_reasoning_sentence() -> None:
    text = "the user said hi, I propably also should say Hi. Hi :)"

    assert final_answer_text(text) == "Hi :)"


def test_final_answer_text_uses_explicit_marker() -> None:
    text = "I need to answer briefly. Final answer: Hi :)"

    assert final_answer_text(text) == "Hi :)"


def test_final_answer_text_strips_leaked_reasoning_paragraph_prefix() -> None:
    text = "I need to mention what changed and include tests.\n\nUpdated the final-response handling.\n\nTests passed."

    assert final_answer_text(text) == "Updated the final-response handling.\n\nTests passed."


def test_final_answer_text_strips_multiple_leaked_reasoning_sentences() -> None:
    text = "The user asked if this is done. I should answer directly. Yes."

    assert final_answer_text(text) == "Yes."


def test_subprocess_startup_kwargs_hide_windows_console(monkeypatch) -> None:
    import subprocess

    monkeypatch.setattr("sys.platform", "win32")

    assert _subprocess_startup_kwargs() == {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
