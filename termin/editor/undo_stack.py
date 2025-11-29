from __future__ import annotations

from typing import List


class UndoCommand:
    """
    Базовый класс команды для undo/redo.

    Предполагается, что:
    - do() приводит состояние в "новое" значение;
    - undo() возвращает состояние к "старому" значению;
    - merge_with() пытается слить другую команду в себя и вернуть True,
      если слияние удалось.
    """

    def __init__(self, text: str = "") -> None:
        self.text = text

    def do(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError

    def merge_with(self, other: "UndoCommand") -> bool:
        """
        Пытается поглотить соседнюю команду `other`,
        которая идёт сразу после текущей по времени.

        По умолчанию команды не сливаются.
        """
        return False


class UndoStack:
    """
    Простой стек undo/redo без привязки к GUI.

    Ветви истории:
    - _done   — уже выполненные команды (можно откатить через undo);
    - _undone — отменённые команды (можно вернуть через redo).

    max_depth > 0 ограничивает глубину истории:
    - при переполнении отбрасывается самая старая выполненная команда;
    - состояние при этом остаётся таким, какое сейчас есть,
      но вернуться "ещё дальше назад" уже нельзя.
    """

    def __init__(self, max_depth: int = 1000) -> None:
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        self._done: List[UndoCommand] = []
        self._undone: List[UndoCommand] = []
        self._max_depth = max_depth

    @property
    def can_undo(self) -> bool:
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        return bool(self._undone)

    @property
    def max_depth(self) -> int:
        return self._max_depth

    def clear(self) -> None:
        """
        Полностью очищает историю undo/redo.
        Состояние объекта, над которым выполнялись команды,
        не трогается — ответственность вызывающего.
        """
        self._done.clear()
        self._undone.clear()

    def push(self, cmd: UndoCommand, merge: bool = False) -> None:
        """
        Добавляет новую команду в стек и выполняет её.

        merge == False:
            обычное поведение — команда добавляется в историю.

        merge == True:
            пытаемся слить команду с последней выполненной:
            - если последняя команда self._done[-1].merge_with(cmd) вернула True,
              то:
                * состояние объекта приводится к новому через cmd.do();
                * сама команда cmd в историю не попадает;
                * в истории остаётся старая команда, но с обновлённым
                  внутренним состоянием (после merge_with);
            - иначе работаем как при merge == False.

        В любом случае ветка redo очищается.
        """
        if merge and self._done:
            last = self._done[-1]
            if last.merge_with(cmd):
                # Команда "поглощена": применяем только новую часть,
                # история redo всегда инвалидируется.
                cmd.do()
                self._undone.clear()
                return

        # Обычное добавление новой команды
        cmd.do()
        self._done.append(cmd)

        # Ограничение глубины истории
        if self._max_depth > 0 and len(self._done) > self._max_depth:
            # Отбрасываем самую старую команду.
            # Её уже нельзя будет отменить, но состояние остаётся текущим.
            self._done.pop(0)

        # Любая новая команда инвалидирует ветку redo
        self._undone.clear()

    def undo(self) -> None:
        """
        Откатывает последнюю выполненную команду, если такая есть.
        """
        if not self._done:
            return
        cmd = self._done.pop()
        cmd.undo()
        self._undone.append(cmd)

    def redo(self) -> None:
        """
        Повторно выполняет последнюю отменённую команду, если такая есть.
        """
        if not self._undone:
            return
        cmd = self._undone.pop()
        cmd.do()
        self._done.append(cmd)

        if self._max_depth > 0 and len(self._done) > self._max_depth:
            # Если при повторном применении переполнили историю,
            # выкидываем самую старую команду.
            self._done.pop(0)

    def __len__(self) -> int:
        """
        Количество выполненных команд в истории (ветка undo).
        """
        return len(self._done)
