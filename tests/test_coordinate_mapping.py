from ospilot.tools.coordinates import Bounds, clamp_point, ease_in_out_cubic, human_mouse_path, normalize_target, screenshot_pixel_to_display_point


def test_normalized_target_maps_to_monitor_bounds() -> None:
    assert normalize_target({"x": 0.5, "y": 0.25}, Bounds(100, 200, 800, 400)) == (500, 300)


def test_absolute_target_passes_through() -> None:
    assert normalize_target({"x": 1200, "y": 640}, Bounds(0, 0, 800, 600)) == (1200, 640)


def test_screenshot_pixel_target_maps_to_display_points() -> None:
    context = {
        "monitor_bounds": {"x": 100, "y": 50, "width": 1000, "height": 500},
        "screenshot_size": {"width": 2000, "height": 1000},
    }

    assert screenshot_pixel_to_display_point(1000, 500, context) == (600, 300)
    assert normalize_target({"x": 1000, "y": 500}, Bounds(100, 50, 1000, 500), context) == (600, 300)


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
