from termin.editor_core.audio_debugger_model import AudioDebuggerController
from termin.editor_core.undo_history_model import UndoHistoryController
from termin.editor_core.undo_stack import UndoCommand, UndoStack


class _Command(UndoCommand):
    def do(self) -> None:
        pass

    def undo(self) -> None:
        pass


class _AudioEngine:
    is_initialized = True
    num_channels = 3

    def get_master_volume(self):
        return 0.75

    def is_channel_playing(self, channel):
        return channel != 1

    def get_channel_volume(self, channel):
        return 0.5 + channel * 0.1

    def get_channel_position(self, channel):
        return 15.0 * channel, 2.0 + channel

    def is_channel_paused(self, channel):
        return channel == 2


def test_undo_history_controller_snapshots_done_and_undone_commands():
    stack = UndoStack()
    stack.push(_Command("first"))
    stack.push(_Command())
    stack.undo()
    controller = UndoHistoryController(stack)
    changes = []
    controller.changed.connect(changes.append)

    snapshot = controller.refresh()

    assert [(entry.index, entry.text) for entry in snapshot.done] == [(0, "first")]
    assert [(entry.index, entry.text) for entry in snapshot.undone] == [(0, "_Command")]
    assert changes == [snapshot]


def test_audio_debugger_controller_snapshots_only_active_channels():
    controller = AudioDebuggerController(_AudioEngine())

    snapshot = controller.snapshot()

    assert snapshot.initialized
    assert snapshot.master_volume == 0.75
    assert snapshot.total_channels == 3
    assert [channel.channel for channel in snapshot.channels] == [0, 2]
    assert snapshot.channels[1].paused
    assert snapshot.channels[1].angle == 30.0


def test_audio_debugger_controller_handles_uninitialized_engine():
    engine = _AudioEngine()
    engine.is_initialized = False

    assert AudioDebuggerController(engine).snapshot().channels == ()
