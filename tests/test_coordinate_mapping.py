from ospilot.desktop.common.coordinates import Bounds, clamp_point, ease_in_out_cubic, human_mouse_path, normalize_target, screenshot_pixel_to_display_point
from ospilot.desktop.common.screenshots import hd_screenshot_size


def test_normalized_target_maps_to_monitor_bounds() -> None:
    assert normalize_target({"x": 0.5, "y": 0.25}, Bounds(100, 200, 800, 400)) == (500, 300)


def test_absolute_target_passes_through() -> None:
    assert normalize_target({"x": 1200, "y": 640}, Bounds(0, 0, 800, 600)) == (1200, 640)


def test_screenshot_pixel_target_maps_to_display_points() -> None:
    context = {
        "monitor_bounds": {"x": 100, "y": 50, "width": 1000, "height": 500},
        "screenshot_size": {"width": 1000, "height": 500},
        "original_screenshot_size": {"width": 2000, "height": 1000},
    }

    assert screenshot_pixel_to_display_point(500, 250, context) == (600, 300)
    assert normalize_target({"x": 500, "y": 250}, Bounds(100, 50, 1000, 500), context) == (600, 300)


def test_relative_target_uses_screenshot_monitor_bounds() -> None:
    context = {
        "monitor_bounds": {"x": 100, "y": 50, "width": 1000, "height": 500},
        "screenshot_size": {"width": 1000, "height": 500},
    }

    assert normalize_target({"x": 0.5, "y": 0.5, "coordinate_space": "relative"}, Bounds(0, 0, 1, 1), context) == (600, 300)


def test_hd_screenshot_size_fits_common_resolutions() -> None:
    assert hd_screenshot_size(3840, 2160) == (1280, 720)
    assert hd_screenshot_size(2560, 1600) == (1152, 720)
    assert hd_screenshot_size(1920, 1080) == (1280, 720)


def test_clamp_point_limits_to_bounds() -> None:
    assert clamp_point(-10, 900, Bounds(0, 0, 800, 600)) == (0, 600)


def test_easing_endpoints() -> None:
    assert ease_in_out_cubic(0) == 0
    assert ease_in_out_cubic(1) == 1


def test_human_mouse_path_is_curved_and_reaches_target() -> None:
    path = human_mouse_path((0, 0), (100, 0), 20, seed=1)

    assert path[0] == (0, 0)
    assert path[-1] == (100, 0)
    assert any(abs(y) > 0.1 for _, y in path[1:-1])
