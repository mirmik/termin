"""Native projection adapter for the toolkit-neutral ProceduralMesh extension model."""

from __future__ import annotations

import logging

from termin.editor_core.component_editor_extension import (
    ComponentEditorExtension,
    ComponentExtensionPresentation,
)
from termin.gui_native import TcDocument

from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)


def project_native_procedural_mesh_extension(
    extension: ComponentEditorExtension,
    document: TcDocument,
) -> ComponentExtensionPresentation:
    from termin.csg.native_editor_panel import (
        NativeCsgPanelMetrics,
        build_native_csg_editor_panel,
    )
    from termin.editor_core.procedural_mesh_editor_extension import (
        ProceduralMeshExtensionModel,
    )

    if not isinstance(extension, ProceduralMeshExtensionModel):
        _logger.error("ProceduralMesh projector received incompatible extension")
        raise TypeError("procedural mesh projector requires ProceduralMeshExtensionModel")

    panel = build_native_csg_editor_panel(
        document,
        extension,
        metrics=NativeCsgPanelMetrics(
            embedded_panel_insets=EDITOR_UI_METRICS.embedded_panel_insets,
            spacing=EDITOR_UI_METRICS.spacing,
            dense_spacing=EDITOR_UI_METRICS.dense_spacing,
            compact_spacing=EDITOR_UI_METRICS.compact_spacing,
            section_row=EDITOR_UI_METRICS.section_row,
            compact_status_row=EDITOR_UI_METRICS.compact_status_row,
            compact_row=EDITOR_UI_METRICS.compact_row,
        ),
    )
    if panel.root is None:
        raise RuntimeError("embedded native CSG panel did not create a combined root")
    return ComponentExtensionPresentation(right_panel=panel.root, close=panel.close)


__all__ = ["project_native_procedural_mesh_extension"]
