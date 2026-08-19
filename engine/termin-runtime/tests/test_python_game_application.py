from __future__ import annotations

import pytest

from termin.runtime import (
    GameApplication,
    list_python_game_application_owner,
    publish_game_applications,
    unregister_python_game_application_owner,
)
from termin.runtime._runtime_native import _game_application_type_info
from termin_modules import module_context


def test_project_owner_commit_publishes_declarations_only_after_import_boundary() -> None:
    owner = "python_game_application_commit_test"
    package = __name__

    with module_context.module_registration_context(owner, [package]):

        class ProjectDirector(GameApplication):
            game_application_type_name = "ProjectDirector.CommitProbe"

            def start(self, context) -> None:
                pass

            def stop(self, context) -> None:
                pass

        assert _game_application_type_info("ProjectDirector.CommitProbe") is None
        assert list_python_game_application_owner(owner) == ["ProjectDirector.CommitProbe"]

        module_context.publish_module_owner(owner)
        info = _game_application_type_info("ProjectDirector.CommitProbe")
        assert info is not None
        assert info["owner"] == owner
        assert info["parent"] == "GameApplication"
        assert info["python_class"] is ProjectDirector

        module_context.unregister_module_owner(owner)
        assert _game_application_type_info("ProjectDirector.CommitProbe") is None
        assert list_python_game_application_owner(owner) == []


def test_failed_batch_validation_publishes_no_partial_descriptor() -> None:
    owner = "python_game_application_batch_failure_test"

    class ValidDirector(GameApplication):
        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class MissingStopDirector(GameApplication):
        def start(self, context) -> None:
            pass

    try:
        with pytest.raises(TypeError, match="must implement stop"):
            publish_game_applications([ValidDirector, MissingStopDirector], owner=owner)
        assert _game_application_type_info("ValidDirector") is None
        assert _game_application_type_info("MissingStopDirector") is None
    finally:
        unregister_python_game_application_owner(owner)


def test_same_owner_publication_replaces_python_class_when_no_instance_is_live() -> None:
    owner = "python_game_application_replacement_test"

    class FirstDirector(GameApplication):
        game_application_type_name = "ReplaceableProjectDirector"
        version = 1

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class SecondDirector(GameApplication):
        game_application_type_name = "ReplaceableProjectDirector"
        version = 2

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    try:
        assert publish_game_applications([FirstDirector], owner=owner) == ["ReplaceableProjectDirector"]
        assert _game_application_type_info("ReplaceableProjectDirector")["python_class"] is FirstDirector

        assert publish_game_applications([SecondDirector], owner=owner) == ["ReplaceableProjectDirector"]
        assert _game_application_type_info("ReplaceableProjectDirector")["python_class"] is SecondDirector
    finally:
        unregister_python_game_application_owner(owner)


def test_failed_batch_restores_replaced_descriptor_and_removes_new_types() -> None:
    owner = "python_game_application_rollback_test"
    foreign_owner = "python_game_application_rollback_foreign_test"

    class PreviousDirector(GameApplication):
        game_application_type_name = "A.RollbackProjectDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class ReplacementDirector(GameApplication):
        game_application_type_name = "A.RollbackProjectDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class NewDirector(GameApplication):
        game_application_type_name = "B.RollbackNewDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    class ForeignDirector(GameApplication):
        game_application_type_name = "Z.RollbackForeignDirector"

        def start(self, context) -> None:
            pass

        def stop(self, context) -> None:
            pass

    try:
        publish_game_applications([PreviousDirector], owner=owner)
        publish_game_applications([ForeignDirector], owner=foreign_owner)

        with pytest.raises(RuntimeError, match="owned by"):
            publish_game_applications(
                [ReplacementDirector, NewDirector, ForeignDirector],
                owner=owner,
            )

        replacement_info = _game_application_type_info("A.RollbackProjectDirector")
        assert replacement_info is not None
        assert replacement_info["python_class"] is PreviousDirector
        assert _game_application_type_info("B.RollbackNewDirector") is None
        foreign_info = _game_application_type_info("Z.RollbackForeignDirector")
        assert foreign_info is not None
        assert foreign_info["owner"] == foreign_owner
    finally:
        unregister_python_game_application_owner(owner)
        unregister_python_game_application_owner(foreign_owner)
