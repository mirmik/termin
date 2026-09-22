import numpy as np
import pytest

from termin.plot import PlotAxis3D, RetainedChart3D, SrgbColor


def test_retained_chart3d_accepts_series_before_gpu_attachment():
    plot = RetainedChart3D()

    line = plot.add_line(
        np.array([0.0, 1.0, 2.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.5, 1.0]),
    )
    scatter = plot.add_scatter(
        np.array([0.0, 1.0]),
        np.array([1.0, 0.0]),
        np.array([0.25, 0.75]),
    )
    surface = plot.add_surface(
        np.array([0.0, 1.0, 0.0, 1.0]),
        np.array([0.0, 0.0, 1.0, 1.0]),
        np.array([0.0, 0.5, 1.0, 0.25]),
        2,
        2,
    )

    assert line.scene_id == scatter.scene_id == surface.scene_id
    assert plot.set_surface_grid(
        surface,
        True,
        8,
        8,
        SrgbColor(0.05, 0.05, 0.05, 1.0),
    )
    plot.set_colorbar(surface, "height")
    plot.clear_colorbar()
    assert plot.destroy_item(line)
    assert plot.destroy_item(scatter)
    assert plot.destroy_item(surface)


def test_axis_display_bindings_validate_and_keep_independent_offsets():
    plot = RetainedChart3D()
    for axis in (PlotAxis3D.X, PlotAxis3D.Y, PlotAxis3D.Z):
        assert plot.get_axis_display_offset(axis) == 0
    plot.set_axis_display_offset(PlotAxis3D.X, 100)
    plot.set_axis_display_offset(PlotAxis3D.Z, -40)
    assert plot.get_axis_display_offset(PlotAxis3D.X) == 100
    assert plot.get_axis_display_offset(PlotAxis3D.Y) == 0
    assert plot.get_axis_display_offset(PlotAxis3D.Z) == -40
    plot.set_axis_tick_label(PlotAxis3D.Z, 0, "≤ −40 dBsm")
    plot.set_axis_tick_label(PlotAxis3D.Z, 0, None)
    plot.clear_axis_tick_labels(PlotAxis3D.Z)
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(RuntimeError):
            plot.set_axis_display_offset(PlotAxis3D.Z, value)
        with pytest.raises(RuntimeError):
            plot.set_axis_tick_label(PlotAxis3D.Z, value, "invalid")
    with pytest.raises(RuntimeError):
        plot.set_axis_display_offset(PlotAxis3D.Radius, -40)
    assert plot.get_axis_display_offset(PlotAxis3D.Z) == -40
