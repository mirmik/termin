from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np

from termin.visualization.core.entity import Component
from termin.visualization.core.animation_clip_handle import AnimationClipHandle
from termin.editor.inspect_field import InspectField
from termin.geombase.pose3 import Pose3
from termin.geombase.general_pose3 import GeneralPose3
from .clip import AnimationClip

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonInstance
    from termin.visualization.core.scene import Scene


class AnimationPlayer(Component):
    """
    Компонент-плеер: хранит набор клипов и проигрывает один из них,
    обновляя локальный Pose3 сущности (и её scale).

    Может также обновлять SkeletonInstance для скелетной анимации.
    """

    _DEBUG_UPDATE = False
    _DEBUG_LIFECYCLE = True  # Debug deserialization/start issues

    inspect_fields = {
        **Component.inspect_fields,
        "clips": InspectField(
            label="Animation Clips",
            kind="animation_clip_list",
            getter=lambda self: self._clip_handles,
            setter=lambda self, v: self._set_clip_handles(v),
        ),
        "_current_clip_name": InspectField(
            path="_current_clip_name",
            label="Current Clip",
            kind="str",
        ),
        "playing": InspectField(
            path="playing",
            label="Playing",
            kind="bool",
        ),
    }

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._clip_handles: List[AnimationClipHandle] = []
        self.clips: Dict[str, AnimationClip] = {}  # Cache for quick lookup
        self.current: Optional[AnimationClip] = None
        self._current_clip_name: str = ""  # For serialization
        self.time: float = 0.0
        self.playing: bool = False
        self._target_skeleton: "SkeletonInstance | None" = None

    def _set_clip_handles(self, handles: List[AnimationClipHandle] | None) -> None:
        """Setter for clips InspectField."""
        if self._DEBUG_LIFECYCLE:
            print(f"[AnimationPlayer._set_clip_handles] handles={len(handles) if handles else 0}")
            if handles:
                for i, h in enumerate(handles):
                    asset = h.asset
                    asset_uuid = asset.uuid[:8] if asset and asset.uuid else 'None'
                    clip_name = h.clip.name if h.clip else 'None'
                    print(f"  [{i}] asset_uuid={asset_uuid}..., clip={clip_name}")
        self._clip_handles = handles if handles else []
        self._rebuild_clips_cache()

    def _rebuild_clips_cache(self) -> None:
        """Rebuild clips dict from handles."""
        self.clips.clear()
        for handle in self._clip_handles:
            clip = handle.clip
            if clip is not None:
                self.clips[clip.name] = clip
        if self._DEBUG_LIFECYCLE:
            print(f"[AnimationPlayer._rebuild_clips_cache] clips={list(self.clips.keys())}")

    def start(self, scene: "Scene") -> None:
        """Called once before the first update. Find SkeletonController on entity."""
        if self._DEBUG_LIFECYCLE:
            print(f"[AnimationPlayer.start] entity={self.entity.name if self.entity else 'None'}")
            print(f"  _clip_handles={len(self._clip_handles)}, _current_clip_name={self._current_clip_name!r}, playing={self.playing}")
        super().start(scene)
        self._acquire_skeleton()
        self._rebuild_clips_cache()
        # Resume playing if we have a current clip name
        if self._current_clip_name and self._current_clip_name in self.clips:
            self.current = self.clips[self._current_clip_name]
            if self._DEBUG_LIFECYCLE:
                print(f"  Restored current clip: {self._current_clip_name}")
        elif self._current_clip_name:
            if self._DEBUG_LIFECYCLE:
                print(f"  WARNING: current clip '{self._current_clip_name}' not found in clips!")
        if self._DEBUG_LIFECYCLE:
            print(f"  After start: current={self.current.name if self.current else 'None'}, playing={self.playing}, skeleton={self._target_skeleton is not None}")

    def _acquire_skeleton(self) -> None:
        """Find SkeletonController on entity and get skeleton_instance."""
        if self.entity is None:
            return

        from termin.visualization.render.components.skeleton_controller import SkeletonController
        skeleton_controller = self.entity.get_component(SkeletonController)
        if self._DEBUG_LIFECYCLE:
            print(f"  [_acquire_skeleton] skeleton_controller={skeleton_controller is not None}")
        if skeleton_controller is not None:
            self._target_skeleton = skeleton_controller.skeleton_instance
            if self._DEBUG_LIFECYCLE:
                print(f"  [_acquire_skeleton] skeleton_instance={self._target_skeleton is not None}")

    @property
    def target_skeleton(self) -> "SkeletonInstance | None":
        """Get target skeleton for bone animation."""
        return self._target_skeleton

    @target_skeleton.setter
    def target_skeleton(self, value: "SkeletonInstance | None"):
        """Set target skeleton for bone animation."""
        self._target_skeleton = value

    def add_clip(self, clip: AnimationClip) -> AnimationClip:
        """Add animation clip to the player."""
        self.clips[clip.name] = clip
        # Create handle from asset if registered, otherwise direct
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_animation_clip_asset(clip.name)
        if asset is not None:
            handle = AnimationClipHandle.from_asset(asset)
        else:
            handle = AnimationClipHandle.from_direct(clip)
        self._clip_handles.append(handle)
        return clip

    def play(self, name: str, restart: bool = True):
        clip = self.clips.get(name)
        if clip is None:
            raise KeyError(f"[AnimationPlayer] clip '{name}' not found")

        if self.current is not clip or restart:
            self.time = 0.0

        self.current = clip
        self._current_clip_name = name  # Store for serialization
        self.playing = True

    def stop(self):
        self.playing = False

    _debug_frame_count = 0
    _debug_update_logged = False

    def update(self, dt: float):
        if not (self.enabled and self.playing and self.current):
            if self._DEBUG_LIFECYCLE and not AnimationPlayer._debug_update_logged:
                AnimationPlayer._debug_update_logged = True
                print(f"[AnimationPlayer.update] SKIPPED: enabled={self.enabled}, playing={self.playing}, current={self.current is not None}")
            return

        self.time += dt

        sample = self.current.sample(self.time)

        if self._DEBUG_UPDATE and AnimationPlayer._debug_frame_count < 3:
            AnimationPlayer._debug_frame_count += 1
            print(f"[AnimationPlayer.update] clip={self.current.name!r}, duration={self.current.duration:.3f}s, time={self.time:.3f}")
            print(f"  channels={len(sample)}, target_skeleton={self._target_skeleton is not None}")
            for name, data in list(sample.items())[:3]:
                tr, rot, sc = data
                print(f"  {name}: tr={tr}, rot={rot}")

        # If we have a target skeleton, apply bone transforms
        if self._target_skeleton is not None:
            self._update_skeleton(sample)

        # Also update entity transform if entity is set (for root motion, etc.)
        if self.entity is not None:
            self._update_entity(sample)

    _debug_skeleton_frame = 0

    def _update_skeleton(self, sample: Dict):
        """Update skeleton bone transforms from animation sample."""
        found_count = 0
        for channel_name, channel_data in sample.items():
            tr = channel_data[0]  # translation
            rot = channel_data[1]  # rotation (quaternion xyzw)
            sc = channel_data[2]  # scale (float or None)

            # Check if bone exists before setting
            bone_idx = self._target_skeleton._data.get_bone_index(channel_name)
            if bone_idx >= 0:
                found_count += 1

            # Set bone transform
            self._target_skeleton.set_bone_transform_by_name(
                channel_name,
                translation=tr,
                rotation=rot,
                scale=sc,  # Already a float from AnimationChannel.sample()
            )

        if self._DEBUG_UPDATE and AnimationPlayer._debug_skeleton_frame < 3:
            AnimationPlayer._debug_skeleton_frame += 1
            skeleton_bones = [b.name for b in self._target_skeleton._data.bones[:5]]
            sample_channels = list(sample.keys())[:5]
            print(f"[_update_skeleton] found {found_count}/{len(sample)} channels matching bones")
            print(f"  skeleton bones[:5]: {skeleton_bones}")
            print(f"  sample channels[:5]: {sample_channels}")

    def _update_entity(self, sample: Dict):
        """Update entity transform from animation sample (legacy mode)."""
        # Look for "clip" channel (legacy single-channel mode)
        if "clip" not in sample:
            return

        channel_data = sample["clip"]

        pose: GeneralPose3 = self.entity.transform.local_pose()

        tr = channel_data[0]
        rot = channel_data[1]
        sc = channel_data[2]

        new_lin = np.asarray(tr, dtype=np.float64) if tr is not None else pose.lin
        new_ang = np.asarray(rot, dtype=np.float64) if rot is not None else pose.ang

        if sc is not None:
            # sc can be scalar or array
            if isinstance(sc, (int, float)):
                new_scale = np.full(3, float(sc), dtype=np.float64)
            elif len(sc) == 1:
                new_scale = np.full(3, float(sc[0]), dtype=np.float64)
            else:
                new_scale = np.asarray(sc, dtype=np.float64)
        else:
            new_scale = pose.scale

        new_pose = GeneralPose3(lin=new_lin, ang=new_ang, scale=new_scale)
        self.entity.transform.relocate(new_pose)
