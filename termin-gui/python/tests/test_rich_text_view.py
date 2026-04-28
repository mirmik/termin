from tcgui.widgets.rich_text_view import RichTextView


def test_set_html_preserves_lines_and_plain_text():
    view = RichTextView()

    view.set_html("<pre>A<br>B</pre>")

    assert view.text == "A\nB"


def test_set_html_reads_span_color_and_bold():
    view = RichTextView()

    view.set_html("<span style='color: #50fa7b; font-weight: bold;'>Writer</span>")

    segment = view.lines[0][0]
    assert segment.text == "Writer"
    assert segment.style.bold is True
    assert segment.style.color == (80 / 255.0, 250 / 255.0, 123 / 255.0, 1.0)


def test_set_text_replaces_rich_lines():
    view = RichTextView()
    view.set_html("<b>A</b>")

    view.text = "plain\ntext"

    assert view.text == "plain\ntext"
    assert view.lines[0][0].style.bold is False
