import pytest

from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.plot.gui_native import Plot2D


def test_native_plot_creates_distinct_data_marker_handles():
    document = tc_ui_document_create()
    try:
        plot = Plot2D(document)
        line = plot.plot([0.0, 5.0, 10.0], [0.0, 5.0, 10.0])
        first = plot.create_data_marker(5.0, 5.0, "sample", snap_line_index=line)
        second = plot.create_data_marker(10.0, 10.0, "end", snap_line_index=line)
        assert first[0] == second[0] > 0
        assert first != second
        with pytest.raises(RuntimeError, match="rejected data marker"):
            plot.create_data_marker(float("nan"), 5.0, "invalid")
    finally:
        tc_ui_document_destroy(document)
