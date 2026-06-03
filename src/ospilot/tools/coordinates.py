from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Bounds:
    x: float
    y: float
    width: float
    height: float


def normalize_target(target: dict[str, Any], bounds: Bounds) -> tuple[float, float]:
    x = target.get("x")
    y = target.get("y")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        raise ValueError("target requires numeric x and y")
    if 0 <= x <= 1 and 0 <= y <= 1:
        return bounds.x + bounds.width * float(x), bounds.y + bounds.height * float(y)
    return float(x), float(y)


def clamp_point(x: float, y: float, bounds: Bounds) -> tuple[float, float]:
    return (
        min(max(x, bounds.x), bounds.x + bounds.width),
        min(max(y, bounds.y), bounds.y + bounds.height),
    )


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2
