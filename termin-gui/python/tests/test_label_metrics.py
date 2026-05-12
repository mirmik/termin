from tcgui.widgets.label import Label


class LabelRenderer:
    def __init__(self):
        self.drawn_text: tuple[float, float, str, float] | None = None
        self.clip_rect: tuple[float, float, float, float] | None = None
        self.clip_closed = False

    def line_height_at(self, font_size: float) -> float:
        return font_size

    def ascent_at(self, font_size: float) -> float:
        return font_size * 0.8

    def measure_text(self, text: str, font_size: float) -> tuple[float, float]:
        return (len(text) * font_size * 0.5, font_size)

    def begin_clip(self, x: float, y: float, w: float, h: float) -> None:
        self.clip_rect = (x, y, w, h)

    def end_clip(self) -> None:
        self.clip_closed = True

    def draw_text(
        self,
        x: float,
        y: float,
        text: str,
        color: tuple[float, float, float, float],
        font_size: float,
    ) -> None:
        self.drawn_text = (x, y, text, font_size)

    def draw_text_centered(self, *args, **kwargs) -> None:
        raise AssertionError("left-aligned label must not draw centered text")


def test_label_uses_font_ascent_for_baseline():
    label = Label()
    label.text = "gypqj"
    label.font_size = 40
    label.layout(10, 20, 200, 48, 800, 600)

    renderer = LabelRenderer()
    label.render(renderer)

    assert renderer.clip_rect == (10, 20, 200, 48)
    assert renderer.clip_closed
    assert renderer.drawn_text == (10, 56.0, "gypqj", 40)
