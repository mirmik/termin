"""
SceneManager - manages scene lifecycle and update cycles.

Re-exports C++ SceneManager.
"""

from termin._native.scene import SceneManager, SceneMode

__all__ = ["SceneManager", "SceneMode"]
