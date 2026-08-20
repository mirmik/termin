from __future__ import annotations

import pytest

from termin.engine import (
    WorldController,
    list_python_world_controller_owner,
    publish_world_controllers,
    unregister_python_world_controller_owner,
)
from termin.engine._engine_native import _world_controller_type_info
from termin_modules import module_context


def test_project_owner_commit_publishes_declarations_only_after_import_boundary() -> None:
    owner = "python_world_controller_commit_test"
    package = __name__

    with module_context.module_registration_context(owner, [package]):

        class ProjectDirector(WorldController):
            world_controller_type_name = "ProjectDirector.CommitProbe"

            def start(self, context) -> None:
                pass

            def stop(self, context) -> None:
                pass

        assert _world_controller_type_info("ProjectDirector.CommitProbe") is None
        assert list_python_world_controller_owner(owner) == ["ProjectDirector.CommitProbe"]

        module_context.publish_module_owner(owner)
        info = _world_controller_type_info("ProjectDirector.CommitProbe")
        assert info is not None
        assert info["owner"] == owner
        assert info["parent"] == "WorldController"
        assert info["python_class"] is ProjectDirector

        module_context.unregister_module_owner(owner)
        assert _world_controller_type_info("ProjectDirector.CommitProbe") is None
        assert list_python_world_controller_owner(owner) == []


def test_failed_batch_validation_publishes_no_partial_descriptor() -> None:
    owner = "python_world_controller_batch_failure_test"

    class ValidDirector(WorldController):
        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class MissingStopDirector(WorldController):
        def start(self, context) -> None:
            pass

    try:
        with pytest.raises(TypeError, match="must implement stop"):
            publish_world_controllers([ValidDirector, MissingStopDirector], owner=owner)
        assert _world_controller_type_info("ValidDirector") is None
        assert _world_controller_type_info("MissingStopDirector") is None
    finally:
        unregister_python_world_controller_owner(owner)


def test_same_owner_publication_replaces_python_class_when_no_instance_is_live() -> None:
    owner = "python_world_controller_replacement_test"

    class FirstDirector(WorldController):
        world_controller_type_name = "ReplaceableProjectDirector"
        version = 1

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class SecondDirector(WorldController):
        world_controller_type_name = "ReplaceableProjectDirector"
        version = 2

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    try:
        assert publish_world_controllers([FirstDirector], owner=owner) == ["ReplaceableProjectDirector"]
        assert _world_controller_type_info("ReplaceableProjectDirector")["python_class"] is FirstDirector

        assert publish_world_controllers([SecondDirector], owner=owner) == ["ReplaceableProjectDirector"]
        assert _world_controller_type_info("ReplaceableProjectDirector")["python_class"] is SecondDirector
    finally:
        unregister_python_world_controller_owner(owner)


def test_failed_batch_restores_replaced_descriptor_and_removes_new_types() -> None:
    owner = "python_world_controller_rollback_test"
    foreign_owner = "python_world_controller_rollback_foreign_test"

    class PreviousDirector(WorldController):
        world_controller_type_name = "A.RollbackProjectDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class ReplacementDirector(WorldController):
        world_controller_type_name = "A.RollbackProjectDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class NewDirector(WorldController):
        world_controller_type_name = "B.RollbackNewDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class ForeignDirector(WorldController):
        world_controller_type_name = "Z.RollbackForeignDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    try:
        publish_world_controllers([PreviousDirector], owner=owner)
        publish_world_controllers([ForeignDirector], owner=foreign_owner)

        with pytest.raises(RuntimeError, match="owned by"):
            publish_world_controllers(
                [ReplacementDirector, NewDirector, ForeignDirector],
                owner=owner,
            )

        replacement_info = _world_controller_type_info("A.RollbackProjectDirector")
        assert replacement_info is not None
        assert replacement_info["python_class"] is PreviousDirector
        assert _world_controller_type_info("B.RollbackNewDirector") is None
        foreign_info = _world_controller_type_info("Z.RollbackForeignDirector")
        assert foreign_info is not None
        assert foreign_info["owner"] == foreign_owner
    finally:
        unregister_python_world_controller_owner(owner)
        unregister_python_world_controller_owner(foreign_owner)
