"""Build profile stage of the native editor composition."""

from collections.abc import Callable
from pathlib import Path

from termin.editor_core.build_profiles_model import (
    BuildProfileAction,
    BuildProfileStorePersistence,
    BuildProfilesController,
)
from termin.editor_core.project_build_controller import ProjectBuildController
from termin.editor_native.build_profiles_window import (
    build_native_build_profiles_window,
    default_build_profile_templates,
)


def configure_native_build_profiles(
    *,
    project_file: str | Path | None,
    project_stage,
    document,
    editor_viewport,
    shell,
    scene_file_controller,
    settings_controller,
    settings_saved,
    request_editor_render: Callable[[], None],
    present_build_output: Callable[[str], None],
):
    project_build_controller = None
    build_profiles_window = None
    project_build_commands: dict[int, Callable[[], None]] = {}
    profile_command_actions = {
        shell.build_selected_profile_command: BuildProfileAction.BUILD,
        shell.run_selected_profile_command: BuildProfileAction.RUN,
        shell.install_selected_profile_command: BuildProfileAction.INSTALL,
        shell.launch_selected_profile_command: BuildProfileAction.LAUNCH,
    }
    profile_action_commands = {
        BuildProfileAction.BUILD: shell.build_selected_profile_command,
        BuildProfileAction.RUN: shell.run_selected_profile_command,
        BuildProfileAction.INSTALL: shell.install_selected_profile_command,
        BuildProfileAction.LAUNCH: shell.launch_selected_profile_command,
    }
    if project_file is not None:
        build_project_root = Path(project_file).resolve().parent
        build_profiles_window_ref = [None]

        def present_profile_output(message: str) -> None:
            present_build_output(message)
            window = build_profiles_window_ref[0]
            if window is not None:
                window.append_output(message)

        project_build_controller = ProjectBuildController(
            save_scene=scene_file_controller.save_scene,
            on_output=present_profile_output,
            toolchain_settings=settings_controller.toolchain_context,
        )
        profiles_controller = BuildProfilesController(
            BuildProfileStorePersistence(
                build_project_root,
                build_project_root / "project_settings" / "build_profiles.json",
            ),
            default_build_profile_templates(
                build_project_root,
                Path("scene.scene"),
            ),
            action_service=project_build_controller,
        )

        def update_profile_commands(snapshot) -> None:
            for action, command_id in profile_action_commands.items():
                shell.game_menu_model.set_enabled(
                    command_id,
                    snapshot.capabilities.for_action(action).enabled,
                )

        build_profiles_window = project_stage.own(
            "Build Profiles window",
            build_native_build_profiles_window(
                document,
                profiles_controller,
                viewport=editor_viewport,
                request_render=request_editor_render,
                on_snapshot=update_profile_commands,
            ),
            cleanup=lambda: build_profiles_window.close(),
        )
        build_profiles_window_ref[0] = build_profiles_window
        settings_saved.handlers.append(build_profiles_window.refresh)
        project_build_commands[shell.build_profiles_command] = build_profiles_window.show
        project_build_commands.update(
            {
                command_id: (lambda action=action: build_profiles_window.execute(action))
                for command_id, action in profile_command_actions.items()
            }
        )
    else:
        for command_id in (
            shell.build_profiles_command,
            *profile_command_actions,
        ):
            shell.game_menu_model.set_enabled(command_id, False)

    return project_build_controller, build_profiles_window, project_build_commands
