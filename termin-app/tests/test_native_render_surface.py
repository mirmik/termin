def test_native_render_reexports_canonical_render_modules():
    import termin._native as native
    from termin.editor._editor_native import SolidPrimitiveRenderer
    from termin.render_components import Camera, CameraProjection
    from termin.render_passes import (
        ShadowCameraParams,
        build_shadow_view_matrix,
        fit_shadow_frustum_to_camera,
    )

    assert native.render.Camera is Camera
    assert native.render.CameraProjection is CameraProjection
    assert native.render.ShadowCameraParams is ShadowCameraParams
    assert native.render.build_shadow_view_matrix is build_shadow_view_matrix
    assert native.render.fit_shadow_frustum_to_camera is fit_shadow_frustum_to_camera
    assert native.render.SolidPrimitiveRenderer is SolidPrimitiveRenderer
