from __future__ import annotations

import logging

import pytest

from termin.editor_core.rendering_factories import (
    PipelineAssetResolver,
    RenderingFactoryRegistration,
)


class _Resources:
    def __init__(self) -> None:
        self.by_uuid = {"pipeline-uuid": object()}
        self.by_name = {"NamedPipeline": object()}
        self.uuid_requests: list[str] = []
        self.name_requests: list[str] = []

    def get_pipeline_by_uuid(self, identifier: str):
        self.uuid_requests.append(identifier)
        return self.by_uuid.get(identifier)

    def get_pipeline(self, name: str):
        self.name_requests.append(name)
        return self.by_name.get(name)


class _Manager:
    def __init__(self, *, fail_pipeline: bool = False) -> None:
        self.display_factory = None
        self.pipeline_factory = None
        self.fail_pipeline = fail_pipeline
        self.events: list[tuple[str, object]] = []

    def set_display_factory(self, factory) -> None:
        self.display_factory = factory
        self.events.append(("display", factory))

    def set_pipeline_factory(self, factory) -> None:
        if factory is not None and self.fail_pipeline:
            raise RuntimeError("pipeline registration failed")
        self.pipeline_factory = factory
        self.events.append(("pipeline", factory))


def test_pipeline_asset_resolver_supports_uuid_name_and_editor(caplog):
    resources = _Resources()
    editor_pipeline = object()
    resolver = PipelineAssetResolver(
        resources,
        make_editor_pipeline=lambda: editor_pipeline,
    )

    assert resolver.resolve("pipeline-uuid") is resources.by_uuid["pipeline-uuid"]
    assert resolver.resolve("NamedPipeline") is resources.by_name["NamedPipeline"]
    assert resolver.resolve("(Editor)") is editor_pipeline
    assert resolver.resolve("Default") is None

    with caplog.at_level(logging.ERROR):
        assert resolver.resolve("missing-pipeline") is None
    assert "Cannot resolve rendering pipeline asset 'missing-pipeline'" in caplog.text


def test_rendering_factory_registration_installs_and_clears_both_callbacks():
    manager = _Manager()
    display_factory = lambda _name: None
    pipeline_factory = lambda _name: None
    registration = RenderingFactoryRegistration(
        manager,
        display_factory=display_factory,
        pipeline_factory=pipeline_factory,
    )

    registration.install()

    assert registration.installed
    assert manager.display_factory is display_factory
    assert manager.pipeline_factory is pipeline_factory

    registration.close()
    registration.close()

    assert not registration.installed
    assert manager.pipeline_factory is None
    assert manager.display_factory is None
    assert manager.events[-2:] == [("pipeline", None), ("display", None)]


def test_rendering_factory_registration_rolls_back_display_on_pipeline_failure():
    manager = _Manager(fail_pipeline=True)
    registration = RenderingFactoryRegistration(
        manager,
        display_factory=lambda _name: None,
        pipeline_factory=lambda _name: None,
    )

    with pytest.raises(RuntimeError, match="pipeline registration failed"):
        registration.install()

    assert not registration.installed
    assert manager.display_factory is None
    assert manager.pipeline_factory is None
