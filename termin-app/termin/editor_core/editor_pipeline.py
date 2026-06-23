"""Editor render pipeline factory."""

from termin.render_framework import RenderPipeline


def make_editor_pipeline() -> RenderPipeline:
    """
    Create editor pipeline with gizmo, id pass, and highlight passes.

    Returns:
        RenderPipeline configured for editor use.
    """
    from termin.editor._editor_native import EditorInteractionSystem
    from termin.render_components import DepthPass
    from termin.render_framework import ResourceSpec
    from termin.render_passes import (
        BloomPass,
        ColliderGizmoPass,
        ColorPass,
        HighlightPass,
        IdPass,
        ImmediateDepthPass,
        PresentToScreenPass,
        ResolvePass,
        ShadowPass,
        SkyBoxPass,
        TonemapPass,
        UIWidgetPass,
        UnifiedGizmoPass,
    )

    def get_gizmo_manager():
        sys = EditorInteractionSystem.instance()
        return sys.gizmo_manager if sys else None

    def get_selected_pick_id():
        sys = EditorInteractionSystem.instance()
        return sys.selection.selected_pick_id if sys else 0

    def get_hovered_pick_id():
        sys = EditorInteractionSystem.instance()
        return sys.selection.hovered_pick_id if sys else 0

    # MSAA resolve before fullscreen effects
    resolve_pass = ResolvePass(
        input_res="color",
        output_res="color_resolved",
        pass_name="Resolve",
    )

    hover_highlight_pass = HighlightPass(
        get_hovered_pick_id,
        color=(0.3, 0.8, 1.0, 1.0),
        input_res="color_resolved",
        id_res="id",
        output_res="color_hover_highlight",
        pass_name="HoverHighlight",
    )

    selected_highlight_pass = HighlightPass(
        get_selected_pick_id,
        color=(1.0, 0.9, 0.1, 1.0),
        input_res="color_hover_highlight",
        id_res="id",
        output_res="color_highlight",
        pass_name="SelectedHighlight",
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

    editor_debug_pass = ColorPass(
        input_res="color_editor",
        output_res="color_editor_debug",
        shadow_res=None,
        pass_name="EditorDebug",
        phase_mark="editor_debug",
        sort_mode="near_to_far",
    )

    editor_debug_transparent_pass = ColorPass(
        input_res="color_editor_debug",
        output_res="color_editor_debug_transparent",
        shadow_res=None,
        pass_name="EditorDebugTransparent",
        phase_mark="editor_debug_transparent",
        sort_mode="far_to_near",
    )

    collider_gizmo_pass = ColliderGizmoPass(
        input_res="color_editor_debug_transparent",
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
        pass_name="Shadow"
    )

    tonemap_pass = TonemapPass(
        input_res="color_bloom",
        output_res="color_tonemapped",
        pass_name="Tonemap",
        method=2,
    )

    bloom_pass = BloomPass(
        input_res="color_highlight",
        output_res="color_bloom",
    )

    passes: list = [
        shadow_pass,
        skybox_pass,
        color_pass,
        transparent_pass,
        editor_color_pass,
        editor_debug_pass,
        editor_debug_transparent_pass,
        collider_gizmo_pass,
        immediate_depth_pass,
        gizmo_pass,
        depth_pass,
        IdPass(input_res="empty_id", output_res="id", pass_name="Id"),
        resolve_pass,
        hover_highlight_pass,
        selected_highlight_pass,
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

    msaa_samples = 4
    color_fbo_format = "render_target"
    pipeline_specs = [
        ResourceSpec(
            resource="empty",
            samples=msaa_samples,
            format=color_fbo_format,
            clear_color=(0.2, 0.2, 0.2, 1.0),
            clear_depth=1.0,
        ),
        ResourceSpec(
            resource="skybox",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_scene",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_transparent",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_editor",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_editor_debug",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_editor_debug_transparent",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_colliders",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_immediate_depth",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_resolved",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_hover_highlight",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_highlight",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_bloom",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color_tonemapped",
            format=color_fbo_format,
        ),
        ResourceSpec(
            resource="color+widgets",
            format=color_fbo_format,
        )
    ]

    return RenderPipeline(
        name="editor",
        _init_passes=passes,
        _init_specs=pipeline_specs,
    )
