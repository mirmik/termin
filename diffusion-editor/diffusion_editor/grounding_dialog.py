"""Grounding DINO + SAM 2.1 dialog for object detection and segmentation."""

from __future__ import annotations

import threading
import time

import numpy as np
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

SAM2_MODELS = [
    ("Tiny (fast, ~82 MB)", "facebook/sam2.1-hiera-tiny"),
    ("Small (balanced, ~184 MB)", "facebook/sam2.1-hiera-small"),
    ("Base+ (accurate, ~322 MB)", "facebook/sam2.1-hiera-base-plus"),
]

# Global cache — DINO
_dino_model = None
_dino_proc = None
_dino_model_id: str | None = None
_dino_device: str | None = None

# Global cache — SAM 2.1
_sam2_model = None
_sam2_proc = None
_sam2_model_id: str | None = None
_sam2_device: str | None = None


class GroundingDialog:
    """Modal dialog for running Grounding DINO + SAM 2.1 on the canvas."""

    def __init__(self, editor):
        self._editor = editor
        self._prompt_input: TextInput | None = None
        self._model_combo: ComboBox | None = None
        self._box_threshold_slider: SliderEdit | None = None
        self._text_threshold_slider: SliderEdit | None = None
        self._sam2_combo: ComboBox | None = None
        self._sam2_checkbox: Checkbox | None = None
        self._sam2_mask_combo: ComboBox | None = None
        self._mask_threshold_slider: SliderEdit | None = None
        self._max_hole_slider: SliderEdit | None = None
        self._max_sprinkle_slider: SliderEdit | None = None
        self._multimask_checkbox: Checkbox | None = None
        self._non_overlap_checkbox: Checkbox | None = None

    def show(self) -> None:
        dlg = Dialog()
        dlg.title = "Detect Objects"
        dlg.buttons = ["OK", "Cancel"]
        dlg.default_button = "OK"
        dlg.cancel_button = "Cancel"
        dlg.min_width = 400

        content = VStack()
        content.spacing = 10

        # ── Grounding DINO ──────────────────────────────────────────────

        prompt_label = Label()
        prompt_label.text = "Objects to find"
        content.add_child(prompt_label)

        self._prompt_input = TextInput()
        self._prompt_input.placeholder = "e.g. cat. red cup. face."
        self._prompt_input.preferred_width = px(400)
        content.add_child(self._prompt_input)

        model_label = Label()
        model_label.text = "Grounding DINO model"
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
        self._box_threshold_slider.tooltip = "Minimum confidence for object detection boxes"
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
        self._text_threshold_slider.tooltip = "Minimum confidence for text-to-box matching"
        self._text_threshold_slider.min_value = 0.05
        self._text_threshold_slider.max_value = 1.0
        self._text_threshold_slider.value = 0.30
        self._text_threshold_slider.step = 0.05
        self._text_threshold_slider.decimals = 2
        self._text_threshold_slider.preferred_width = px(400)
        content.add_child(self._text_threshold_slider)

        # ── SAM 2.1 ─────────────────────────────────────────────────────

        sam2_label = Label()
        sam2_label.text = "SAM 2.1 segmentation (experimental)"
        content.add_child(sam2_label)

        self._sam2_checkbox = Checkbox()
        self._sam2_checkbox.text = "Segment with SAM 2.1"
        self._sam2_checkbox.checked = True
        content.add_child(self._sam2_checkbox)

        self._sam2_combo = ComboBox()
        self._sam2_combo.preferred_width = px(400)
        for label_text, _model_id in SAM2_MODELS:
            self._sam2_combo.add_item(label_text)
        self._sam2_combo.selected_index = 0  # Tiny default
        content.add_child(self._sam2_combo)

        self._sam2_mask_combo = ComboBox()
        self._sam2_mask_combo.preferred_width = px(400)
        self._sam2_mask_combo.add_item("whole (full object)")
        self._sam2_mask_combo.add_item("part")
        self._sam2_mask_combo.add_item("subpart")
        self._sam2_mask_combo.selected_index = 0
        content.add_child(self._sam2_mask_combo)

        # ── SAM 2.1 options ─────────────────────────────────────────────

        mask_thresh_label = Label()
        mask_thresh_label.text = "Mask threshold (higher = tighter)"
        content.add_child(mask_thresh_label)

        self._mask_threshold_slider = SliderEdit()
        self._mask_threshold_slider.tooltip = "Higher values produce tighter masks around object edges"
        self._mask_threshold_slider.min_value = 0.0
        self._mask_threshold_slider.max_value = 1.0
        self._mask_threshold_slider.value = 0.0
        self._mask_threshold_slider.step = 0.05
        self._mask_threshold_slider.decimals = 2
        self._mask_threshold_slider.preferred_width = px(400)
        content.add_child(self._mask_threshold_slider)

        max_hole_label = Label()
        max_hole_label.text = "Max hole area (0 = off, px)"
        content.add_child(max_hole_label)

        self._max_hole_slider = SliderEdit()
        self._max_hole_slider.tooltip = "Fill holes smaller than this area in pixels (0 = disabled)"
        self._max_hole_slider.min_value = 0
        self._max_hole_slider.max_value = 10000
        self._max_hole_slider.value = 0
        self._max_hole_slider.step = 100
        self._max_hole_slider.decimals = 0
        self._max_hole_slider.preferred_width = px(400)
        content.add_child(self._max_hole_slider)

        max_sprinkle_label = Label()
        max_sprinkle_label.text = "Max sprinkle area (0 = off, px)"
        content.add_child(max_sprinkle_label)

        self._max_sprinkle_slider = SliderEdit()
        self._max_sprinkle_slider.tooltip = "Remove isolated pixels smaller than this area (0 = disabled)"
        self._max_sprinkle_slider.min_value = 0
        self._max_sprinkle_slider.max_value = 10000
        self._max_sprinkle_slider.value = 0
        self._max_sprinkle_slider.step = 100
        self._max_sprinkle_slider.decimals = 0
        self._max_sprinkle_slider.preferred_width = px(400)
        content.add_child(self._max_sprinkle_slider)

        self._multimask_checkbox = Checkbox()
        self._multimask_checkbox.text = "Multimask output (3 candidates per box)"
        self._multimask_checkbox.checked = True
        content.add_child(self._multimask_checkbox)

        self._non_overlap_checkbox = Checkbox()
        self._non_overlap_checkbox.text = "Non-overlapping masks"
        self._non_overlap_checkbox.checked = False
        content.add_child(self._non_overlap_checkbox)

        # ── GPU ─────────────────────────────────────────────────────────

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

        use_sam2 = self._sam2_checkbox.checked if self._sam2_checkbox else False
        sam2_idx = self._sam2_combo.selected_index if self._sam2_combo else 0
        sam2_id = SAM2_MODELS[sam2_idx][1] if use_sam2 else None
        sam2_mask_channel = (
            self._sam2_mask_combo.selected_index if self._sam2_mask_combo else 0
        )

        mask_threshold = (
            self._mask_threshold_slider.value if self._mask_threshold_slider else 0.0
        )
        max_hole_area = (
            int(self._max_hole_slider.value) if self._max_hole_slider else 0
        )
        max_sprinkle_area = (
            int(self._max_sprinkle_slider.value) if self._max_sprinkle_slider else 0
        )
        multimask = (
            self._multimask_checkbox.checked if self._multimask_checkbox else True
        )
        non_overlap = (
            self._non_overlap_checkbox.checked if self._non_overlap_checkbox else False
        )

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
            f"text_threshold={text_threshold:.2f}, "
            f"sam2={sam2_id}, mask_channel={sam2_mask_channel}, gpu={use_gpu}, "
            f"mask_threshold={mask_threshold:.2f}, max_hole={max_hole_area}, "
            f"max_sprinkle={max_sprinkle_area}, multimask={multimask}, "
            f"non_overlap={non_overlap}, "
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
                sam2_id,
                sam2_mask_channel,
                mask_threshold,
                max_hole_area,
                max_sprinkle_area,
                multimask,
                non_overlap,
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
    sam2_id,
    sam2_mask_channel,
    mask_threshold,
    max_hole_area,
    max_sprinkle_area,
    multimask,
    non_overlap,
    editor,
):
    """Run DINO then SAM; post result to editor."""
    t0 = time.time()

    def status(msg):
        editor._statusbar.text = msg

    try:
        model, proc = _get_dino_model(model_id, use_gpu, status_fn=status)
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

    # ── SAM 2.1 ─────────────────────────────────────────────────────────
    masks = [None] * len(boxes)
    if sam2_id:
        try:
            status("SAM 2.1: segmenting...")
            sam_model, sam_proc = _get_sam2_model(sam2_id, use_gpu, status_fn=status)
            t_sam0 = time.time()
            masks = _run_sam2(
                sam_proc, sam_model, arr, boxes, sam2_mask_channel,
                mask_threshold, max_hole_area, max_sprinkle_area,
                multimask, non_overlap, use_gpu,
            )
            t_sam1 = time.time()
            log.info(f"SAM 2.1: {sum(1 for m in masks if m is not None)} masks "
                     f"in {t_sam1 - t_sam0:.1f}s")
        except Exception as e:
            log.error(f"SAM 2.1: {e}")
            editor._statusbar.text = f"SAM 2.1 error: {e}"

    results = [
        (label, x0, y0, x1, y1, score, mask)
        for (label, x0, y0, x1, y1, score), mask in zip(boxes, masks)
    ]
    editor._pending_grounding_result = (results, active)

    found = ", ".join(f"{l} ({s:.0%})" for l, _, _, _, _, s, _ in results)
    log.info(f"Grounding: {len(results)} hit(s) — {found} (total {time.time() - t0:.1f}s)")
    editor._statusbar.text = (
        f"Grounding: {len(results)} hit(s): {found}"
    )


# ── DINO model ──────────────────────────────────────────────────────────


def _get_dino_model(model_id: str, use_gpu: bool, status_fn=None):
    global _dino_model, _dino_proc, _dino_model_id, _dino_device

    device = "cuda" if use_gpu else "cpu"
    log.info(f"Grounding: loading DINO model={model_id}, device={device}")

    if _dino_model is not None and model_id != _dino_model_id:
        log.info(f"Grounding: DINO model changed {_dino_model_id} -> {model_id}, resetting cache")
        _dino_model = None
        _dino_proc = None
        _dino_device = None

    if _dino_model is None:
        from transformers import (
            GroundingDinoForObjectDetection,
            GroundingDinoProcessor,
        )
        from huggingface_hub import try_to_load_from_cache

        t_load = time.time()
        cached = try_to_load_from_cache(model_id, "model.safetensors") is not None
        log.info(
            f"Grounding: DINO cache check for {model_id} -> cached={cached} "
            f"({time.time() - t_load:.1f}s)")

        if status_fn:
            short_name = model_id.split("/")[-1]
            if cached:
                status_fn(f"Loading {short_name} from cache...")
            else:
                status_fn(f"Downloading {short_name} (this may take a few minutes)...")

        _dino_proc = GroundingDinoProcessor.from_pretrained(
            model_id, local_files_only=cached)
        _dino_model = GroundingDinoForObjectDetection.from_pretrained(
            model_id, local_files_only=cached)
        _dino_model_id = model_id
        _dino_device = None
        log.info(f"Grounding: DINO model loaded in {time.time() - t_load:.1f}s")

    if _dino_device != device:
        t_move = time.time()
        _dino_model.to(device)
        _dino_model.eval()
        log.info(f"Grounding: moved DINO model to {device} in {time.time() - t_move:.1f}s")
        _dino_device = device

    return _dino_model, _dino_proc


def _run_grounding(
    processor,
    model,
    image_array,
    prompt: str,
    box_threshold: float,
    text_threshold: float,
    use_gpu: bool,
):
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


# ── SAM 2.1 model ───────────────────────────────────────────────────────


def _get_sam2_model(model_id: str, use_gpu: bool, status_fn=None):
    global _sam2_model, _sam2_proc, _sam2_model_id, _sam2_device

    device = "cuda" if use_gpu else "cpu"
    log.info(f"SAM 2.1: loading model={model_id}, device={device}")

    if _sam2_model is not None and model_id != _sam2_model_id:
        log.info(f"SAM 2.1: model changed {_sam2_model_id} -> {model_id}, resetting cache")
        _sam2_model = None
        _sam2_proc = None
        _sam2_device = None

    if _sam2_model is None:
        from transformers import Sam2Processor, Sam2Model
        from huggingface_hub import try_to_load_from_cache

        t_load = time.time()
        cached = try_to_load_from_cache(model_id, "model.safetensors") is not None
        log.info(
            f"SAM 2.1: cache check for {model_id} -> cached={cached} "
            f"({time.time() - t_load:.1f}s)")

        if status_fn:
            short_name = model_id.split("/")[-1]
            if cached:
                status_fn(f"Loading {short_name} from cache...")
            else:
                status_fn(f"Downloading {short_name} (this may take a few minutes)...")

        _sam2_proc = Sam2Processor.from_pretrained(
            model_id, local_files_only=cached)
        _sam2_model = Sam2Model.from_pretrained(
            model_id, local_files_only=cached)
        _sam2_model_id = model_id
        _sam2_device = None
        log.info(f"SAM 2.1: model loaded in {time.time() - t_load:.1f}s")

    if _sam2_device != device:
        t_move = time.time()
        _sam2_model.to(device)
        _sam2_model.eval()
        log.info(f"SAM 2.1: moved model to {device} in {time.time() - t_move:.1f}s")
        _sam2_device = device

    return _sam2_model, _sam2_proc


def _run_sam2(
    processor, model, image_array, boxes, mask_channel,
    mask_threshold, max_hole_area, max_sprinkle_area,
    multimask, non_overlap, use_gpu,
):
    """Run SAM 2.1 for each box; return list of mask arrays (or None)."""
    from PIL import Image

    device = "cuda" if use_gpu else "cpu"

    if isinstance(image_array, np.ndarray):
        image = Image.fromarray(image_array, "RGBA").convert("RGB")
    else:
        image = image_array

    h, w = image.height, image.width
    masks = []

    # Prepare input boxes for all detections at once
    input_boxes = [[[x0, y0, x1, y1] for _, x0, y0, x1, y1, _ in boxes]]

    t_prep = time.time()
    inputs = processor(
        images=image,
        input_boxes=input_boxes,
        return_tensors="pt",
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    log.info(f"SAM 2.1: inputs prepared in {time.time() - t_prep:.1f}s "
             f"({len(boxes)} boxes)")

    t_infer = time.time()
    with torch.no_grad():
        outputs = model(**inputs, multimask_output=multimask)
    log.info(f"SAM 2.1: forward pass in {time.time() - t_infer:.1f}s")

    # Post-process masks back to original image size
    masks_tensor = processor.post_process_masks(
        outputs.pred_masks,
        original_sizes=[(h, w)],
        mask_threshold=mask_threshold,
        max_hole_area=max_hole_area,
        max_sprinkle_area=max_sprinkle_area,
        apply_non_overlapping_constraints=non_overlap,
        binarize=True,
    )
    # post_process_masks returns list[Tensor], one per image
    masks_tensor = masks_tensor[0]

    for i in range(len(boxes)):
        m = masks_tensor[i]
        if multimask and m.dim() > 2:
            m = m[mask_channel]  # multimask channel: 0=whole, 1=part, 2=subpart
        mask = m.cpu().numpy().astype(bool)
        masks.append(mask)
        log.info(
            f"SAM 2.1: mask {i} area={mask.sum()}px "
            f"({mask.sum() / (h * w) * 100:.1f}% of image)")

    return masks
