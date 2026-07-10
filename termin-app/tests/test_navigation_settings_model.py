from copy import deepcopy

import pytest

from termin.editor_core.navigation_settings_model import (
    NavigationAgentSnapshot,
    NavigationSettingsController,
)
from termin.navmesh.settings import AgentType, NavigationSettings, NAVMESH_AREA_COUNT


class _Manager:
    def __init__(self):
        self.settings = NavigationSettings(
            agent_types=[AgentType(name="Default")],
            navmesh_area_names=[f"Area {index}" for index in range(NAVMESH_AREA_COUNT)],
        )
        self.saved = 0

    def update_agent_type(self, index, value):
        self.settings.agent_types[index] = value

    def add_agent_type(self, value):
        self.settings.agent_types.append(value)

    def remove_agent_type(self, index):
        self.settings.agent_types.pop(index)

    def set_navmesh_area_name(self, index, name):
        self.settings.navmesh_area_names[index] = name

    def save(self):
        self.saved += 1
        return True


def test_navigation_settings_controller_stages_reverts_and_saves():
    manager = _Manager()
    original = deepcopy(manager.settings)
    changed = []
    controller = NavigationSettingsController(manager, on_changed=lambda: changed.append(True))
    index, _snapshot = controller.add_agent()
    controller.update_agent(index, NavigationAgentSnapshot("Small", 0.25, 1.0, 30.0, 0.2))
    names = list(controller.snapshot.area_names)
    names[3] = "  Water  "
    controller.set_area_names(tuple(names))

    assert manager.settings == original
    assert controller.revert().agents == (NavigationAgentSnapshot("Default", 0.5, 2.0, 45.0, 0.4),)

    index, _snapshot = controller.add_agent()
    controller.update_agent(index, NavigationAgentSnapshot("Small", 0.25, 1.0, 30.0, 0.2))
    names = list(controller.snapshot.area_names)
    names[3] = "  Water  "
    controller.set_area_names(tuple(names))
    saved = controller.save()

    assert [agent.name for agent in manager.settings.agent_types] == ["Default", "Small"]
    assert saved.area_names[3] == "Water"
    assert manager.saved == 1
    assert changed == [True]


def test_navigation_settings_controller_validates_draft():
    controller = NavigationSettingsController(_Manager())
    with pytest.raises(ValueError):
        controller.remove_agent(0)
    with pytest.raises(ValueError):
        controller.update_agent(0, NavigationAgentSnapshot("", 0.5, 2.0, 45.0, 0.4))
    with pytest.raises(ValueError):
        controller.set_area_names(("short",))
