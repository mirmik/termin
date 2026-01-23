"""Viewport - what to render and where."""

from typing import List

from termin.viewport import Viewport

__all__ = ["Viewport", "make_default_pipeline"]


def make_default_pipeline():
    """
    Build default render pipeline.

    Includes: ShadowPass, SkyBoxPass, ColorPass (opaque + transparent), PostFX, UIWidgets, Present.
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

    shadow_pass = ShadowPass(
        output_res="shadow_maps",
        pass_name="Shadow",
    )

    color_pass = ColorPass(
        input_res="skybox",
        output_res="color_opaque",
        shadow_res="shadow_maps",
        pass_name="Color",
        phase_mark="opaque",
    )

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

    return RenderPipeline(name="Default", _init_passes=passes)
