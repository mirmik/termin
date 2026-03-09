import unittest

from termin.editor.undo_stack import UndoStack, UndoCommand


class CounterCommand(UndoCommand):
    """
    Простая команда: сдвиг целочисленного счётчика на delta.
    Используется для базовых тестов undo/redo.
    """

    def __init__(self, counter, delta: int, text: str = "") -> None:
        super().__init__(text or f"delta {delta}")
        self.counter = counter
        self.delta = delta

    def do(self) -> None:
        self.counter[0] += self.delta

    def undo(self) -> None:
        self.counter[0] -= self.delta


class MergeCounterCommand(UndoCommand):
    """
    Команда, меняющая счётчик с одного значения на другое.
    Поддерживает слияние с "соседкой": два последовательных изменения
    одной и той же цели схлопываются в одну команду.
    """

    def __init__(self, counter, start_value: int, end_value: int, text: str = "") -> None:
        super().__init__(text or "merge-counter")
        self.counter = counter
        self.start_value = start_value
        self.end_value = end_value

    def do(self) -> None:
        self.counter[0] = self.end_value

    def undo(self) -> None:
        self.counter[0] = self.start_value

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Поглощаем соседку, если:
        - она тоже MergeCounterCommand,
        - ссылается на тот же counter.

        Семантика: начальное значение остаётся старым (self.start_value),
        конечное обновляется до более нового (other.end_value).
        """
        if not isinstance(other, MergeCounterCommand):
            return False
        if other.counter is not self.counter:
            return False

        # Обновляем конечное значение на более новое.
        self.end_value = other.end_value
        return True


class TestUndoStack(unittest.TestCase):
    def test_basic_push_undo_redo(self) -> None:
        counter = [0]
        stack = UndoStack()

        cmd1 = CounterCommand(counter, 1)
        cmd2 = CounterCommand(counter, 2)

        stack.push(cmd1)
        self.assertEqual(counter[0], 1)
        self.assertTrue(stack.can_undo)
        self.assertFalse(stack.can_redo)

        stack.push(cmd2)
        self.assertEqual(counter[0], 3)
        self.assertTrue(stack.can_undo)
        self.assertFalse(stack.can_redo)

        # Первый undo откатывает cmd2
        stack.undo()
        self.assertEqual(counter[0], 1)
        self.assertTrue(stack.can_undo)
        self.assertTrue(stack.can_redo)

        # Второй undo откатывает cmd1
        stack.undo()
        self.assertEqual(counter[0], 0)
        self.assertFalse(stack.can_undo)
        self.assertTrue(stack.can_redo)

        # redo по очереди возвращает команды
        stack.redo()
        self.assertEqual(counter[0], 1)
        self.assertTrue(stack.can_undo)
        self.assertTrue(stack.can_redo)

        stack.redo()
        self.assertEqual(counter[0], 3)
        self.assertTrue(stack.can_undo)
        self.assertFalse(stack.can_redo)

    def test_redo_cleared_on_new_push(self) -> None:
        counter = [0]
        stack = UndoStack()

        stack.push(CounterCommand(counter, 1))  # 1
        stack.push(CounterCommand(counter, 2))  # 3
        self.assertEqual(counter[0], 3)

        stack.undo()  # откатили 2, теперь 1
        self.assertEqual(counter[0], 1)
        self.assertTrue(stack.can_redo)

        # Новый push должен очистить ветку redo
        stack.push(CounterCommand(counter, 5))  # 6
        self.assertEqual(counter[0], 6)
        self.assertFalse(stack.can_redo)

    def test_max_depth_limits_how_far_we_can_undo(self) -> None:
        counter = [0]
        stack = UndoStack(max_depth=2)

        # Три последовательные команды
        stack.push(CounterCommand(counter, 1))  # 1
        stack.push(CounterCommand(counter, 1))  # 2
        stack.push(CounterCommand(counter, 1))  # 3

        self.assertEqual(counter[0], 3)
        # В истории должно остаться только 2 команды
        self.assertEqual(len(stack), 2)

        # Первый undo -> откатываем последнюю команду: 3 -> 2
        stack.undo()
        self.assertEqual(counter[0], 2)

        # Второй undo -> откатываем предпоследнюю: 2 -> 1
        stack.undo()
        self.assertEqual(counter[0], 1)

        # Третьего undo быть не должно — ранняя команда уже выкинута
        stack.undo()
        self.assertEqual(counter[0], 1)

    def test_merge_commands_squash_history(self) -> None:
        counter = [0]
        stack = UndoStack()

        # Первая команда: 0 -> 1
        c1 = MergeCounterCommand(counter, start_value=0, end_value=1)
        stack.push(c1)
        self.assertEqual(counter[0], 1)
        self.assertEqual(len(stack), 1)

        # Вторая команда той же природы: 1 -> 5
        # Пытаемся слить её с предыдущей.
        c2 = MergeCounterCommand(counter, start_value=1, end_value=5)
        stack.push(c2, merge=True)

        # Значение должно стать 5
        self.assertEqual(counter[0], 5)
        # В истории по-прежнему только одна команда
        self.assertEqual(len(stack), 1)

        # Undo должен вернуть к самому первому состоянию (0),
        # а не к промежуточному (1), потому что команды схлопнуты.
        stack.undo()
        self.assertEqual(counter[0], 0)
        self.assertFalse(stack.can_undo)
        self.assertTrue(stack.can_redo)

        # Redo снова приводит к финальному состоянию 5.
        stack.redo()
        self.assertEqual(counter[0], 5)

    def test_merge_rejected_for_different_targets(self) -> None:
        counter1 = [0]
        counter2 = [0]
        stack = UndoStack()

        c1 = MergeCounterCommand(counter1, 0, 1)
        stack.push(c1)

        # Команда на другой цели не должна сливаться
        c2 = MergeCounterCommand(counter2, 0, 10)
        stack.push(c2, merge=True)

        # Обе команды должны оказаться в истории
        self.assertEqual(len(stack), 2)
        self.assertEqual(counter1[0], 1)
        self.assertEqual(counter2[0], 10)

    def test_undo_redo_on_empty_stack_do_not_crash(self) -> None:
        stack = UndoStack()
        # просто проверяем, что вызовы не падают
        stack.undo()
        stack.redo()
        self.assertFalse(stack.can_undo)
        self.assertFalse(stack.can_redo)


if __name__ == "__main__":
    unittest.main()
