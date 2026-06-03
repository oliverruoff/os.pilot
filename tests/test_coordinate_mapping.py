from ospilot.tools.coordinates import Bounds, clamp_point, ease_in_out_cubic, normalize_target


def test_normalized_target_maps_to_monitor_bounds() -> None:
    assert normalize_target({"x": 0.5, "y": 0.25}, Bounds(100, 200, 800, 400)) == (500, 300)


def test_absolute_target_passes_through() -> None:
    assert normalize_target({"x": 1200, "y": 640}, Bounds(0, 0, 800, 600)) == (1200, 640)


def test_clamp_point_limits_to_bounds() -> None:
    assert clamp_point(-10, 900, Bounds(0, 0, 800, 600)) == (0, 600)


def test_easing_endpoints() -> None:
    assert ease_in_out_cubic(0) == 0
    assert ease_in_out_cubic(1) == 1
