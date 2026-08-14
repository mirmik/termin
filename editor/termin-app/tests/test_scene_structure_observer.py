from termin.editor_core.scene_structure_observer import SceneStructureObserver


class Subscription:
    def __init__(self) -> None:
        self.unsubscribed = False

    def unsubscribe(self) -> None:
        self.unsubscribed = True


class Scene:
    def __init__(self) -> None:
        self.callback = None
        self.subscription = Subscription()

    def subscribe_event(self, event_name, callback):
        assert event_name == "tc.scene.structure_changed"
        self.callback = callback
        return self.subscription


def test_scene_structure_observer_coalesces_and_switches_safely():
    rebuilds = []
    updates = []
    observer = SceneStructureObserver(
        lambda: rebuilds.append(True),
        lambda: updates.append(True),
    )
    first = Scene()
    second = Scene()
    observer.set_scene(first)

    first.callback(object())
    first.callback(object())
    assert observer.pending
    assert observer.poll()
    assert rebuilds == [True]
    assert len(updates) == 3
    assert not observer.poll()

    observer.set_scene(second)
    assert first.subscription.unsubscribed
    second.callback(object())
    observer.close()
    assert second.subscription.unsubscribed
    assert not observer.pending
