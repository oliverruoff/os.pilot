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
  if (name === "ospilot_capture_screenshot_current_mouse_monitor" && result?.ok && typeof result.screenshot_path === "string") {
    const data = await readFile(result.screenshot_path, { encoding: "base64" });
    content.push({ type: "image", data, mimeType: typeof result.screenshot_mime_type === "string" ? result.screenshot_mime_type : "image/png" });
  }
  return { content, details: result };
}

const commonProperties = {
  target: {
    type: "object" as const,
    description: "Target coordinates. Prefer normalized coordinates {x: 0.5, y: 0.5} relative to the screenshot/monitor. You may also pass screenshot pixel coordinates from the latest screenshot; OSPilot converts them to display coordinates precisely.",
    properties: {
      x: { type: "number" as const, description: "X coordinate. Use 0-1 normalized relative to the monitor, an Accessibility display point, or a pixel coordinate from the latest screenshot." },
      y: { type: "number" as const, description: "Y coordinate. Use 0-1 normalized relative to the monitor, an Accessibility display point, or a pixel coordinate from the latest screenshot." },
      coordinate_space: { type: "string" as const, enum: ["normalized", "display_point", "screenshot_pixel"] as const, description: "Optional coordinate type. Use display_point for Accessibility centers; use screenshot_pixel for pixel coordinates from the latest screenshot; omit for normalized 0-1 coordinates." },
    },
    required: ["x", "y"] as const,
  },
};

const tools = [
  {
    name: "ospilot_get_active_context",
    description: "Read current desktop context including mouse position and active app.",
    parameters: { type: "object" as const, properties: {} },
  },
  {
    name: "ospilot_get_frontmost_ui_elements",
    description: "Fast precise UI element lookup for the frontmost macOS app using Accessibility. Use this before screenshots when the user asks where a named UI control/setting/button is, or before clicking a named control. Pass a short query like \"battery\", \"settings\", \"search\". Returns element labels, roles, bounds, and exact center coordinates in screen points for ospilot_move_mouse or ospilot_click.",
    parameters: {
      type: "object" as const,
      properties: {
        query: { type: "string" as const, description: "Optional text to find in UI labels/descriptions/values, e.g. 'battery' or 'settings'." },
        limit: { type: "integer" as const, description: "Maximum number of elements to return. Defaults to 120." },
      },
    },
  },
  {
    name: "ospilot_capture_screenshot_current_mouse_monitor",
    description: "Capture and view what the user is currently looking at: the monitor containing the current mouse position. Returns a compressed screenshot image plus metadata (mouse position, monitor bounds, scale). Use after ospilot_get_frontmost_ui_elements when Accessibility cannot identify the requested visual target, or for purely visual items not exposed as UI elements.",
    parameters: { type: "object" as const, properties: {} },
  },
  {
    name: "ospilot_show_companion_message",
    description: "Show a short message in OSPilot companion UI.",
    parameters: {
      type: "object" as const,
      properties: {
        text: { type: "string" as const, description: "Message text to display." },
      },
      required: ["text"],
    },
  },
  {
    name: "ospilot_move_mouse",
    description: "Visual pointer tool. Move the mouse to target coordinates to point out or highlight something on screen. For named UI controls, first use ospilot_get_frontmost_ui_elements and pass the returned exact center coordinates. For visual-only targets, use a screenshot and choose the exact center of the requested item. Do not click unless the user explicitly asks to click.",
    parameters: {
      type: "object" as const,
      properties: {
        target: commonProperties.target,
        duration_ms: { type: "integer" as const, description: "Optional movement duration in milliseconds. Defaults to auto-calculated based on distance; keep visible enough for pointing/highlighting." },
      },
      required: ["target"],
    },
  },
  {
    name: "ospilot_press_hotkey",
    description: "Press a keyboard shortcut. Example: {keys: [\"command\", \"c\"]} for Cmd+C.",
    parameters: {
      type: "object" as const,
      properties: {
        keys: { type: "array" as const, items: { type: "string" as const }, description: "Array of key names to press simultaneously." },
      },
      required: ["keys"],
    },
  },
  {
    name: "ospilot_read_clipboard",
    description: "Read clipboard text.",
    parameters: { type: "object" as const, properties: {} },
  },
  {
    name: "ospilot_write_clipboard",
    description: "Write clipboard text.",
    parameters: {
      type: "object" as const,
      properties: {
        text: { type: "string" as const, description: "Text to write to clipboard." },
      },
      required: ["text"],
    },
  },
  {
    name: "ospilot_click",
    description: "Click at current pointer position or move to target first. For named UI controls, first use ospilot_get_frontmost_ui_elements and pass the returned exact center coordinates. Use without target to click at current position.",
    parameters: {
      type: "object" as const,
      properties: {
        target: {
          ...commonProperties.target,
          description: "Optional target coordinates. If omitted, clicks at current mouse position.",
        },
      },
    },
  },
  {
    name: "ospilot_right_click",
    description: "Right-click at current pointer position or move to target first. Use without target to right-click at current position.",
    parameters: {
      type: "object" as const,
      properties: {
        target: {
          ...commonProperties.target,
          description: "Optional target coordinates. If omitted, right-clicks at current mouse position.",
        },
      },
    },
  },
  {
    name: "ospilot_double_click",
    description: "Double click at current pointer position or move to target first. Use without target to double-click at current position.",
    parameters: {
      type: "object" as const,
      properties: {
        target: {
          ...commonProperties.target,
          description: "Optional target coordinates. If omitted, double-clicks at current mouse position.",
        },
      },
    },
  },
  {
    name: "ospilot_type_text",
    description: "Type text into the focused UI element.",
    parameters: {
      type: "object" as const,
      properties: {
        text: { type: "string" as const, description: "Text to type." },
      },
      required: ["text"],
    },
  },
  {
    name: "ospilot_open_app",
    description: "Open a macOS app by name. Example: {app_name: \"Safari\"}",
    parameters: {
      type: "object" as const,
      properties: {
        app_name: { type: "string" as const, description: "Name of the macOS application to open." },
      },
      required: ["app_name"],
    },
  },
] as const;

export default function (pi: any) {
  for (const tool of tools) {
    pi.registerTool({
      name: tool.name,
      label: tool.name.replace(/^ospilot_/, "OSPilot ").replaceAll("_", " "),
      description: tool.description,
      parameters: tool.parameters,
      async execute(_toolCallId: string, payload: ToolPayload) {
        const result = await callOSPilot(tool.name, payload);
        return await toToolResult(tool.name, result);
      },
    });
  }
}
