from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from termin.graphics import RenderState

if TYPE_CHECKING:
    from termin._native.render import TcMaterial
