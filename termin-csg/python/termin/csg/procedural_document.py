"""Small editable document model for procedural CSG construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from uuid import uuid4

from tcbase import log

Vec2Data = tuple[float, float]
Vec3Data = tuple[float, float, float]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _v_sub(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _v_add(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _v_mul(a: Vec3Data, k: float) -> Vec3Data:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec3Data, b: Vec3Data) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3Data) -> float:
    return sqrt(_dot(a, a))


def _normalized(a: Vec3Data, fallback: Vec3Data) -> Vec3Data:
    n = _norm(a)
    if n < 1e-9:
        return fallback
    return (a[0] / n, a[1] / n, a[2] / n)


def _as_vec3(value) -> Vec3Data:
    return (float(value[0]), float(value[1]), float(value[2]))


def _as_vec2(value) -> Vec2Data:
    return (float(value[0]), float(value[1]))


@dataclass
class ProceduralPlane:
    origin: Vec3Data = (0.0, 0.0, 0.0)
    x_axis: Vec3Data = (1.0, 0.0, 0.0)
    y_axis: Vec3Data = (0.0, 1.0, 0.0)

    @property
    def normal(self) -> Vec3Data:
        return _normalized(_cross(self.x_axis, self.y_axis), (0.0, 0.0, 1.0))

    @classmethod
    def from_world_points(cls, points: list[Vec3Data]) -> "ProceduralPlane":
        if len(points) < 2:
            return cls()

        origin = points[0]
        x_axis = _normalized(_v_sub(points[1], origin), (1.0, 0.0, 0.0))
        normal = (0.0, 0.0, 1.0)
        for point in points[2:]:
            candidate = _cross(x_axis, _v_sub(point, origin))
            if _norm(candidate) >= 1e-6:
                normal = _normalized(candidate, (0.0, 0.0, 1.0))
                break

        y_axis = _normalized(_cross(normal, x_axis), (0.0, 1.0, 0.0))
        return cls(origin=origin, x_axis=x_axis, y_axis=y_axis)

    def project(self, point: Vec3Data) -> Vec2Data:
        rel = _v_sub(point, self.origin)
        return (_dot(rel, self.x_axis), _dot(rel, self.y_axis))

    def unproject(self, point: Vec2Data) -> Vec3Data:
        return _v_add(
            self.origin,
            _v_add(_v_mul(self.x_axis, point[0]), _v_mul(self.y_axis, point[1])),
        )

    def to_dict(self) -> dict:
        return {
            "origin": list(self.origin),
            "x_axis": list(self.x_axis),
            "y_axis": list(self.y_axis),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralPlane":
        return cls(
            origin=_as_vec3(data.get("origin", (0.0, 0.0, 0.0))),
            x_axis=_as_vec3(data.get("x_axis", (1.0, 0.0, 0.0))),
            y_axis=_as_vec3(data.get("y_axis", (0.0, 1.0, 0.0))),
        )


@dataclass
class ContourDocument:
    id: str = field(default_factory=lambda: _new_id("contour"))
    name: str = "Contour"
    points: list[Vec2Data] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "points": [[p[0], p[1]] for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContourDocument":
        return cls(
            id=str(data.get("id", _new_id("contour"))),
            name=str(data.get("name", "Contour")),
            points=[_as_vec2(p) for p in data.get("points", [])],
        )


@dataclass
class SketchItemDocument:
    id: str = field(default_factory=lambda: _new_id("sketch"))
    name: str = "Sketch"
    plane: ProceduralPlane = field(default_factory=ProceduralPlane)
    contours: list[ContourDocument] = field(default_factory=list)

    def add_contour_from_world_points(self, points: list[Vec3Data]) -> ContourDocument | None:
        if len(points) < 3:
            log.error(f"[ProceduralMeshDocument] contour needs at least 3 points, got {len(points)}")
            return None
        contour = ContourDocument(
            name=f"Contour {len(self.contours) + 1}",
            points=[self.plane.project(point) for point in points],
        )
        self.contours.append(contour)
        return contour

    def contour_world_points(self, contour: ContourDocument) -> list[Vec3Data]:
        return [self.plane.unproject(point) for point in contour.points]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": "sketch",
            "plane": self.plane.to_dict(),
            "contours": [contour.to_dict() for contour in self.contours],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SketchItemDocument":
        return cls(
            id=str(data.get("id", _new_id("sketch"))),
            name=str(data.get("name", "Sketch")),
            plane=ProceduralPlane.from_dict(data.get("plane", {})),
            contours=[ContourDocument.from_dict(c) for c in data.get("contours", [])],
        )


@dataclass
class OperationDocument:
    id: str = field(default_factory=lambda: _new_id("operation"))
    name: str = "Operation"
    kind: str = "unknown"
    inputs: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "inputs": self.inputs[:],
            "params": dict(self.params),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OperationDocument":
        return cls(
            id=str(data.get("id", _new_id("operation"))),
            name=str(data.get("name", "Operation")),
            kind=str(data.get("kind", "unknown")),
            inputs=[str(item) for item in data.get("inputs", [])],
            params=dict(data.get("params", {})),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class ProceduralMeshDocument:
    version: int = 1
    items: list[SketchItemDocument] = field(default_factory=list)
    operations: list[OperationDocument] = field(default_factory=list)

    def ensure_sketch_for_world_points(self, points: list[Vec3Data]) -> SketchItemDocument:
        if self.items:
            return self.items[0]
        sketch = SketchItemDocument(plane=ProceduralPlane.from_world_points(points))
        self.items.append(sketch)
        return sketch

    def add_contour_from_world_points(self, points: list[Vec3Data]) -> ContourDocument | None:
        sketch = self.ensure_sketch_for_world_points(points)
        return sketch.add_contour_from_world_points(points)

    def add_contour_on_plane_from_world_points(
        self,
        points: list[Vec3Data],
        plane: ProceduralPlane,
    ) -> ContourDocument | None:
        if self.items:
            sketch = self.items[0]
        else:
            sketch = SketchItemDocument(plane=plane)
            self.items.append(sketch)
        return sketch.add_contour_from_world_points(points)

    def contour_count(self) -> int:
        return sum(len(item.contours) for item in self.items)

    def contour_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self.items:
            for contour in item.contours:
                ids.append(contour.id)
        return ids

    def find_sketch(self, sketch_id: str) -> SketchItemDocument | None:
        for item in self.items:
            if item.id == sketch_id:
                return item
        return None

    def used_source_sketch_ids(self) -> set[str]:
        ids: set[str] = set()
        for operation in self.operations:
            source_id = operation.params.get("source_sketch_id", "")
            if source_id:
                ids.add(str(source_id))
        return ids

    def add_extrude_operation(
        self,
        height: float = 1.0,
        contour_ids: list[str] | None = None,
    ) -> OperationDocument | None:
        inputs = contour_ids if contour_ids is not None else self.contour_ids()
        if not inputs:
            log.error("[ProceduralMeshDocument] cannot create extrude operation: no contours")
            return None
        operation = OperationDocument(
            name=f"Extrude {len(self.operations) + 1}",
            kind="extrude",
            inputs=inputs[:],
            params={
                "height": float(height),
                "direction": "plane_normal",
                "mode": "new_body",
            },
        )
        self.operations.append(operation)
        return operation

    def add_extrude_operation_for_sketch(
        self,
        sketch_id: str,
        height: float = 1.0,
    ) -> OperationDocument | None:
        sketch = self.find_sketch(sketch_id)
        if sketch is None:
            log.error(f"[ProceduralMeshDocument] cannot create extrude operation: sketch not found '{sketch_id}'")
            return None
        contour_ids = [contour.id for contour in sketch.contours]
        if not contour_ids:
            log.error(f"[ProceduralMeshDocument] cannot create extrude operation: sketch has no contours '{sketch_id}'")
            return None
        operation = self.add_extrude_operation(height=height, contour_ids=contour_ids)
        if operation is None:
            return None
        operation.params["source_sketch_id"] = sketch.id
        return operation

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "items": [item.to_dict() for item in self.items],
            "operations": [operation.to_dict() for operation in self.operations],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralMeshDocument":
        items: list[SketchItemDocument] = []
        for item in data.get("items", []):
            if item.get("kind", "sketch") == "sketch":
                items.append(SketchItemDocument.from_dict(item))
        return cls(
            version=int(data.get("version", 1)),
            items=items,
            operations=[OperationDocument.from_dict(op) for op in data.get("operations", [])],
        )


__all__ = [
    "ContourDocument",
    "OperationDocument",
    "ProceduralMeshDocument",
    "ProceduralPlane",
    "SketchItemDocument",
]
