"""Editor render pipeline factory."""

from termin.visualization.render.framegraph import RenderPipeline


def make_editor_pipeline() -> RenderPipeline:
    """
    Create editor pipeline with gizmo, id pass, highlight effects.

    Returns:
        RenderPipeline configured for editor use.
    """
    from termin._native.editor import EditorInteractionSystem
    from termin.visualization.render.framegraph import (
        ColorPass,
        IdPass,
        PresentToScreenPass,
    )
    from termin.visualization.render.framegraph.passes.present import ResolvePass
    from termin.visualization.render.framegraph.resource_spec import ResourceSpec
    from termin.visualization.render.framegraph.passes.unified_gizmo import UnifiedGizmoPass
    from termin.visualization.render.framegraph.passes.collider_gizmo import ColliderGizmoPass
    from termin.visualization.render.framegraph.passes.immediate_depth import ImmediateDepthPass
    from termin.visualization.render.postprocess import PostProcessPass
    from termin.visualization.render.posteffects.highlight import HighlightEffect
    from termin.visualization.render.framegraph.passes.depth import DepthPass
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
    from termin.visualization.render.framegraph.passes.shadow import ShadowPass
    from termin.visualization.render.framegraph.passes.ui_widget import UIWidgetPass
    from termin.visualization.render.framegraph.passes.tonemap import TonemapPass
    from termin.visualization.render.framegraph.passes.bloom_pass import BloomPass

    def get_gizmo_manager():
        sys = EditorInteractionSystem.instance()
        return sys.gizmo_manager if sys else None

    def get_selected_pick_id():
        sys = EditorInteractionSystem.instance()
        return sys.selection.selected_pick_id if sys else 0

    def get_hovered_pick_id():
        sys = EditorInteractionSystem.instance()
        return sys.selection.hovered_pick_id if sys else 0

    # MSAA resolve before postprocessing
    resolve_pass = ResolvePass(
        input_res="color",
        output_res="color_resolved",
        pass_name="Resolve",
    )

    postprocess = PostProcessPass(
        effects=[],
        input_res="color_resolved",
        output_res="color_pp",
        pass_name="PostFX",
        internal_format="rgba16f",
    )

    depth_pass = DepthPass(input_res="empty_depth", output_res="depth", pass_name="Depth")

    color_pass = ColorPass(
        input_res="skybox",
        output_res="color_scene",
        shadow_res="shadow_maps",
        pass_name="Color",
        phase_mark="opaque",
        sort_mode="near_to_far",
    )

    transparent_pass = ColorPass(
        input_res="color_scene",
        output_res="color_transparent",
        shadow_res=None,
        pass_name="Transparent",
        phase_mark="transparent",
        sort_mode="far_to_near",
    )

    editor_color_pass = ColorPass(
        input_res="color_transparent",
        output_res="color_editor",
        shadow_res=None,
        pass_name="EditorColor",
        phase_mark="editor",
    )

    collider_gizmo_pass = ColliderGizmoPass(
        input_res="color_editor",
        output_res="color_colliders",
        pass_name="ColliderGizmo",
    )

    immediate_depth_pass = ImmediateDepthPass(
        input_res="color_colliders",
        output_res="color_immediate_depth",
        pass_name="ImmediateDepth",
    )

    gizmo_pass = UnifiedGizmoPass(
        gizmo_manager=get_gizmo_manager,
        input_res="color_immediate_depth",
        output_res="color",
        pass_name="Gizmo",
    )

    skybox_pass = SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox")

    shadow_pass = ShadowPass(
        output_res="shadow_maps",
        pass_name="Shadow",
    )

    tonemap_pass = TonemapPass(
        input_res="color_bloom",
        output_res="color_tonemapped",
        pass_name="Tonemap",
        method=2,
    )

    bloom_pass = BloomPass(
        input_res="color_pp",
        output_res="color_bloom",
    )

    passes: list = [
        shadow_pass,
        skybox_pass,
        color_pass,
        transparent_pass,
        editor_color_pass,
        immediate_depth_pass,
        collider_gizmo_pass,
        gizmo_pass,
        depth_pass,
        IdPass(input_res="empty_id", output_res="id", pass_name="Id"),
        resolve_pass,
        postprocess,
        bloom_pass,
        tonemap_pass,
        UIWidgetPass(
            input_res="color_tonemapped",
            output_res="color+widgets",
            include_internal_entities=True,
        ),
        PresentToScreenPass(
            input_res="color+widgets",
            pass_name="Present",
        ),
    ]

    postprocess.add_effect(
        HighlightEffect(
            get_hovered_pick_id,
            color=(0.3, 0.8, 1.0, 1.0),
        )
    )
    postprocess.add_effect(
        HighlightEffect(
            get_selected_pick_id,
            color=(1.0, 0.9, 0.1, 1.0),
        )
    )

    msaa_samples = 4
    hdr_format = "rgba16f"
    pipeline_specs = [
        ResourceSpec(
            resource="empty",
            samples=msaa_samples,
            format=hdr_format,
            clear_color=(0.2, 0.2, 0.2, 1.0),
            clear_depth=1.0,
        ),
        ResourceSpec(
            resource="color_resolved",
            format=hdr_format,
        ),
        ResourceSpec(
            resource="color_tonemapped",
            format=hdr_format,
        ),
        ResourceSpec(
            resource="color+widgets",
            format=hdr_format,
        ),
        ResourceSpec(
            resource="color_pp",
            format=hdr_format,
        )
    ]

    return RenderPipeline(
        name="editor",
        _init_passes=passes,
        _init_specs=pipeline_specs,
    )
