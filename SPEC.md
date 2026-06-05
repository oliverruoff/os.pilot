# OSPilot — SPEC.md

## 1. Project Summary

Build a standalone macOS menu-bar/background desktop agent named **OSPilot**.

OSPilot is a lightweight cursor companion around **pi-coding-agent**. It does not implement its own LLM orchestration, model loop, or provider routing. Instead, OSPilot launches and interfaces with `pi-coding-agent` through JSON-RPC, maps pi runtime events into a native desktop companion UI, and exposes macOS desktop actions to pi as tools.

The product experience is not a traditional centered chat window. The app behaves like a cursor-attached assistant: a small floating bubble appears near the mouse cursor while the user is entering input, pi is thinking, pi is responding, or pi is executing desktop tools.

OSPilot should run primarily as a background/menu-bar app with global shortcuts.

---

## 2. Core Goals

The application should:

1. Run locally on macOS as a menu-bar/background app.
2. Use `pi-coding-agent` as the orchestration/runtime dependency.
3. Interface with pi through JSON-RPC as much as possible.
4. Reuse pi-coding-agent's provider and model configuration as much as possible, similar to `pi.lot`.
5. Be invoked through global shortcuts.
6. Display transient cursor companion UI next to the cursor.
7. Expose desktop tools to pi through a pi extension.
8. Let pi decide when to call tools, including screenshot capture.
9. Animate agent-driven mouse movement instead of teleporting the cursor.
10. Visually mark agent-driven cursor movement with a colored halo/ring/glow.
11. Include an emergency stop shortcut that aborts pi and local actions.
12. Include privacy-conscious logging and debugging.

---

## 3. Non-Goals for MVP

The MVP should not include:

- Independent LLM orchestration outside pi.
- Independent provider/model routing outside pi.
- A custom multi-step agent loop outside pi.
- Full permission-management UI.
- Real voice transcription if it slows down the first version.
- Windows/Linux support.
- Persistent long-term memory beyond pi session files.
- Continuous background screen monitoring.
- A large persistent chat window.
- Cloud-hosted orchestration.
- Confirmation gates for risky tools.

Voice mode may be a placeholder initially.

---

## 4. High-Level Architecture

```text
OSPilot macOS App
  ├─ macOS Shell / UI Layer
  │  ├─ Menu-bar app
  │  ├─ Global shortcut listener
  │  ├─ Cursor companion bubble
  │  ├─ Cursor halo / target highlight overlay
  │  ├─ Local IPC server for desktop tools
  │  └─ Local desktop action executor
  │
  ├─ Pi Runtime Bridge
  │  ├─ Launches pi-coding-agent in JSON-RPC mode
  │  ├─ Sends prompts to pi
  │  ├─ Sends abort/new-session commands
  │  ├─ Handles pi events
  │  ├─ Maps pi events to UI states
  │  └─ Handles extension UI responses
  │
  ├─ Pi Extension Layer
  │  ├─ TypeScript extension registered with pi
  │  ├─ Desktop tool schemas
  │  ├─ Calls local OSPilot IPC endpoint
  │  └─ Returns structured results to pi
  │
  └─ Config / Logs / Runtime Data
     ├─ pi provider/model config passthrough
     ├─ Environment variable loading
     ├─ Pi session directory
     └─ Local logs
```

Implementation should be **Python-first**:

- Python + PySide6 for menu-bar app and companion UI.
- Python local IPC server for desktop actions.
- Python JSON-RPC bridge to pi.
- TypeScript pi extension for registering OSPilot desktop tools with pi.

---

## 5. Runtime Dependency: pi-coding-agent

OSPilot depends on `pi-coding-agent` and should use it as the primary agent runtime.

OSPilot should launch pi similarly to `pi.lot`:

```bash
pi --mode rpc --skill <ospilot-skills-dir>
```

Additional args may be supplied through `PI_ARGS`.

The JSON-RPC bridge should support at minimum:

```text
prompt
abort
new_session
get_state
extension_ui_response
```

The bridge should consume pi stdout as newline-delimited JSON objects and handle both responses and events.

Important pi events to handle:

```text
agent_start
turn_start
message_update
message_end
agent_end
extension_ui_request
extension_error
queue_update
auto_retry_start
auto_retry_end
```

---

## 6. Pi Provider and Model Configuration

Provider and model selection should be owned by pi-coding-agent.

OSPilot must not hardcode a specific provider, model, model role, or routing policy. It should pass through the same provider/model environment variables and pi CLI arguments that the user would use with pi directly.

The primary model-selection mechanism is `PI_ARGS`, same as `pi.lot`:

```env
PI_ARGS=--model <provider>/<model>
```

OSPilot may install or copy pi-compatible provider override files when useful, but those files are provider configuration for pi, not OSPilot-owned routing logic.

Example optional provider override, matching the pattern currently used by `pi.lot` for Kimi:

```json
{
  "providers": {
    "kimi-coding": {
      "headers": {
        "User-Agent": "gsd-pi"
      }
    }
  }
}
```

Secrets must be environment variables only.

Example `.env` values for Kimi, if the user chooses Kimi:

```env
KIMI_API_KEY=replace-me
PI_ARGS=--model kimi-coding/<model-name>
```

Example `.env` values for another provider should work the same way, using whatever environment variables pi-coding-agent expects for that provider.

OSPilot should pass relevant environment variables through to the pi subprocess without interpreting provider-specific secrets where possible.

OSPilot should not implement separate model-role routing in the MVP. pi owns provider/model behavior, retries, capabilities, and provider-specific request handling.

---

## 7. Runtime Paths

Recommended paths:

```text
Config:
  ~/.config/ospilot/config.yaml

App data:
  ~/Library/Application Support/OSPilot

Pi sessions:
  ~/Library/Application Support/OSPilot/pi-sessions

Logs:
  ~/Library/Logs/OSPilot/ospilot.log

Optional pi provider/model config overrides managed by OSPilot:
  ~/Library/Application Support/OSPilot/pi/models.json

Pi extensions managed by OSPilot:
  ~/Library/Application Support/OSPilot/pi/extensions
```

If pi requires global agent config paths, OSPilot may copy or link its optional provider/model config overrides and extensions into the required pi config directory, but should keep OSPilot-owned source files in the application data directory.

---

## 8. Menu-Bar App

OSPilot should run as a menu-bar/background app.

For MVP:

- Use `PySide6` and `QSystemTrayIcon`.
- Do not show a normal main window by default.
- Show transient companion bubbles only when needed.
- Provide a tray menu.

Suggested tray menu items:

```text
Open Chat
Open Voice
New Session
Stop
Quit
```

For packaged macOS app builds, use `LSUIElement` so the app can run without a Dock icon.

---

## 9. Global Shortcuts

Required global shortcuts:

```text
Cmd + ,  Open voice input
Cmd + .  Open chat input
Cmd + <  Emergency stop
```

Notes:

- `Cmd + ,` is intentionally used for voice input even though it commonly means Preferences in many apps.
- Shortcut handling should work while OSPilot is in the background.
- Prefer macOS-native shortcut registration through PyObjC/Carbon APIs if practical.
- A Python hotkey listener may be used as an initial fallback if native registration delays the MVP.

---

## 10. User Experience

### 10.1 Cursor Companion UI

The UI must not be a centered chat window.

Instead, implement a transient cursor-attached companion bubble.

The companion appears when:

- The user opens chat input.
- The user opens voice input.
- The user enters a prompt.
- pi is thinking.
- pi streams a response.
- pi previews or executes a desktop tool.
- An error occurs.

The companion should be hidden otherwise.

### 10.2 Companion Positioning

The companion bubble should:

- Appear near the mouse cursor.
- Default to the lower-right side of the cursor.
- Flip to another side if it would go off-screen.
- Stay within the bounds of the monitor containing the cursor.
- Follow cursor movement smoothly with easing when appropriate.
- Avoid covering the cursor itself.
- Avoid covering target UI elements during action execution when practical.

During active typing, the bubble may temporarily anchor to its initial position to avoid distracting movement.

Suggested offset:

```text
18-28 px away from cursor
```

Suggested input size:

```text
Width: 320-420 px
Height: auto, initial 48-80 px
```

Suggested output size:

```text
Width: 360-520 px
Max height: 40% of monitor height
Scrollable if content is longer
```

### 10.3 UI States

The UI should support these states:

```text
hidden:
  No visible UI.

chat_input:
  Small prompt field next to the cursor.

voice_input:
  Voice-mode bubble. Real speech-to-text may be a placeholder in MVP.

thinking:
  Compact status bubble, e.g. "Thinking..." or pi status text.

output:
  Answer bubble next to the cursor.

tool_running:
  Shows compact status while a pi tool executes.

extension_ui:
  Shows pi extension UI request and lets user type a response.

error:
  Shows a compact error message.
```

---

## 11. Prompt and Session Behavior

OSPilot sends user prompts to pi through JSON-RPC.

Session history is owned by pi.

Session rules:

1. Keep the current pi session until app quit or `/new`.
2. If the user types `/new`, call pi `new_session`.
3. Do not implement separate long-term memory in OSPilot MVP.
4. Use `PI_CODING_AGENT_SESSION_DIR` to store pi sessions under OSPilot app data.

Prompt behavior:

- Do not automatically capture a screenshot when chat or voice input opens.
- Screenshot capture is a tool pi may call when it decides visual context is useful.
- OSPilot may include concise desktop context in the prompt when cheap and available, such as mouse position or active app, but pi remains responsible for reasoning and tool choice.

---

## 12. Screenshot Behavior

Screenshot capture is not automatic.

`ospilot_capture_screenshot_current_mouse_monitor` is a tool exposed to pi.

When pi calls this tool:

1. Determine the current mouse position.
2. Determine which monitor contains that mouse position.
3. Capture only that monitor.
4. Return structured metadata and screenshot reference.

Do not capture all monitors by default.

Suggested tool result:

```json
{
  "ok": true,
  "screenshot_path": "/path/to/screenshot.png",
  "mouse_position": {"x": 1200, "y": 640},
  "monitor_bounds": {"x": 0, "y": 0, "width": 3024, "height": 1964},
  "screenshot_size": {"width": 3024, "height": 1964},
  "scale_factor": 2.0
}
```

Screenshots should not be stored permanently by default unless needed for the tool result. Temporary files should be cleaned up when safe.

---

## 13. Desktop Tools Exposed To pi

Desktop tools should be registered with pi through a TypeScript extension using `pi.registerTool(...)`.

The extension should call back into the running Python OSPilot app through local IPC.

Preferred IPC:

```text
HTTP server bound to 127.0.0.1
Random per-run bearer token passed to the extension through environment variables
JSON request/response payloads
```

This keeps pi tool schemas native to pi while letting the Python app perform macOS-specific actions and coordinate UI effects.

### 13.1 Initial Tools

Implement these first:

```text
ospilot_get_active_context()
ospilot_capture_screenshot_current_mouse_monitor()
ospilot_show_companion_message(text)
ospilot_move_mouse(target, duration_ms optional, highlight optional)
ospilot_press_hotkey(keys)
ospilot_read_clipboard()
ospilot_write_clipboard(text)
ospilot_run_shell_command(command, cwd optional)
```

Then add:

```text
ospilot_click(target optional)
ospilot_double_click(target optional)
ospilot_type_text(text)
ospilot_open_app(app_name)
```

### 13.2 Tool Result Format

Each IPC endpoint and pi tool should return structured results.

Example:

```json
{
  "ok": true,
  "tool": "ospilot_run_shell_command",
  "stdout": "...",
  "stderr": "",
  "metadata": {
    "exit_code": 0,
    "duration_ms": 423
  }
}
```

---

## 14. Coordinate System

Tools should prefer normalized coordinates relative to the screenshot or monitor when interacting with visual targets.

Example:

```json
{
  "x": 0.52,
  "y": 0.34
}
```

The local macOS action executor translates normalized coordinates into actual screen coordinates.

Rules:

1. Visual target tool calls should use normalized coordinates by default.
2. The local executor handles conversion to physical/logical coordinates.
3. The executor must account for Retina scaling.
4. The executor must account for multi-monitor bounds.
5. Screenshot dimensions and monitor bounds must be included in screenshot tool results.

---

## 15. Mouse Movement and Visual Feedback

Agent-controlled mouse movement must be visible and understandable.

The agent must not instantly teleport the cursor to a target position unless explicitly configured for debugging.

### 15.1 Animated Movement

When executing a mouse move:

1. Read the current cursor position.
2. Convert target coordinates to screen coordinates.
3. Move the cursor smoothly over a configurable duration.
4. Use easing, not linear jump movement.
5. Optionally pause briefly at the target before clicking.

Suggested default duration:

```text
300-800 ms depending on distance
```

### 15.2 Cursor Halo

During agent-controlled cursor movement, draw a visual marker around the cursor.

Do not attempt to modify the native macOS cursor directly. Draw a transparent overlay with a colored ring/glow/halo around the cursor position.

Suggested colors:

```text
Blue: agent is moving the mouse
Yellow: agent/pi is thinking or waiting
Green: agent is executing a local action
Red: action blocked, errored, or stopped
```

### 15.3 Target Highlight

Before clicking, optionally highlight the target point or target area briefly.

### 15.4 Do Not Block Target

Before executing a mouse or click action, check if the companion bubble overlaps the target area. If it does, move the bubble to the opposite side or hide it temporarily.

---

## 16. Emergency Stop

The emergency stop shortcut is:

```text
Cmd + <
```

It must:

- Send pi `abort`.
- Cancel active local tool execution when possible.
- Cancel active mouse movement.
- Prevent the next planned local action if queued.
- Hide or reset the companion UI.
- Return OSPilot to a safe idle state.

If pi is unresponsive after abort, OSPilot may restart the pi RPC subprocess.

---

## 17. Safety Model for MVP

For the first MVP, do not implement confirmation gates.

pi may decide to call exposed OSPilot tools autonomously based on the user prompt and available tool descriptions.

Still keep tool boundaries explicit and structured so confirmation can be added later.

Future risk categories:

```text
read_only:
  Screenshot capture
  Active app detection
  Mouse position read
  Screen bounds read
  Window title read

visual:
  Show companion bubble
  Show cursor halo
  Highlight target point

safe_action:
  Move mouse
  Focus window
  Open app
  Press harmless hotkeys

medium_risk:
  Click button
  Type text
  Fill form
  Write clipboard
  Prepare terminal command

high_risk:
  Execute shell command
  Modify files
  Delete files
  Use sudo
  Git push
  Publish packages
  Deploy applications
  Install/uninstall software
  Send external data
```

Future versions should add confirmation for high-risk actions.

---

## 18. Privacy and Security

Screenshots can contain sensitive information.

Privacy requirements:

1. Screenshots are captured only when pi calls the screenshot tool.
2. Screenshots are not stored permanently by default.
3. Conversation logs are optional/configurable.
4. Debug screenshot storage is off by default.
5. API keys are stored in environment variables for MVP.
6. Avoid logging secrets.
7. Local IPC must bind only to `127.0.0.1`.
8. Local IPC must use a random per-run token.

Optional settings:

```yaml
privacy:
  store_screenshots: false
  store_conversations: false
  redact_secrets_best_effort: true
  debug_mode: false
```

---

## 19. Logging and Debugging

Logs should help debug behavior without leaking unnecessary private data.

Suggested log fields:

```text
timestamp
request_id
pi_session
pi_event_type
selected_model if available from pi event/state
actions_requested
actions_executed
errors
runtime_ms
```

By default:

- Do not store screenshots.
- Do not store full prompts unless user enables debug logging.
- Store pi event metadata, tool metadata, action results, and errors.

Log path:

```text
~/Library/Logs/OSPilot/ospilot.log
```

---

## 20. macOS Permissions

The app will likely require:

```text
Screen Recording permission
Accessibility permission
Input Monitoring permission, depending on hotkey/input implementation
Automation permission, depending on app control implementation
```

No full permission-management UI is required for MVP.

If a permission-dependent operation fails, show a concise error in the companion bubble.

Example:

```text
Screen Recording permission is required to capture the current monitor.
```

---

## 21. Voice Input

`Cmd + ,` opens voice input mode.

For MVP, voice input may be a placeholder state.

Acceptable first behavior:

- Show a voice-mode companion bubble.
- Indicate that real speech-to-text is not wired yet.
- Optionally allow typed fallback input from the same bubble.

Once real transcription exists, the transcribed text should be sent to pi as a normal prompt.

---

## 22. Suggested MVP Implementation Plan

### Phase 1 — Spec, Scaffold, and pi RPC

Implement:

- Python package `ospilot`.
- Basic config/env loading.
- App data/log directories.
- Provider/model config passthrough to pi, including support for optional pi-compatible provider overrides such as the `kimi-coding` override used by `pi.lot`.
- Pi JSON-RPC bridge adapted from the pi.lot approach.
- Start/stop pi subprocess.
- Send prompt and receive streamed pi events.

Acceptance criteria:

```text
OSPilot can launch pi in RPC mode, send a prompt, and receive pi events.
```

### Phase 2 — Menu-Bar App and Chat Bubble

Implement:

- PySide6 menu-bar app.
- Tray menu.
- Chat input bubble.
- Output/thinking bubble.
- Map pi events to companion UI states.
- `/new` calls pi `new_session`.

Acceptance criteria:

```text
User can open chat input, submit a prompt, and see pi response in the cursor companion bubble.
```

### Phase 3 — Shortcuts and Emergency Stop

Implement:

- `Cmd + .` chat shortcut.
- `Cmd + ,` voice placeholder shortcut.
- `Cmd + <` emergency stop.
- Abort pi and reset UI.

Acceptance criteria:

```text
Global shortcuts work while OSPilot is in the background, and emergency stop aborts active runs.
```

### Phase 4 — pi Extension and Local IPC

Implement:

- Local HTTP IPC server bound to `127.0.0.1`.
- Random per-run auth token.
- TypeScript pi extension registering OSPilot desktop tools.
- Basic IPC schema validation.

Acceptance criteria:

```text
pi can call an OSPilot tool through the extension and receive structured results.
```

### Phase 5 — Desktop Tools

Implement:

- get active context
- screenshot current mouse monitor
- move mouse
- press hotkey
- read/write clipboard
- run shell command

Acceptance criteria:

```text
pi can decide to call desktop tools, including screenshot capture, through OSPilot.
```

### Phase 6 — Animated Cursor and Halo

Implement:

- Smooth cursor movement.
- Cursor halo overlay.
- Target highlight.
- Companion avoidance of target area when practical.

Acceptance criteria:

```text
Agent-driven mouse actions are visible, smooth, and cancellable.
```

### Phase 7 — Logging and Tests

Implement:

- Local logs.
- Coordinate mapping tests.
- Pi RPC response routing tests.
- IPC tool schema tests.
- Session reset tests.

Acceptance criteria:

```text
Core runtime behavior is test-covered and logs are useful without storing sensitive content by default.
```

---

## 23. Recommended Repository Structure

```text
OSPilot/
  README.md
  SPEC.md
  pyproject.toml
  config.example.yaml
  .env.example
  models.json optional

  src/
    ospilot/
      __init__.py
      app.py
      config.py
      logging.py
      paths.py

      pi/
        __init__.py
        rpc.py
        events.py
        runtime.py

      ui/
        __init__.py
        tray.py
        companion.py
        halo.py

      ipc/
        __init__.py
        server.py
        auth.py
        schemas.py

      desktop/
        __init__.py
        backend.py
        registry.py
        common/
          clipboard.py
          coordinates.py
          shell.py
        macos/
          backend.py
          context.py
          screenshot.py
          mouse.py
          keyboard.py
          apps.py
          shortcuts.py
          ui_elements.py
          window.py
        windows/
          backend.py
          context.py
          screenshot.py
          mouse.py
          keyboard.py
          apps.py
          shortcuts.py
          ui_elements.py
          window.py

  pi/
    tools/
      ospilot-desktop-tools.ts
    skills/
      README.md

  tests/
    test_pi_rpc.py
    test_coordinate_mapping.py
    test_ipc_schema.py
    test_config.py
    test_session_commands.py
```

---

## 24. Acceptance Criteria for MVP v0.1

MVP v0.1 is complete when:

1. App launches locally on macOS as a menu-bar/background app.
2. OSPilot launches `pi-coding-agent` in JSON-RPC mode.
3. Provider/model selection works through pi config/env/`PI_ARGS`, with Kimi selectable the same way as in `pi.lot` when the user configures it.
4. `Cmd + .` opens a small companion chat bubble near the cursor.
5. Bubble accepts text input and sends it to pi.
6. pi responses appear in the cursor companion bubble.
7. `Cmd + ,` opens a voice-input placeholder bubble.
8. `Cmd + <` emergency stop aborts pi and cancels local actions.
9. `/new` starts a new pi session.
10. Screenshot capture is not automatic and is available as a pi-callable tool.
11. pi can call at least one OSPilot desktop tool through a TypeScript extension and local IPC.
12. The system can perform at least one simple requested action, such as moving the mouse or pressing a hotkey.
13. Agent-controlled mouse movement is animated and visually marked with a halo.
14. Screenshots are not stored permanently by default.
15. Logs are written locally without storing full prompts/screenshots by default.

---

## 25. Design Principles

1. **Pi-first orchestration**: pi-coding-agent owns planning, model calls, sessions, and tool decisions.
2. **Cursor-first UX**: OSPilot should feel attached to the user's current focus point.
3. **Menu-bar native**: OSPilot should feel like a small background macOS utility, not a large desktop app.
4. **Screenshot as tool**: visual context is captured only when pi decides to call the screenshot tool.
5. **Visible automation**: mouse movement and clicks should be visually understandable.
6. **Emergency stop always works**: user must be able to abort pi and local actions quickly.
7. **No surprise persistence**: screenshots and full prompts are not stored by default.
8. **Structured tools**: desktop actions are exposed through pi tool schemas and local IPC.
9. **Retina/multi-monitor safe**: coordinate handling must be robust.
10. **Small MVP, expandable architecture**: build the smallest useful pi-backed desktop shell first.
