from tcgui.widgets.file_dialog_overlay import parse_filter_string


def test_parse_filter_string_empty():
    assert parse_filter_string("") == [("All files", "*.*")]


def test_parse_filter_string_with_labels_and_patterns():
    got = parse_filter_string("Images | *.png *.jpg;;Project | *.deproj")
    assert got == [
        ("Images", "*.png *.jpg"),
        ("Project", "*.deproj"),
    ]


def test_parse_filter_string_without_pipe_uses_default_pattern():
    got = parse_filter_string("Text files")
    assert got == [("Text files", "*.*")]


def test_parse_filter_string_ignores_empty_parts():
    got = parse_filter_string(";;Images | *.png;;")
    assert got == [("Images", "*.png")]
