"""Core scene graph primitives and resource helpers.

This package is intentionally an empty namespace. Import the specific
submodules you need directly, e.g.:

    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.display import Display

This avoids pulling the whole render stack on every import, which matters
because some submodules (e.g. render.render_context) have heavy native
dependencies that aren't needed by every consumer.
"""
