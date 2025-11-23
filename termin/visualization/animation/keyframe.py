from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AnimationKeyframe:
    """
    Кадр анимации в момент time.

    Любое из полей может быть None — тогда этот канал анимацией не затрагивается.
    translation: np.array shape (3,)
    rotation:    np.array shape (4,) (кватернион x, y, z, w)
    scale:       float (uniform-скейл)
    """
    time: float
    translation: Optional[np.ndarray] = None
    rotation: Optional[np.ndarray] = None
    scale: Optional[float] = None

    def __post_init__(self):
        self.time = float(self.time)

        if self.translation is not None:
            self.translation = np.asarray(self.translation, dtype=float)
            if self.translation.shape != (3,):
                raise ValueError("translation must have shape (3,)")

        if self.rotation is not None:
            self.rotation = np.asarray(self.rotation, dtype=float)
            if self.rotation.shape != (4,):
                raise ValueError("rotation (quaternion) must have shape (4,)")

        if self.scale is not None:
            self.scale = float(self.scale)
