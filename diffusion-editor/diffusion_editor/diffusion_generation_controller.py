"""Application workflow for Stable Diffusion generation tasks."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
from PIL import Image
from tcbase import log

from .diffusion_engine import DiffusionEngine
from .diffusion_request_builder import DiffusionRequestBuilder
from .layer import Layer
from .layer_stack import LayerStack
from .tool import DiffusionTool


@dataclass(frozen=True)
class DiffusionControllerEvent:
    status: str | None = None
    model_loaded_path: str | None = None
    model_error: str | None = None
    ip_adapter_loaded: bool = False
    ip_adapter_error: str | None = None
    inference_result: tuple[Layer, Image.Image, int] | None = None
    inference_error: str | None = None


class DiffusionGenerationController:
    def __init__(
            self,
            *,
            engine: DiffusionEngine,
            layer_stack: LayerStack,
            composite_below: Callable[[Layer], np.ndarray | None]):
        self._engine = engine
        self._layer_stack = layer_stack
        self._composite_below = composite_below
        self._pending_layer: Layer | None = None

    @property
    def pending_layer(self) -> Layer | None:
        return self._pending_layer

    def clear_pending_layer(self, layer: Layer) -> None:
        if self._pending_layer is layer:
            self._pending_layer = None

    def submit_load_model(
            self,
            path: str,
            prediction_type: str | None = None) -> DiffusionControllerEvent:
        if self._engine.is_busy:
            return DiffusionControllerEvent()
        pred = prediction_type if prediction_type else None
        submitted = self._engine.submit_load(path, pred)
        if not submitted:
            return DiffusionControllerEvent()
        return DiffusionControllerEvent(status="Loading model...")

    def submit_load_ip_adapter(self) -> DiffusionControllerEvent:
        if self._engine.is_busy or not self._engine.is_loaded:
            return DiffusionControllerEvent()
        submitted = self._engine.submit_load_ip_adapter()
        if not submitted:
            return DiffusionControllerEvent()
        return DiffusionControllerEvent(status="Loading IP-Adapter...")

    def start_regeneration(self, layer: Layer) -> DiffusionControllerEvent:
        if self._engine.is_busy:
            return DiffusionControllerEvent()
        tool = layer.tool
        if not isinstance(tool, DiffusionTool):
            return DiffusionControllerEvent()

        if tool.model_path and tool.model_path != self._engine.model_path:
            self._pending_layer = layer
            pred = tool.prediction_type if tool.prediction_type else None
            submitted = self._engine.submit_load(tool.model_path, pred)
            if not submitted:
                self._pending_layer = None
                return DiffusionControllerEvent()
            return DiffusionControllerEvent(status="Loading model for regeneration...")

        if not self._engine.is_loaded:
            return DiffusionControllerEvent()
        return self._submit_regeneration(layer)

    def _submit_regeneration(self, layer: Layer) -> DiffusionControllerEvent:
        tool = layer.tool
        if not isinstance(tool, DiffusionTool):
            return DiffusionControllerEvent()

        self._pending_layer = layer

        composite_below = None
        if tool.mode != "txt2img":
            composite_below = self._composite_below(layer)

        build = DiffusionRequestBuilder(self._layer_stack).build(
            layer,
            composite_below,
        )
        if build.error is not None:
            log.error(build.error.log_message or build.error.message)
            self._pending_layer = None
            return DiffusionControllerEvent(status=build.error.message)

        request = build.request
        if request is None:
            log.error(f"Diffusion request builder returned no request for {layer.name}")
            self._pending_layer = None
            return DiffusionControllerEvent(status="Could not build diffusion request")

        if request.ip_adapter_image is not None and not self._engine.ip_adapter_loaded:
            submitted = self._engine.submit_load_ip_adapter()
            if not submitted:
                self._pending_layer = None
                return DiffusionControllerEvent(status="Could not load IP-Adapter")
            return DiffusionControllerEvent(status="Loading IP-Adapter...")

        submitted = self._engine.submit(
            image=request.image,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            strength=request.strength,
            steps=request.steps,
            guidance_scale=request.guidance_scale,
            seed=request.seed,
            mode=request.mode,
            mask_image=request.mask_image,
            masked_content=request.masked_content,
            ip_adapter_image=request.ip_adapter_image,
            ip_adapter_scale=request.ip_adapter_scale,
            width=request.width,
            height=request.height,
        )
        if not submitted:
            self._pending_layer = None
            return DiffusionControllerEvent()

        return DiffusionControllerEvent(
            status=f"Regenerating ({request.width}x{request.height})..."
        )

    def poll(self) -> DiffusionControllerEvent | None:
        task_type, result, error, _meta = self._engine.poll()
        if task_type is None:
            return None

        log.debug(
            f"[DiffusionGenerationController] task_type={task_type}, "
            f"error={error}, result_type={type(result)}"
        )

        if task_type == "load":
            if error:
                log.error(f"Diffusion model load error: {error}")
                self._pending_layer = None
                return DiffusionControllerEvent(
                    model_error=error,
                    status=f"Model load error: {error[:80]}",
                )
            pending = self._pending_layer
            event = DiffusionControllerEvent(
                model_loaded_path=result,
                status="Model loaded",
            )
            if pending is not None and isinstance(pending.tool, DiffusionTool):
                return replace(
                    self._submit_regeneration(pending),
                    model_loaded_path=result,
                )
            return event

        if task_type == "load_ip_adapter":
            if error:
                log.error(f"IP-Adapter load error: {error}")
                self._pending_layer = None
                return DiffusionControllerEvent(
                    ip_adapter_error=error,
                    status=f"IP-Adapter error: {error[:80]}",
                )
            pending = self._pending_layer
            event = DiffusionControllerEvent(
                ip_adapter_loaded=True,
                status="IP-Adapter loaded",
            )
            if pending is not None and isinstance(pending.tool, DiffusionTool):
                return replace(
                    self._submit_regeneration(pending),
                    ip_adapter_loaded=True,
                )
            return event

        if task_type == "inference":
            if error:
                log.error(f"Diffusion inference error: {error}")
                self._pending_layer = None
                return DiffusionControllerEvent(
                    inference_error=error,
                    status=f"Diffusion error: {error[:80]}",
                )

            pending = self._pending_layer
            self._pending_layer = None
            if pending is None:
                return DiffusionControllerEvent(
                    status="Diffusion result ignored: no pending layer"
                )
            result_image, used_seed = result
            log.debug(
                "[DiffusionGenerationController] inference OK, "
                f"seed={used_seed}, pending={type(pending).__name__}"
            )
            return DiffusionControllerEvent(
                inference_result=(pending, result_image, used_seed)
            )

        return DiffusionControllerEvent()
