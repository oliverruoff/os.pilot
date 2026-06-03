import { readFile } from "node:fs/promises";

type ToolPayload = Record<string, unknown>;

const endpoint = process.env.OSPILOT_IPC_URL;
const token = process.env.OSPILOT_IPC_TOKEN;

async function callOSPilot(tool: string, payload: ToolPayload = {}) {
  if (!endpoint || !token) throw new Error("OSPilot IPC environment is not configured");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`${endpoint}/tool`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ tool, payload }),
    });
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

async function toToolResult(name: string, result: any) {
  const content: any[] = [{ type: "text", text: JSON.stringify(result) }];
  return { content, details: result };
}

const tools = [
  ["ospilot_get_active_context", "Read current desktop context."],
  ["ospilot_capture_screenshot_current_mouse_monitor", "Capture only the monitor containing the mouse cursor."],
  ["ospilot_show_companion_message", "Show a short message in OSPilot companion UI."],
  ["ospilot_move_mouse", "Move mouse smoothly to normalized or screen coordinates."],
  ["ospilot_press_hotkey", "Press a keyboard shortcut."],
  ["ospilot_read_clipboard", "Read clipboard text."],
  ["ospilot_write_clipboard", "Write clipboard text."],
  ["ospilot_run_shell_command", "Run a local shell command."],
  ["ospilot_click", "Click at current pointer or target."],
  ["ospilot_double_click", "Double click at current pointer or target."],
  ["ospilot_type_text", "Type text into the focused UI."],
  ["ospilot_open_app", "Open a macOS app by name."],
] as const;

export default function (pi: any) {
  for (const [name, description] of tools) {
    pi.registerTool({
      name,
      label: name.replace(/^ospilot_/, "OSPilot ").replaceAll("_", " "),
      description,
      parameters: { type: "object", additionalProperties: true },
      async execute(_toolCallId: string, payload: ToolPayload) {
        const result = await callOSPilot(name, payload);
        return await toToolResult(name, result);
      },
    });
  }
}
