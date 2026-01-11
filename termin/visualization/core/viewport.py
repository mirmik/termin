from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.identifiable import Identifiable

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.display import Display
    from termin.visualization.ui.canvas import Canvas
    from termin.visualization.render.framegraph import RenderPipeline


@dataclass(eq=False)
class Viewport(Identifiable):
    """
    Viewport — "что рендерим и куда" в рамках дисплея.

    Содержит данные:
    - name: имя viewport для идентификации в пайплайне
    - scene: сцена с объектами
    - camera: камера для рендеринга
    - display: родительский дисплей
    - rect: нормализованный прямоугольник (x, y, w, h) в [0..1]
    - canvas: опциональная 2D канва для UI
    - depth: приоритет рендеринга (меньше = раньше, как Camera.depth в Unity)
    - pipeline: конвейер рендеринга (None = default)
    - layer_mask: маска слоёв (какие entity рендерить)

    fbos управляются снаружи через ViewportRenderState.

    Для рендеринга используйте RenderEngine с RenderView и ViewportRenderState.
    """
    name: str
    scene: "Scene"
    camera: "CameraComponent"
    rect: Tuple[float, float, float, float]  # x, y, width, height in normalized coords (0.0:1.0)
    display: Optional["Display"] = None
    canvas: Optional["Canvas"] = None
    depth: int = 0  # Render priority: lower values render first
    pipeline: Optional["RenderPipeline"] = None  # None = don't render
    input_mode: str = "simple"  # "none", "simple", "editor"
    block_input_in_editor: bool = False  # Block input when running in editor
    managed_by_scene_pipeline: Optional[str] = None  # Name of scene pipeline managing this viewport
    layer_mask: int = 0xFFFFFFFFFFFFFFFF  # All layers enabled by default
    enabled: bool = True  # Whether this viewport is rendered
    _init_uuid: str | None = field(default=None, repr=False)

    def __post_init__(self):
        Identifiable.__init__(self, uuid=self._init_uuid)

    @property
    def effective_layer_mask(self) -> int:
        """
        Get effective layer mask, checking ViewportHintComponent on camera first.

        If camera has ViewportHintComponent attached, use its layer_mask.
        Otherwise use viewport's own layer_mask.
        """
        if self.camera is not None and self.camera.entity is not None:
            from termin.visualization.core.viewport_hint import ViewportHintComponent
            hint = self.camera.entity.get_component(ViewportHintComponent)
            if hint is not None:
                return hint.layer_mask
        return self.layer_mask

    def screen_point_to_ray(self, x: float, y: float):
        """
        Преобразует экранные координаты в луч в мировом пространстве.

        Параметры:
            x, y: координаты в пикселях окна.

        Возвращает:
            Ray3 из камеры через указанную точку.
        """
        if self.display is None:
            raise ValueError("Viewport has no display")
        rect = self.display.viewport_rect_to_pixels(self)
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def compute_pixel_rect(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """
        Вычисляет прямоугольник viewport'а в пикселях.

        Параметры:
            width, height: размер родительской поверхности.

        Возвращает:
            (px, py, pw, ph) — позиция и размер в пикселях.
        """
        vx, vy, vw, vh = self.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = max(1, int(vw * width))
        ph = max(1, int(vh * height))
        return (px, py, pw, ph)

    def serialize(self) -> dict:
        """
        Сериализует viewport в словарь.

        Возвращает имя сущности камеры для последующего поиска при загрузке.
        """
        camera_entity_name = None
        if self.camera is not None and self.camera.entity is not None:
            camera_entity_name = self.camera.entity.name

        # Get pipeline name for serialization
        pipeline_name = None
        if self.pipeline is not None:
            pipeline_name = self.pipeline.name

        result = {
            "uuid": self._uuid,
            "name": self.name,
            "camera_entity": camera_entity_name,
            "rect": list(self.rect),
            "depth": self.depth,
            "pipeline": pipeline_name,
            "input_mode": self.input_mode,
            "block_input_in_editor": self.block_input_in_editor,
            "enabled": self.enabled,
        }
        # Only serialize layer_mask if not all layers (to keep files clean)
        if self.layer_mask != 0xFFFFFFFFFFFFFFFF:
            result["layer_mask"] = hex(self.layer_mask)
        return result


def make_default_pipeline() -> "RenderPipeline":
    """
    Собирает дефолтный конвейер рендера.

    Включает: ShadowPass, SkyBoxPass, ColorPass (opaque + transparent), PostFX, UIWidgets, Present.
    """
    from termin.visualization.render.framegraph import (
        ColorPass,
        PresentToScreenPass,
        RenderPipeline,
        UIWidgetPass,
    )
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
    from termin.visualization.render.framegraph.passes.shadow import ShadowPass
    from termin.visualization.render.postprocess import PostProcessPass

    # Shadow pass — генерирует shadow maps
    shadow_pass = ShadowPass(
        output_res="shadow_maps",
        pass_name="Shadow",
    )

    # Opaque pass — читает shadow maps
    color_pass = ColorPass(
        input_res="skybox",
        output_res="color_opaque",
        shadow_res="shadow_maps",
        pass_name="Color",
        phase_mark="opaque",
    )

    # Transparent pass — прозрачные объекты с сортировкой
    transparent_pass = ColorPass(
        input_res="color_opaque",
        output_res="color",
        shadow_res=None,
        pass_name="Transparent",
        phase_mark="transparent",
        sort_mode="far_to_near",
    )

    passes: List = [
        shadow_pass,
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        color_pass,
        transparent_pass,
        PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        ),
        UIWidgetPass(
            input_res="color_pp",
            output_res="color+widgets",
            pass_name="UIWidgets",
        ),
        PresentToScreenPass(
            input_res="color+widgets",
            pass_name="Present",
        )
    ]

    return RenderPipeline(name="Default", passes=passes)