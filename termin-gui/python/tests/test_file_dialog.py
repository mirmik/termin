from tcgui.widgets.file_dialog_overlay import parse_filter_string


def test_parse_filter_string_cases():
    cases = [
        ("", [("All files", "*.*")]),
        (
            "Images | *.png *.jpg;;Project | *.deproj",
            [("Images", "*.png *.jpg"), ("Project", "*.deproj")],
        ),
        ("Text files", [("Text files", "*.*")]),
        (";;Images | *.png;;", [("Images", "*.png")]),
    ]

    for source, expected in cases:
        assert parse_filter_string(source) == expected
