from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from termin.animation import TcAnimationClip, save_animation_clip
from termin.animation._animation_native import tc_animation_ensure_loaded, tc_animation_is_loaded
from termin.base import log
from termin.geombase import Quat, Vec3
from termin.default_assets.default_preloaders import create_default_preloaders
from termin.default_assets.resource_manager import DefaultResourceManager
from termin_assets import PreLoadResult, set_resource_manager_factory
from termin_assets.plugin_preloader import PluginPreLoader


@pytest.fixture
def manager():
    resource_manager = DefaultResourceManager()
    set_resource_manager_factory(lambda: resource_manager)
    try:
        yield resource_manager
    finally:
        set_resource_manager_factory(None)
        resource_manager.clear_runtime_state()


def _preloader(manager, notifications=None):
    callback = None if notifications is None else lambda kind, name: notifications.append((kind, name))
    matches = [
        item for item in create_default_preloaders(manager, callback)
        if item.resource_type == "animation_clip"
    ]
    assert len(matches) == 1
    assert isinstance(matches[0], PluginPreLoader)
    assert matches[0].extensions == {".tanim"}
    return matches[0]


def _write_clip(path: Path, *, name="walk", distance=4.0, loop=False):
    clip = TcAnimationClip.create(name, str(uuid.uuid4()))
    clip.set_tps(1.0)
    clip.set_loop(loop)
    clip.set_tracks([
        {
            "target_node_index": 3, "path": "translation", "interpolation": "linear",
            "components": 3, "times": [0.0, 2.0],
            "values": [0.0, 0.0, 0.0, distance, 0.0, 0.0],
        },
        {
            "target_node_index": 3, "path": "scale", "interpolation": "step",
            "components": 3, "times": [0.0, 2.0],
            "values": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        },
    ])
    save_animation_clip(clip, path)
    return clip


def _meta(path: Path) -> Path:
    return Path(str(path) + ".meta")


def _clip_snapshot(clip):
    return (
        clip.uuid, clip.name, clip.version, clip.tps, clip.loop, clip.duration,
        json.dumps(clip.tracks, sort_keys=True),
    )


@contextmanager
def _capture_errors():
    errors = []
    log.capture_start(128)
    try:
        yield errors
    finally:
        records, dropped = log.capture_drain(128)
        log.capture_stop()
        assert dropped == 0
        errors.extend(message for level, message in records if level == log.Level.ERROR)


@pytest.mark.parametrize("identity", ["metadata", "generated", "utf8-limit"])
def test_animation_initial_scan_declares_lazy_canonical_uuid_and_preserves_payload(
    tmp_path, manager, identity
):
    path = tmp_path / "walk.tanim"
    source = _write_clip(path)
    if identity != "generated":
        canonical_uuid = "é" * 31 + "x" if identity == "utf8-limit" else str(uuid.uuid4())
        _meta(path).write_text(json.dumps({"uuid": canonical_uuid, "label": "keep"}), encoding="utf-8")
    preloader = _preloader(manager)
    preloader.on_initial_file_added(str(path))
    metadata = json.loads(_meta(path).read_text(encoding="utf-8"))
    canonical_uuid = metadata["uuid"]
    assert canonical_uuid != source.uuid
    if identity != "generated":
        assert metadata["label"] == "keep"
    assert len(canonical_uuid.encode("utf-8")) <= 63
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    assert asset is manager.get_animation_clip_asset("walk")
    assert asset is not None
    assert not asset.is_loaded
    retained = asset.cached_data
    assert retained.is_valid
    assert retained.uuid == canonical_uuid
    assert not tc_animation_is_loaded(retained)
    assert preloader.get_tracked_files() == {str(path): {canonical_uuid}}

    assert tc_animation_ensure_loaded(retained)
    assert tc_animation_is_loaded(retained)
    assert asset.is_loaded
    assert asset.clip.uuid == canonical_uuid
    assert retained.name == source.name
    assert retained.tps == source.tps
    assert retained.loop == source.loop
    assert retained.duration == source.duration
    assert retained.tracks == source.tracks
    assert tuple(retained.sample_track(0, 0.5)) == pytest.approx((1.0, 0.0, 0.0))
    assert tuple(retained.sample_track(1, 0.5)) == pytest.approx((1.0, 2.0, 3.0))
    cached = asset.cached_data
    version = asset.version
    native_version = retained.version
    result = preloader.preload(str(path))
    assert result is not None
    assert manager.register_file(result) is not None
    assert manager.get_animation_clip_asset_by_uuid(canonical_uuid) is asset
    assert asset.cached_data is cached
    assert asset.is_loaded
    assert asset.version == version
    assert retained.version == native_version


def test_animation_initial_scan_lazy_loads_versioned_channels_payload(tmp_path, manager):
    path = tmp_path / "channels.tanim"
    source = TcAnimationClip.create("Authored channels", str(uuid.uuid4()))
    source.set_tps(2.0)
    source.set_loop(False)
    source.set_channels([{
        "target_name": "Root",
        "translation_keys": [(0.0, Vec3(1, 2, 3)), (2.0, Vec3(3, 6, 9))],
        "rotation_keys": [(0.0, Quat(0, 0, 0, 1)), (2.0, Quat(0, 0, 1, 0))],
        "scale_keys": [(0.0, 1.0), (2.0, 3.0)],
    }])
    save_animation_clip(source, path)
    assert "channels" in json.loads(path.read_text(encoding="utf-8"))
    _preloader(manager).on_initial_file_added(str(path))
    canonical_uuid = json.loads(_meta(path).read_text(encoding="utf-8"))["uuid"]
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    assert asset is not None and not asset.is_loaded
    held = asset.cached_data
    assert not tc_animation_is_loaded(held)
    assert tc_animation_ensure_loaded(held)
    assert held.uuid == asset.uuid == canonical_uuid != source.uuid
    assert asset.is_loaded and tc_animation_is_loaded(held)
    assert held.name == source.name
    assert held.tps == 2.0
    assert not held.loop
    assert held.duration == pytest.approx(1.0)
    assert held.channel_count == 1
    assert held.track_count == 0
    assert held.channels == source.channels
    sample = held.sample(0.5)[0]
    assert sample["target_name"] == "Root"
    assert sample["translation"] == pytest.approx([2.0, 4.0, 6.0])
    assert sample["rotation"] == pytest.approx([0.0, 0.0, 2**-0.5, 2**-0.5])
    assert sample["scale"] == pytest.approx(2.0)


def test_animation_loaded_reload_updates_held_handle_and_notifies_once(tmp_path, manager):
    path = tmp_path / "walk.tanim"
    _write_clip(path)
    notifications, events = [], []
    preloader = _preloader(manager, notifications)
    subscription = manager.subscribe_asset_reloaded(events.append)
    try:
        preloader.on_initial_file_added(str(path))
        assert notifications == [("animation_clip", "walk")]
        notifications.clear()
        canonical_uuid = json.loads(_meta(path).read_text(encoding="utf-8"))["uuid"]
        asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
        retained = asset.cached_data
        assert tc_animation_ensure_loaded(retained)
        asset_version, native_version = asset.version, retained.version
        updated = _write_clip(path, name="run", distance=8.0, loop=True)

        preloader.on_file_changed(str(path))

        assert manager.get_animation_clip_asset_by_uuid(canonical_uuid) is asset
        assert retained.uuid == asset.clip.uuid == canonical_uuid
        assert retained.version > native_version
        assert asset.version == asset_version + 1
        assert retained.name == "run"
        assert retained.loop
        assert retained.tracks == updated.tracks
        assert tuple(retained.sample_track(0, 0.5)) == pytest.approx((2.0, 0.0, 0.0))
        assert notifications == [("animation_clip", "walk")]
        assert len(events) == 1
        event = events[0]
        assert (event.type_id, event.name, event.uuid, event.version) == (
            "animation_clip", "walk", canonical_uuid, asset.version
        )
    finally:
        subscription.close()


@pytest.mark.parametrize("malformed_track", [0, 1], ids=["first-track", "later-track"])
def test_animation_corrupt_loaded_reload_keeps_payload_and_emits_no_notifications(
    tmp_path, manager, malformed_track
):
    path = tmp_path / "walk.tanim"
    _write_clip(path)
    notifications, events = [], []
    preloader = _preloader(manager, notifications)
    preloader.on_initial_file_added(str(path))
    canonical_uuid = json.loads(_meta(path).read_text(encoding="utf-8"))["uuid"]
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    retained = asset.cached_data
    assert tc_animation_ensure_loaded(retained)
    before = _clip_snapshot(retained)
    asset_version = asset.version
    notifications.clear()
    subscription = manager.subscribe_asset_reloaded(events.append)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(name="broken", tps=5.0, loop=True)
        payload["tracks"][malformed_track]["values"].pop()
        path.write_text(json.dumps(payload), encoding="utf-8")
        with _capture_errors() as errors:
            preloader.on_file_changed(str(path))
        assert errors
        assert asset.is_loaded
        assert asset.version == asset_version
        assert _clip_snapshot(retained) == before
        assert _clip_snapshot(asset.clip) == before
        assert notifications == []
        assert events == []
    finally:
        subscription.close()


def test_animation_unloaded_reload_defers_parsing_and_has_no_runtime_event(tmp_path, manager):
    path = tmp_path / "walk.tanim"
    _write_clip(path)
    preloader = _preloader(manager)
    preloader.on_initial_file_added(str(path))
    canonical_uuid = json.loads(_meta(path).read_text(encoding="utf-8"))["uuid"]
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    retained = asset.cached_data
    asset_version, native_version = asset.version, retained.version
    updated = _write_clip(path, name="deferred", distance=12.0)
    result = preloader.preload(str(path))
    assert result is not None
    events = []
    subscription = manager.subscribe_asset_reloaded(events.append)
    try:
        assert manager.reload_file(result)
        assert not asset.is_loaded
        assert not tc_animation_is_loaded(retained)
        assert asset.version == asset_version
        assert retained.version == native_version
        assert events == []
        assert tc_animation_ensure_loaded(retained)
        assert retained.tracks == updated.tracks
    finally:
        subscription.close()


@pytest.mark.parametrize(
    "metadata",
    ["not json", "[]", {"uuid": ""}, {"uuid": None}, {"uuid": 42},
     {"uuid": " padded "}, {"uuid": "nul\0uuid"}, {"uuid": "a" * 64}, {"uuid": "é" * 32}],
    ids=["bad-json", "non-object", "empty", "null", "non-string", "padding", "nul", "ascii-overflow", "utf8-overflow"],
)
def test_animation_preload_rejects_bad_metadata_without_rewriting_it(tmp_path, manager, metadata):
    path = tmp_path / "walk.tanim"
    source = _write_clip(path)
    before = _clip_snapshot(source)
    content = metadata if isinstance(metadata, str) else json.dumps(metadata)
    _meta(path).write_text(content, encoding="utf-8")
    original_bytes = _meta(path).read_bytes()
    preloader = _preloader(manager)
    with _capture_errors() as errors:
        assert preloader.preload(str(path)) is None
        preloader.on_initial_file_added(str(path))
    assert errors
    assert _meta(path).read_bytes() == original_bytes
    assert manager.get_animation_clip_asset("walk") is None
    assert preloader.get_file_count() == 0
    assert _clip_snapshot(source) == before


def test_animation_metadata_uuid_change_cannot_rebind_or_overwrite_loaded_asset(tmp_path, manager):
    path = tmp_path / "walk.tanim"
    _write_clip(path)
    notifications, events = [], []
    preloader = _preloader(manager, notifications)
    preloader.on_initial_file_added(str(path))
    canonical_uuid = json.loads(_meta(path).read_text(encoding="utf-8"))["uuid"]
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    retained = asset.cached_data
    assert tc_animation_ensure_loaded(retained)
    before, asset_version = _clip_snapshot(retained), asset.version
    notifications.clear()
    replacement_uuid = str(uuid.uuid4())
    _meta(path).write_text(json.dumps({"uuid": replacement_uuid}), encoding="utf-8")
    original_bytes = _meta(path).read_bytes()
    subscription = manager.subscribe_asset_reloaded(events.append)
    try:
        with _capture_errors() as errors:
            preloader.on_spec_changed(str(_meta(path)), str(path))
        assert errors
        assert _meta(path).read_bytes() == original_bytes
        assert manager.get_animation_clip_asset_by_uuid(canonical_uuid) is asset
        assert manager.get_animation_clip_asset_by_uuid(replacement_uuid) is None
        assert not TcAnimationClip.from_uuid(replacement_uuid).is_valid
        assert _clip_snapshot(retained) == before
        assert asset.version == asset_version
        assert notifications == events == []
        assert preloader.get_tracked_files() == {str(path): {canonical_uuid}}
    finally:
        subscription.close()


def test_animation_runtime_registration_rejects_inconsistent_metadata_before_native_declare(tmp_path, manager):
    path = tmp_path / "walk.tanim"
    _write_clip(path)
    canonical_uuid = str(uuid.uuid4())
    result = PreLoadResult(
        resource_type="animation_clip", path=str(path), uuid=canonical_uuid,
        spec_data={"uuid": str(uuid.uuid4())},
    )
    with _capture_errors() as errors:
        with pytest.raises(ValueError, match="UUID"):
            manager.register_file(result)
    assert errors
    assert manager.get_animation_clip_asset_by_uuid(canonical_uuid) is None
    assert not TcAnimationClip.from_uuid(canonical_uuid).is_valid


def test_installed_animation_plugins_discover_and_lazy_load_full_payload_without_overlay(tmp_path):
    path = tmp_path / "installed.tanim"
    source = _write_clip(path)
    canonical_uuid = str(uuid.uuid4())
    _meta(path).write_text(json.dumps({"uuid": canonical_uuid}), encoding="utf-8")
    child_cwd = tmp_path / "fresh-process"
    child_cwd.mkdir()
    script = """
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import sys
from termin.animation import TcAnimationClip
from termin.animation._animation_native import tc_animation_ensure_loaded, tc_animation_is_loaded
from termin.default_assets.default_preloaders import create_default_preloaders
from termin.default_assets.resource_manager import DefaultResourceManager
from termin_assets import set_resource_manager_factory

sdk_root = Path(os.environ['TERMIN_SDK']).resolve()
dist = metadata.distribution('termin-default-assets')
assert Path(dist.locate_file('')).resolve().is_relative_to(sdk_root)
origins = {}
for group, factory in (
    ('termin.asset_import_plugins', 'create_import_plugin'),
    ('termin.asset_runtime_plugins', 'create_runtime_plugin'),
):
    entries = [ep for ep in metadata.entry_points(group=group) if ep.name == 'animation_clip']
    assert len(entries) == 1
    entry = entries[0]
    assert entry.value == 'termin.default_assets.animation.asset_plugin:' + factory
    assert entry.dist.metadata['Name'] == 'termin-default-assets'
    module = importlib.import_module(entry.module)
    origin = Path(module.__file__).resolve()
    assert origin.is_relative_to(sdk_root), origin
    assert entry.load()().type_id == 'animation_clip'
    origins[group] = str(origin)
for module_name in ('termin.default_assets.animation.asset', 'termin.animation._animation_native'):
    origin = Path(importlib.import_module(module_name).__file__).resolve()
    assert origin.is_relative_to(sdk_root), origin

path, canonical_uuid, payload_uuid = sys.argv[1:]
assert not TcAnimationClip.from_uuid(canonical_uuid).is_valid
assert not TcAnimationClip.from_uuid(payload_uuid).is_valid
manager = DefaultResourceManager()
set_resource_manager_factory(lambda: manager)
try:
    preloaders = [p for p in create_default_preloaders(manager) if p.resource_type == 'animation_clip']
    assert len(preloaders) == 1
    preloaders[0].on_initial_file_added(path)
    asset = manager.get_animation_clip_asset_by_uuid(canonical_uuid)
    assert asset is not None and not asset.is_loaded
    held = asset.cached_data
    assert held.is_valid and held.uuid == canonical_uuid
    assert not tc_animation_is_loaded(held)
    assert tc_animation_ensure_loaded(held)
    assert tc_animation_is_loaded(held) and asset.is_loaded
    assert held.uuid == canonical_uuid != payload_uuid
    assert not TcAnimationClip.from_uuid(payload_uuid).is_valid
    print('ANIMATION_PLUGIN_PROBE=' + json.dumps({
        'origins': origins, 'name': held.name, 'tps': held.tps, 'loop': held.loop,
        'duration': held.duration, 'tracks': held.tracks,
        'translation': list(held.sample_track(0, 0.5)),
        'scale': list(held.sample_track(1, 0.5)),
    }), flush=True)
finally:
    set_resource_manager_factory(None)
    manager.clear_runtime_state()
"""
    child_env = os.environ.copy()
    for key in ("TERMIN_PYTHON_OVERLAY", "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE"):
        child_env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script, str(path), canonical_uuid, source.uuid],
        cwd=child_cwd, env=child_env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [line.removeprefix("ANIMATION_PLUGIN_PROBE=") for line in result.stdout.splitlines() if line.startswith("ANIMATION_PLUGIN_PROBE=")]
    assert len(reports) == 1, result.stdout
    report = json.loads(reports[0])
    assert set(report.pop("origins")) == {"termin.asset_import_plugins", "termin.asset_runtime_plugins"}
    assert report == {
        "name": source.name, "tps": source.tps, "loop": source.loop,
        "duration": source.duration, "tracks": source.tracks,
        "translation": [1.0, 0.0, 0.0], "scale": [1.0, 2.0, 3.0],
    }
