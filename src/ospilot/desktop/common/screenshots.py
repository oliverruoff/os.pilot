from __future__ import annotations

HD_MAX_WIDTH = 1280
HD_MAX_HEIGHT = 720


def hd_screenshot_size(width: int | float, height: int | float) -> tuple[int, int]:
    """Return a 720p/HD-bounded size preserving aspect ratio.

    The model receives this image, so screenshot pixel coordinates should be
    interpreted relative to this scaled size, not the original capture size.
    """
    source_width = int(width)
    source_height = int(height)
    if source_width <= 0 or source_height <= 0:
        raise ValueError("screenshot dimensions must be positive")

    scale = min(HD_MAX_WIDTH / source_width, HD_MAX_HEIGHT / source_height)
    scaled_width = max(1, round(source_width * scale))
    scaled_height = max(1, round(source_height * scale))
    return scaled_width, scaled_height
