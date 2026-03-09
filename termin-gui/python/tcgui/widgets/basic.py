"""Basic widgets — re-export hub for backward compatibility."""

from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.icon_button import IconButton
from tcgui.widgets.separator import Separator
from tcgui.widgets.image_widget import ImageWidget
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.progress_bar import ProgressBar
from tcgui.widgets.slider import Slider
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.slider_edit import SliderEdit
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.frame_time_graph import FrameTimeGraph

__all__ = [
    "Label", "Button", "Checkbox", "IconButton", "Separator",
    "ImageWidget", "TextInput", "ListWidget", "ProgressBar",
    "Slider", "ComboBox", "SpinBox", "SliderEdit", "TextArea",
    "FrameTimeGraph",
]
