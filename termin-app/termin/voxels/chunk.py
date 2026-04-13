"""
VoxelChunk — данные одного чанка 16×16×16.
"""

from __future__ import annotations

import numpy as np
from typing import Iterator

CHUNK_SIZE = 16
CHUNK_VOLUME = CHUNK_SIZE ** 3


class VoxelChunk:
    """
    Чанк вокселей размером CHUNK_SIZE³.

    Хранит типы вокселей как uint8:
    - 0: пустой
    - 1+: заполненный (разные типы для будущего расширения)
    """

    __slots__ = ("_data", "_non_empty_count")

    def __init__(self) -> None:
        self._data: np.ndarray = np.zeros(
            (CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE),
            dtype=np.uint8
        )
        self._non_empty_count: int = 0

    @property
    def data(self) -> np.ndarray:
        """Прямой доступ к массиву данных (для быстрых операций)."""
        return self._data

    @property
    def non_empty_count(self) -> int:
        """Количество непустых вокселей."""
        return self._non_empty_count

    @property
    def is_empty(self) -> bool:
        """True если все воксели пустые."""
        return self._non_empty_count == 0

    def get(self, x: int, y: int, z: int) -> int:
        """Получить тип вокселя по локальным координатам."""
        return int(self._data[x, y, z])

    def set(self, x: int, y: int, z: int, value: int) -> None:
        """Установить тип вокселя по локальным координатам."""
        old_value = self._data[x, y, z]
        self._data[x, y, z] = value

        # Обновляем счётчик
        if old_value == 0 and value != 0:
            self._non_empty_count += 1
        elif old_value != 0 and value == 0:
            self._non_empty_count -= 1

    def fill(self, value: int) -> None:
        """Заполнить весь чанк одним значением."""
        self._data.fill(value)
        self._non_empty_count = CHUNK_VOLUME if value != 0 else 0

    def clear(self) -> None:
        """Очистить чанк."""
        self._data.fill(0)
        self._non_empty_count = 0

    def iter_non_empty(self) -> Iterator[tuple[int, int, int, int]]:
        """
        Итератор по непустым вокселям.

        Yields:
            (x, y, z, type) для каждого непустого вокселя.
        """
        indices = np.argwhere(self._data != 0)
        for x, y, z in indices:
            yield int(x), int(y), int(z), int(self._data[x, y, z])

    def recalculate_count(self) -> None:
        """Пересчитать счётчик непустых (после прямого доступа к data)."""
        self._non_empty_count = int(np.count_nonzero(self._data))

    def serialize(self) -> dict:
        """Сериализовать чанк в dict."""
        import base64
        import gzip

        compressed = gzip.compress(self._data.tobytes())
        return {
            "data": base64.b64encode(compressed).decode("ascii"),
            "count": self._non_empty_count,
        }

    @classmethod
    def deserialize(cls, data: dict) -> VoxelChunk:
        """Десериализовать чанк из dict."""
        import base64
        import gzip

        chunk = cls()
        compressed = base64.b64decode(data["data"])
        raw = gzip.decompress(compressed)
        chunk._data = np.frombuffer(raw, dtype=np.uint8).reshape(
            CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE
        ).copy()  # copy() чтобы массив был writable
        chunk._non_empty_count = data.get("count", 0)
        return chunk
