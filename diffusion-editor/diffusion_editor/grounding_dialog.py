"""Grounding DINO dialog for object detection on the canvas."""

from __future__ import annotations

import threading
import time

import torch
from tcbase import log

from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.label import Label
from tcgui.widgets.slider_edit import SliderEdit
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


GROUNDING_MODELS = [
    ("Tiny (fast, ~340 MB)", "IDEA-Research/grounding-dino-tiny"),
    ("Base (balanced, ~690 MB)", "IDEA-Research/grounding-dino-base"),
]

# Global cache
_model = None
_proc = None
_model_id: str | None = None
_model_device: str | None = None


class GroundingDialog:
    """Modal dialog for running Grounding DINO on the canvas."""

    def __init__(self, editor):
        self._editor = editor
        self._prompt_input: TextInput | None = None
        self._model_combo: ComboBox | None = None
        self._box_threshold_slider: SliderEdit | None = None
        self._text_threshold_slider: SliderEdit | None = None

    def show(self) -> None:
        dlg = Dialog()
        dlg.title = "Detect Objects"
        dlg.buttons = ["OK", "Cancel"]
        dlg.default_button = "OK"
        dlg.cancel_button = "Cancel"
        dlg.min_width = 400

        content = VStack()
        content.spacing = 10

        prompt_label = Label()
        prompt_label.text = "Objects to find"
        content.add_child(prompt_label)

        self._prompt_input = TextInput()
        self._prompt_input.placeholder = "e.g. cat. red cup. face."
        self._prompt_input.preferred_width = px(400)
        content.add_child(self._prompt_input)

        model_label = Label()
        model_label.text = "Model"
        content.add_child(model_label)

        self._model_combo = ComboBox()
        self._model_combo.preferred_width = px(400)
        for label_text, _model_id in GROUNDING_MODELS:
            self._model_combo.add_item(label_text)
        self._model_combo.selected_index = 1
        content.add_child(self._model_combo)

        box_threshold_label = Label()
        box_threshold_label.text = "Box confidence threshold"
        content.add_child(box_threshold_label)

        self._box_threshold_slider = SliderEdit()
        self._box_threshold_slider.min_value = 0.05
        self._box_threshold_slider.max_value = 1.0
        self._box_threshold_slider.value = 0.40
        self._box_threshold_slider.step = 0.05
        self._box_threshold_slider.decimals = 2
        self._box_threshold_slider.preferred_width = px(400)
        content.add_child(self._box_threshold_slider)

        text_threshold_label = Label()
        text_threshold_label.text = "Text token threshold"
        content.add_child(text_threshold_label)

        self._text_threshold_slider = SliderEdit()
        self._text_threshold_slider.min_value = 0.05
        self._text_threshold_slider.max_value = 1.0
        self._text_threshold_slider.value = 0.30
        self._text_threshold_slider.step = 0.05
        self._text_threshold_slider.decimals = 2
        self._text_threshold_slider.preferred_width = px(400)
        content.add_child(self._text_threshold_slider)

        self._gpu_checkbox = Checkbox()
        self._gpu_checkbox.text = "Use GPU"
        self._gpu_checkbox.checked = torch.cuda.is_available()
        self._gpu_checkbox.enabled = torch.cuda.is_available()
        content.add_child(self._gpu_checkbox)

        dlg.content = content
        dlg.on_result = self._on_result
        dlg.show(self._editor.ui)

    def _on_result(self, button: str) -> None:
        if button != "OK" or self._prompt_input is None:
            return

        prompt = self._prompt_input.text.strip()
        if not prompt:
            return
        if not prompt.endswith("."):
            prompt += "."

        box_threshold = (
            self._box_threshold_slider.value if self._box_threshold_slider else 0.40
        )
        text_threshold = (
            self._text_threshold_slider.value if self._text_threshold_slider else 0.30
        )
        model_idx = self._model_combo.selected_index if self._model_combo else 0
        model_id = GROUNDING_MODELS[model_idx][1]
        use_gpu = self._gpu_checkbox.checked

        editor = self._editor
        active = editor._layer_stack.active_layer
        if active is None:
            log.warning("Grounding: no active layer")
            editor._statusbar.text = "Grounding: no active layer"
            return

        try:
            arr = editor._layer_stack.composite()
        except Exception as exc:
            log.error(f"Grounding: failed to get composite — {exc}")
            editor._statusbar.text = "Grounding: failed to get composite"
            return

        log.info(
            f"Grounding start: model={model_id}, prompt='{prompt}', "
            f"box_threshold={box_threshold:.2f}, "
            f"text_threshold={text_threshold:.2f}, gpu={use_gpu}, "
            f"image={arr.shape[1]}x{arr.shape[0]}",
        )

        editor._statusbar.text = "Grounding: detecting..."
        threading.Thread(
            target=_run_grounding_thread,
            args=(
                model_id,
                box_threshold,
                text_threshold,
                prompt,
                arr,
                active,
                use_gpu,
                editor,
            ),
            daemon=True,
        ).start()


def _run_grounding_thread(
    model_id,
    box_threshold,
    text_threshold,
    prompt,
    arr,
    active,
    use_gpu,
    editor,
):
    """Run inference in background; post result to editor for main-thread drawing."""
    t0 = time.time()

    def status(msg):
        editor._statusbar.text = msg

    try:
        model, proc = _get_model(model_id, use_gpu, status_fn=status)
        t1 = time.time()
        log.info(f"Grounding: model ready in {t1 - t0:.1f}s")

        status("Grounding: detecting...")
        boxes = _run_grounding(
            proc, model, arr, prompt, box_threshold, text_threshold, use_gpu
        )
        t2 = time.time()
        log.info(f"Grounding: inference done in {t2 - t1:.1f}s")

    except Exception as e:
        log.error(f"Grounding: {e}")
        editor._statusbar.text = f"Grounding error: {e}"
        return

    if not boxes:
        log.info(f"Grounding: nothing found for prompt='{prompt}'")
        editor._statusbar.text = "Grounding: nothing found"
        return

    editor._pending_grounding_result = (boxes, active)
    found = ", ".join(f"{l} ({s:.0%})" for l, _, _, _, _, s in boxes)
    log.info(f"Grounding: {len(boxes)} hit(s) — {found} (total {t2 - t0:.1f}s)")
    editor._statusbar.text = (
        f"Grounding: {len(boxes)} hit(s): {found}"
    )


def _get_model(model_id: str, use_gpu: bool, status_fn=None):
    global _model, _proc, _model_id, _model_device

    device = "cuda" if use_gpu else "cpu"
    log.info(f"Grounding: loading model={model_id}, device={device}")

    if _model is not None and model_id != _model_id:
        log.info(f"Grounding: model changed {_model_id} -> {model_id}, resetting cache")
        _model = None
        _proc = None
        _model_device = None

    if _model is None:
        from transformers import (
            GroundingDinoForObjectDetection,
            GroundingDinoProcessor,
        )
        from huggingface_hub import try_to_load_from_cache

        t_load = time.time()
        cached = try_to_load_from_cache(model_id, "model.safetensors") is not None
        log.info(
            f"Grounding: cache check for {model_id} -> cached={cached} "
            f"({time.time() - t_load:.1f}s)")

        if status_fn:
            short_name = model_id.split("/")[-1]
            if cached:
                status_fn(f"Loading {short_name} from cache...")
            else:
                status_fn(f"Downloading {short_name} (this may take a few minutes)...")

        _proc = GroundingDinoProcessor.from_pretrained(
            model_id, local_files_only=cached)
        _model = GroundingDinoForObjectDetection.from_pretrained(
            model_id, local_files_only=cached)
        _model_id = model_id
        _model_device = None
        log.info(f"Grounding: model loaded in {time.time() - t_load:.1f}s")

    if _model_device != device:
        t_move = time.time()
        _model.to(device)
        _model.eval()
        log.info(f"Grounding: moved model to {device} in {time.time() - t_move:.1f}s")
        _model_device = device

    return _model, _proc


def _run_grounding(
    processor,
    model,
    image_array,
    prompt: str,
    box_threshold: float,
    text_threshold: float,
    use_gpu: bool,
):
    import numpy as np
    from PIL import Image

    device = "cuda" if use_gpu else "cpu"

    if isinstance(image_array, np.ndarray):
        image = Image.fromarray(image_array, "RGBA").convert("RGB")
    else:
        image = image_array

    log.info(
        f"Grounding: running inference, image={image.width}x{image.height}, "
        f"prompt='{prompt}', box_threshold={box_threshold:.2f}, "
        f"text_threshold={text_threshold:.2f}, device={device}")

    t_prep = time.time()
    inputs = processor(images=image, text=prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    log.info(f"Grounding: inputs prepared in {time.time() - t_prep:.1f}s")

    t_infer = time.time()
    with torch.no_grad():
        outputs = model(**inputs)
    log.info(f"Grounding: model forward pass in {time.time() - t_infer:.1f}s")

    h, w = image.height, image.width
    results = processor.post_process_grounded_object_detection(
        outputs,
        input_ids=inputs.get("input_ids"),
        threshold=box_threshold,
        text_threshold=text_threshold,
        target_sizes=[(h, w)],
    )

    boxes = []
    for result in results:
        for score, box, label in zip(
            result["scores"].tolist(),
            result["boxes"].tolist(),
            result["labels"],
        ):
            x0, y0, x1, y1 = [int(v) for v in box]
            boxes.append((label, x0, y0, x1, y1, score))
            log.info(
                f"Grounding: detected '{label}' box=({x0},{y0},{x1},{y1}) "
                f"score={score:.3f}")

    boxes.sort(key=lambda b: b[5], reverse=True)
    log.info(f"Grounding: post-processing done, {len(boxes)} boxes found")
    return boxes
