from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

from dataclasses import dataclass

import pytest

from termin.editor_core.component_editor_extension import (
    ComponentEditorExtensionRegistry,
    ComponentEditorExtensionSession,
    ComponentExtensionPresentation,
)
from termin.editor_native.component_extensions import NativeComponentExtensionProjectorRegistry


@dataclass
class _Extension:
    name: str
    events: list[str]
    fail_detach: bool = False

    def attach(self, _editor, _entity, _component_ref) -> None:
        self.events.append(f"attach:{self.name}")

    def detach(self) -> None:
        self.events.append(f"detach:{self.name}")
        if self.fail_detach:
            raise RuntimeError(f"detach failed: {self.name}")


def test_component_extension_session_replaces_and_clears_exactly_once():
    events: list[str] = []
    registry = ComponentEditorExtensionRegistry()
    registry.register("First", lambda: _Extension("first", events))
    registry.register("Second", lambda: _Extension("second", events))

    def presenter(extension, type_name):
        events.append(f"project:{type_name}")
        return ComponentExtensionPresentation(right_panel=f"right:{extension.name}")

    session = ComponentEditorExtensionSession(
        editor=lambda: "editor",
        presenter=presenter,
        present=lambda type_name, _presentation: events.append(f"present:{type_name}"),
        clear_presentation=lambda: events.append("clear"),
        registry=registry,
    )

    session.select_component("entity", "ref", "First")
    assert session.active_type_name == "First"
    session.select_component("entity", "ref", "Second")
    assert session.active_type_name == "Second"
    session.clear()
    assert session.active_type_name == ""
    assert events == [
        "clear",
        "attach:first",
        "project:First",
        "present:First",
        "detach:first",
        "clear",
        "attach:second",
        "project:Second",
        "present:Second",
        "detach:second",
        "clear",
    ]


def test_component_extension_session_detaches_and_clears_failed_projection():
    events: list[str] = []
    registry = ComponentEditorExtensionRegistry()
    registry.register("Broken", lambda: _Extension("broken", events))

    def fail_projection(_extension, _type_name):
        events.append("project")
        raise RuntimeError("projection failed")

    session = ComponentEditorExtensionSession(
        editor=lambda: object(),
        presenter=fail_projection,
        present=lambda _type_name, _presentation: events.append("present"),
        clear_presentation=lambda: events.append("clear"),
        registry=registry,
    )

    with pytest.raises(RuntimeError, match="projection failed"):
        session.select_component(object(), object(), "Broken")
    assert session.active_type_name == ""
    assert events == ["clear", "attach:broken", "project", "detach:broken", "clear"]


def test_component_extension_session_clears_presentation_when_detach_fails():
    events: list[str] = []
    registry = ComponentEditorExtensionRegistry()
    registry.register("Broken", lambda: _Extension("broken", events, fail_detach=True))
    session = ComponentEditorExtensionSession(
        editor=lambda: object(),
        presenter=lambda _extension, _type_name: ComponentExtensionPresentation(),
        present=lambda _type_name, _presentation: events.append("present"),
        clear_presentation=lambda: events.append("clear"),
        registry=registry,
    )
    session.select_component(object(), object(), "Broken")

    with pytest.raises(RuntimeError, match="detach failed"):
        session.clear()
    assert session.active_type_name == ""
    assert events[-2:] == ["detach:broken", "clear"]


def test_native_component_extension_projector_registry_owns_frontend_boundary():
    document = tc_ui_document_create()
    registry = NativeComponentExtensionProjectorRegistry(document)
    extension = _Extension("native", [])

    def project(_extension, owner_document):
        panel = owner_document.create_vstack("native-extension-test-panel")
        return ComponentExtensionPresentation(right_panel=panel)

    registry.register("Native", project)
    presentation = registry.project(extension, "Native")
    assert presentation.right_panel.debug_name == "native-extension-test-panel"
    with pytest.raises(KeyError, match="Missing"):
        registry.project(extension, "Missing")
    tc_ui_document_destroy(document)
