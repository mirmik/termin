"""Python automation facade for the native packaged-player host."""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
from typing import Any

from termin.base import log

from termin.display import Display
from termin.engine import _borrow_engine_core
from termin.scene import TcScene
from termin.viewport import Viewport

from . import runtime as player_runtime
from .mcp_server import start_player_mcp_server


class NativePlayerWindow:
    """Non-owning Python view of the native host's presentation window."""

    def __init__(self, bridge: ModuleType) -> None:
        self._bridge = bridge

    def framebuffer_size(self) -> tuple[int, int]:
        width, height = self._bridge.window_framebuffer_size()
        return int(width), int(height)

    def should_close(self) -> bool:
        return bool(self._bridge.window_should_close())

    def set_should_close(self, value: bool) -> None:
        self._bridge.set_window_should_close(bool(value))


class NativePlayerRuntime:
    """Live, non-owning runtime context exposed to player MCP scripts."""

    def __init__(self, bridge: ModuleType) -> None:
        self._bridge = bridge
        self._engine = _borrow_engine_core(bridge.engine_capsule())
        self.rendering_manager = self._engine.rendering_manager
        from termin.default_assets.resource_manager import DefaultResourceManager

        self.resource_manager = DefaultResourceManager.instance()

        display_index, display_generation = bridge.display_handle()
        self.display = Display.from_handle(display_index, display_generation)

        self.window = NativePlayerWindow(bridge)
        self.camera = None
        self.project_path = Path(bridge.project_path())
        self.delta_time = 0.0

    @property
    def scene(self):
        """Return the primary packaged scene published by RuntimeSession."""
        scene_index, scene_generation = self._bridge.scene_handle()
        return TcScene.from_handle(scene_index, scene_generation)

    @property
    def viewport(self):
        """Return the current primary scene's first packaged viewport."""
        viewport_index, viewport_generation = self._bridge.viewport_handle()
        return Viewport._from_handle((viewport_index, viewport_generation))

    @property
    def scene_name(self) -> str:
        """Return the stable package identity of the primary scene."""
        return str(self._bridge.scene_name())

    @property
    def exit_code(self) -> int:
        return int(self._bridge.exit_code())

    def request_quit(self, exit_code: int = 0) -> None:
        self._bridge.request_quit(int(exit_code))


class NativePlayerSession:
    """Own the Python-side automation lifecycle for one native host run."""

    def __init__(
        self,
        runtime: NativePlayerRuntime,
        *,
        explicit_mcp: bool,
        manifest_options: dict[str, Any],
    ) -> None:
        self.runtime = runtime
        self._closed = False
        player_runtime._active_runtime = runtime
        try:
            self._executor, self._server = start_player_mcp_server(
                runtime,
                explicit=explicit_mcp,
                manifest_options=manifest_options,
            )
        except BaseException:
            player_runtime._active_runtime = None
            raise
        if self._executor is not None and self._server is None:
            log.error("[NativePlayerSession] Player MCP server did not start")

    def process_pending(self) -> int:
        if self._closed or self._executor is None:
            return 0
        return self._executor.process_pending()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._executor is not None:
            self._executor.close()
        if self._server is not None:
            self._server.stop()
            self._server = None
        self._executor = None
        if player_runtime._active_runtime is self.runtime:
            player_runtime._active_runtime = None


def create_native_player_session(
    bridge: ModuleType,
    explicit_mcp: bool,
    manifest_options_json: str,
) -> NativePlayerSession:
    """Build one native-host facade and optionally start its MCP server."""
    manifest_options = json.loads(manifest_options_json)
    if not isinstance(manifest_options, dict):
        raise TypeError("native player MCP manifest options must be an object")
    return NativePlayerSession(
        NativePlayerRuntime(bridge),
        explicit_mcp=bool(explicit_mcp),
        manifest_options=manifest_options,
    )


__all__ = [
    "NativePlayerRuntime",
    "NativePlayerSession",
    "NativePlayerWindow",
    "create_native_player_session",
]
