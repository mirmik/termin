"""File serialization for the standalone termin-csg CAD tool."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from termin.csg.procedural_document import ProceduralMeshDocument
from termin.csg.viewer_camera import OrbitCamera


CAD_STATE_SCHEMA = "termin.csg.cad.state"
CAD_STATE_VERSION = 1
CAD_STATE_FILTER = "termin-csg CAD | *.tcsg.json;;JSON | *.json;;All files | *.*"


SelectionData = tuple[str, str]


@dataclass
class CameraState:
    target: tuple[float, float, float]
    distance: float
    yaw: float
    pitch: float
    fov_y: float
    near: float
    far: float

    @classmethod
    def from_camera(cls, camera: OrbitCamera) -> "CameraState":
        target = camera.target
        return cls(
            target=(float(target[0]), float(target[1]), float(target[2])),
            distance=float(camera.distance),
            yaw=float(camera.yaw),
            pitch=float(camera.pitch),
            fov_y=float(camera.fov_y),
            near=float(camera.near),
            far=float(camera.far),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "CameraState":
        target = data.get("target", (0.0, 0.0, 0.0))
        return cls(
            target=(float(target[0]), float(target[1]), float(target[2])),
            distance=float(data.get("distance", 8.0)),
            yaw=float(data.get("yaw", 0.7853981633974483)),
            pitch=float(data.get("pitch", 0.4886921905584123)),
            fov_y=float(data.get("fov_y", 0.7853981633974483)),
            near=float(data.get("near", 0.01)),
            far=float(data.get("far", 100.0)),
        )

    def apply_to(self, camera: OrbitCamera) -> None:
        camera.target = self.target
        camera.distance = self.distance
        camera.yaw = self.yaw
        camera.pitch = self.pitch
        camera.fov_y = self.fov_y
        camera.near = self.near
        camera.far = self.far

    def to_dict(self) -> dict:
        return {
            "target": list(self.target),
            "distance": self.distance,
            "yaw": self.yaw,
            "pitch": self.pitch,
            "fov_y": self.fov_y,
            "near": self.near,
            "far": self.far,
        }


@dataclass
class CadState:
    document: ProceduralMeshDocument
    camera: CameraState
    selection: SelectionData | None = None

    @classmethod
    def from_app_state(
        cls,
        document: ProceduralMeshDocument,
        camera: OrbitCamera,
        selection: SelectionData | None,
    ) -> "CadState":
        return cls(
            document=document,
            camera=CameraState.from_camera(camera),
            selection=selection,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "CadState":
        schema = str(data.get("schema", ""))
        if schema != CAD_STATE_SCHEMA:
            raise ValueError(f"unsupported termin-csg CAD state schema '{schema}'")

        version = int(data.get("version", 0))
        if version != CAD_STATE_VERSION:
            raise ValueError(f"unsupported termin-csg CAD state version {version}")

        selection = _selection_from_dict(data.get("selection"))
        return cls(
            document=ProceduralMeshDocument.from_dict(data.get("document", {})),
            camera=CameraState.from_dict(data.get("camera", {})),
            selection=selection,
        )

    def to_dict(self) -> dict:
        return {
            "schema": CAD_STATE_SCHEMA,
            "version": CAD_STATE_VERSION,
            "document": self.document.to_dict(),
            "camera": self.camera.to_dict(),
            "selection": _selection_to_dict(self.selection),
        }


def load_cad_state(path: str | Path) -> CadState:
    state_path = Path(path).expanduser()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("termin-csg CAD state root must be a JSON object")
    return CadState.from_dict(data)


def save_cad_state(path: str | Path, state: CadState) -> Path:
    state_path = _normalized_state_path(Path(path).expanduser())
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state_path


def _normalized_state_path(path: Path) -> Path:
    if path.suffix:
        return path
    return path.with_suffix(".tcsg.json")


def _selection_from_dict(data) -> SelectionData | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("termin-csg CAD state selection must be an object or null")
    return (str(data.get("kind", "")), str(data.get("id", "")))


def _selection_to_dict(selection: SelectionData | None) -> dict | None:
    if selection is None:
        return None
    return {
        "kind": selection[0],
        "id": selection[1],
    }


__all__ = [
    "CAD_STATE_FILTER",
    "CAD_STATE_SCHEMA",
    "CAD_STATE_VERSION",
    "CadState",
    "CameraState",
    "load_cad_state",
    "save_cad_state",
]
