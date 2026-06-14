from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Bounds:
    x: float
    y: float
    width: float
    height: float


def normalize_target(target: dict[str, Any], bounds: Bounds, screenshot_context: dict[str, Any] | None = None) -> tuple[float, float]:
    x = target.get("x")
    y = target.get("y")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        raise ValueError("target requires numeric x and y")
    x_float = float(x)
    y_float = float(y)
    coordinate_space = str(target.get("coordinate_space", "")).strip()
    if coordinate_space == "display_point":
        return x_float, y_float
    if coordinate_space in {"normalized", "relative"}:
        relative_bounds = screenshot_monitor_bounds(screenshot_context) or bounds
        return relative_bounds.x + relative_bounds.width * x_float, relative_bounds.y + relative_bounds.height * y_float
    if coordinate_space == "screenshot_pixel":
        converted = screenshot_pixel_to_display_point(x_float, y_float, screenshot_context)
        if converted is None:
            raise ValueError("screenshot_pixel target requires a recent screenshot context")
        return converted
    if 0 <= x_float <= 1 and 0 <= y_float <= 1:
        relative_bounds = screenshot_monitor_bounds(screenshot_context) or bounds
        return relative_bounds.x + relative_bounds.width * x_float, relative_bounds.y + relative_bounds.height * y_float

    # If the model points at pixel coordinates from the last screenshot, convert
    # them back into logical display coordinates. This matters on Retina/high-DPI
    # and avoids several-centimeter misses when screenshot pixels != display pts.
    converted = screenshot_pixel_to_display_point(x_float, y_float, screenshot_context)
    if converted is not None:
        return converted
    return x_float, y_float


def screenshot_monitor_bounds(screenshot_context: dict[str, Any] | None) -> Bounds | None:
    if not screenshot_context:
        return None
    monitor_bounds = screenshot_context.get("monitor_bounds")
    if not isinstance(monitor_bounds, dict):
        return None
    monitor_x = monitor_bounds.get("x")
    monitor_y = monitor_bounds.get("y")
    monitor_width = monitor_bounds.get("width")
    monitor_height = monitor_bounds.get("height")
    values = (monitor_x, monitor_y, monitor_width, monitor_height)
    if not all(isinstance(value, int | float) for value in values):
        return None
    if float(monitor_width) <= 0 or float(monitor_height) <= 0:
        return None
    return Bounds(float(monitor_x), float(monitor_y), float(monitor_width), float(monitor_height))


def screenshot_pixel_to_display_point(x: float, y: float, screenshot_context: dict[str, Any] | None) -> tuple[float, float] | None:
    if not screenshot_context:
        return None
    screenshot_size = screenshot_context.get("screenshot_size")
    monitor_bounds = screenshot_context.get("monitor_bounds")
    if not isinstance(screenshot_size, dict) or not isinstance(monitor_bounds, dict):
        return None
    screenshot_width = screenshot_size.get("width")
    screenshot_height = screenshot_size.get("height")
    monitor_x = monitor_bounds.get("x")
    monitor_y = monitor_bounds.get("y")
    monitor_width = monitor_bounds.get("width")
    monitor_height = monitor_bounds.get("height")
    values = (screenshot_width, screenshot_height, monitor_x, monitor_y, monitor_width, monitor_height)
    if not all(isinstance(value, int | float) and value > 0 for value in (screenshot_width, screenshot_height, monitor_width, monitor_height)):
        return None
    if not all(isinstance(value, int | float) for value in values):
        return None
    if not (0 <= x <= float(screenshot_width) and 0 <= y <= float(screenshot_height)):
        return None
    return (
        float(monitor_x) + x / float(screenshot_width) * float(monitor_width),
        float(monitor_y) + y / float(screenshot_height) * float(monitor_height),
    )


def clamp_point(x: float, y: float, bounds: Bounds) -> tuple[float, float]:
    return (
        min(max(x, bounds.x), bounds.x + bounds.width),
        min(max(y, bounds.y), bounds.y + bounds.height),
    )


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_human_mouse(t: float) -> float:
    """Human-ish cursor timing: quick launch, gentle landing."""
    t = max(0.0, min(1.0, t))
    return 1 - pow(1 - t, 2.7)


def human_mouse_path(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int,
    *,
    seed: int | None = None,
) -> list[tuple[float, float]]:
    """Generate a slightly curved, non-uniform path between two points.

    The path is deterministic when a seed is supplied, making it testable while
    still giving runtime motion a natural-looking arc and subtle hand jitter.
    """
    if steps <= 0:
        return [end]
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    distance = math.hypot(dx, dy)
    if distance <= 0:
        return [end for _ in range(steps + 1)]

    rng = random.Random(seed)
    nx = -dy / distance
    ny = dx / distance
    bend = min(90.0, max(8.0, distance * 0.08)) * rng.choice((-1, 1))
    c1 = (sx + dx * 0.28 + nx * bend * rng.uniform(0.45, 0.9), sy + dy * 0.28 + ny * bend * rng.uniform(0.45, 0.9))
    c2 = (sx + dx * 0.72 - nx * bend * rng.uniform(0.25, 0.75), sy + dy * 0.72 - ny * bend * rng.uniform(0.25, 0.75))

    points: list[tuple[float, float]] = []
    jitter = min(2.2, distance * 0.006)
    for index in range(steps + 1):
        u = ease_human_mouse(index / steps)
        inv = 1 - u
        x = inv**3 * sx + 3 * inv**2 * u * c1[0] + 3 * inv * u**2 * c2[0] + u**3 * ex
        y = inv**3 * sy + 3 * inv**2 * u * c1[1] + 3 * inv * u**2 * c2[1] + u**3 * ey
        if 0 < index < steps:
            fade = math.sin(math.pi * index / steps)
            x += rng.uniform(-jitter, jitter) * fade
            y += rng.uniform(-jitter, jitter) * fade
        points.append((x, y))
    points[-1] = end
    return points
