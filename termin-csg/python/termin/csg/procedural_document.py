"""Small editable document model for procedural CSG construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from uuid import uuid4

from tcbase import log

from termin.csg.operation_specs import (
    BOOLEAN_OPERATION_KINDS,
    OPERATION_KIND_WALL,
    PRIMITIVE_KINDS,
    PRIMITIVE_OPERATION_KIND,
    boolean_operation_label,
    extrude_default_params,
    operation_transform_defaults,
    primitive_default_params,
    primitive_label,
    wall_default_params,
)

Vec2Data = tuple[float, float]
Vec3Data = tuple[float, float, float]
CONTOUR_ROLE_OUTER = "outer"
CONTOUR_ROLE_HOLE = "hole"
CONTOUR_ROLES = {CONTOUR_ROLE_OUTER, CONTOUR_ROLE_HOLE}


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


def _validated_contour_role(role: str) -> str:
    contour_role = str(role)
    if contour_role not in CONTOUR_ROLES:
        log.error(f"[ProceduralMeshDocument] invalid contour role '{role}', using outer")
        return CONTOUR_ROLE_OUTER
    return contour_role


def _validated_primitive_kind(kind: str) -> str:
    primitive_kind = str(kind)
    if primitive_kind not in PRIMITIVE_KINDS:
        log.error(f"[ProceduralMeshDocument] invalid primitive kind '{kind}'")
        return ""
    return primitive_kind


@dataclass
class ProceduralPlane:
    origin: Vec3Data = (0.0, 0.0, 0.0)
    x_axis: Vec3Data = (1.0, 0.0, 0.0)
    y_axis: Vec3Data = (0.0, 1.0, 0.0)

    @property
    def normal(self) -> Vec3Data:
        return _normalized(_cross(self.x_axis, self.y_axis), (0.0, 0.0, 1.0))

    @classmethod
    def from_points(cls, points: list[Vec3Data]) -> "ProceduralPlane":
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
    role: str = CONTOUR_ROLE_OUTER
    parent_contour_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "points": [[p[0], p[1]] for p in self.points],
            "role": self.role,
            "parent_contour_id": self.parent_contour_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContourDocument":
        role = str(data.get("role", CONTOUR_ROLE_OUTER))
        if role not in CONTOUR_ROLES:
            log.error(f"[ProceduralMeshDocument] invalid contour role '{role}', using outer")
            role = CONTOUR_ROLE_OUTER
        parent_value = data.get("parent_contour_id")
        parent_contour_id = None if parent_value is None else str(parent_value)
        return cls(
            id=str(data.get("id", _new_id("contour"))),
            name=str(data.get("name", "Contour")),
            points=[_as_vec2(p) for p in data.get("points", [])],
            role=role,
            parent_contour_id=parent_contour_id,
        )


@dataclass
class SketchPathDocument:
    id: str = field(default_factory=lambda: _new_id("path"))
    name: str = "Path"
    points: list[Vec2Data] = field(default_factory=list)
    closed: bool = False
    purpose: str = "wall"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "points": [[p[0], p[1]] for p in self.points],
            "closed": bool(self.closed),
            "purpose": self.purpose,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SketchPathDocument":
        return cls(
            id=str(data.get("id", _new_id("path"))),
            name=str(data.get("name", "Path")),
            points=[_as_vec2(p) for p in data.get("points", [])],
            closed=bool(data.get("closed", False)),
            purpose=str(data.get("purpose", "wall")),
        )


@dataclass
class SketchItemDocument:
    id: str = field(default_factory=lambda: _new_id("sketch"))
    name: str = "Sketch"
    plane: ProceduralPlane = field(default_factory=ProceduralPlane)
    contours: list[ContourDocument] = field(default_factory=list)
    paths: list[SketchPathDocument] = field(default_factory=list)

    def add_contour_from_points(
        self,
        points: list[Vec3Data],
        role: str = CONTOUR_ROLE_OUTER,
        parent_contour_id: str | None = None,
    ) -> ContourDocument | None:
        if len(points) < 3:
            log.error(f"[ProceduralMeshDocument] contour needs at least 3 points, got {len(points)}")
            return None
        contour_role = _validated_contour_role(role)
        if contour_role == CONTOUR_ROLE_OUTER:
            parent_id = None
        else:
            parent_id = str(parent_contour_id) if parent_contour_id else ""
            parent = self.find_contour(parent_id)
            if parent is None or parent.role != CONTOUR_ROLE_OUTER:
                log.error(
                    "[ProceduralMeshDocument] cannot create hole contour: "
                    f"outer parent not found '{parent_id}'"
                )
                return None
        contour = ContourDocument(
            name=f"Contour {len(self.contours) + 1}",
            points=[self.plane.project(point) for point in points],
            role=contour_role,
            parent_contour_id=parent_id if contour_role == CONTOUR_ROLE_HOLE else None,
        )
        self.contours.append(contour)
        return contour

    def contour_points(self, contour: ContourDocument) -> list[Vec3Data]:
        return [self.plane.unproject(point) for point in contour.points]

    def add_path_from_points(
        self,
        points: list[Vec3Data],
        purpose: str = "wall",
        closed: bool = False,
    ) -> SketchPathDocument | None:
        if len(points) < 2:
            log.error(f"[ProceduralMeshDocument] path needs at least 2 points, got {len(points)}")
            return None
        path = SketchPathDocument(
            name=f"Path {len(self.paths) + 1}",
            points=[self.plane.project(point) for point in points],
            closed=bool(closed),
            purpose=str(purpose),
        )
        self.paths.append(path)
        return path

    def path_points(self, path: SketchPathDocument) -> list[Vec3Data]:
        return [self.plane.unproject(point) for point in path.points]

    def find_contour(self, contour_id: str) -> ContourDocument | None:
        for contour in self.contours:
            if contour.id == contour_id:
                return contour
        return None

    def find_path(self, path_id: str) -> SketchPathDocument | None:
        for path in self.paths:
            if path.id == path_id:
                return path
        return None

    def outer_contours(self) -> list[ContourDocument]:
        return [contour for contour in self.contours if contour.role == CONTOUR_ROLE_OUTER]

    def hole_contours_for_outer(self, outer_contour_id: str) -> list[ContourDocument]:
        return [
            contour
            for contour in self.contours
            if contour.role == CONTOUR_ROLE_HOLE and contour.parent_contour_id == outer_contour_id
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": "sketch",
            "plane": self.plane.to_dict(),
            "contours": [contour.to_dict() for contour in self.contours],
            "paths": [path.to_dict() for path in self.paths],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SketchItemDocument":
        return cls(
            id=str(data.get("id", _new_id("sketch"))),
            name=str(data.get("name", "Sketch")),
            plane=ProceduralPlane.from_dict(data.get("plane", {})),
            contours=[ContourDocument.from_dict(c) for c in data.get("contours", [])],
            paths=[SketchPathDocument.from_dict(p) for p in data.get("paths", [])],
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

    def add_contour_from_points(self, points: list[Vec3Data]) -> ContourDocument | None:
        return self.add_contour_on_plane_from_points(points, ProceduralPlane.from_points(points))

    def add_contour_on_plane_from_points(
        self,
        points: list[Vec3Data],
        plane: ProceduralPlane,
        role: str = CONTOUR_ROLE_OUTER,
        parent_contour_id: str | None = None,
    ) -> ContourDocument | None:
        sketch = SketchItemDocument(
            name=f"Sketch {len(self.items) + 1}",
            plane=plane,
        )
        contour = sketch.add_contour_from_points(points, role=role, parent_contour_id=parent_contour_id)
        if contour is None:
            return None
        self.items.append(sketch)
        return contour

    def add_contour_to_sketch_from_points(
        self,
        sketch_id: str,
        points: list[Vec3Data],
        role: str = CONTOUR_ROLE_OUTER,
        parent_contour_id: str | None = None,
    ) -> ContourDocument | None:
        sketch = self.find_sketch(sketch_id)
        if sketch is None:
            log.error(f"[ProceduralMeshDocument] cannot add contour: sketch not found '{sketch_id}'")
            return None
        return sketch.add_contour_from_points(points, role=role, parent_contour_id=parent_contour_id)

    def add_path_on_plane_from_points(
        self,
        points: list[Vec3Data],
        plane: ProceduralPlane,
        purpose: str = "wall",
        closed: bool = False,
    ) -> SketchPathDocument | None:
        sketch = SketchItemDocument(
            name=f"Sketch {len(self.items) + 1}",
            plane=plane,
        )
        path = sketch.add_path_from_points(points, purpose=purpose, closed=closed)
        if path is None:
            return None
        self.items.append(sketch)
        return path

    def add_path_to_sketch_from_points(
        self,
        sketch_id: str,
        points: list[Vec3Data],
        purpose: str = "wall",
        closed: bool = False,
    ) -> SketchPathDocument | None:
        sketch = self.find_sketch(sketch_id)
        if sketch is None:
            log.error(f"[ProceduralMeshDocument] cannot add path: sketch not found '{sketch_id}'")
            return None
        return sketch.add_path_from_points(points, purpose=purpose, closed=closed)

    def find_sketch_id_for_contour(self, contour_id: str) -> str:
        for item in self.items:
            for contour in item.contours:
                if contour.id == contour_id:
                    return item.id
        return ""

    def find_contour_ref(self, contour_id: str) -> tuple[SketchItemDocument, ContourDocument] | None:
        for item in self.items:
            for contour in item.contours:
                if contour.id == contour_id:
                    return (item, contour)
        return None

    def find_sketch_id_for_path(self, path_id: str) -> str:
        for item in self.items:
            for path in item.paths:
                if path.id == path_id:
                    return item.id
        return ""

    def find_path_ref(self, path_id: str) -> tuple[SketchItemDocument, SketchPathDocument] | None:
        for item in self.items:
            for path in item.paths:
                if path.id == path_id:
                    return (item, path)
        return None

    def contour_count(self) -> int:
        return sum(len(item.contours) for item in self.items)

    def path_count(self) -> int:
        return sum(len(item.paths) for item in self.items)

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

    def find_operation(self, operation_id: str) -> OperationDocument | None:
        for operation in self.operations:
            if operation.id == operation_id:
                return operation
        return None

    def used_source_sketch_ids(self) -> set[str]:
        ids: set[str] = set()
        for operation in self.operations:
            source_id = operation.params.get("source_sketch_id", "")
            if operation.enabled and source_id:
                ids.add(str(source_id))
            source_path_id = operation.params.get("source_path_id", "")
            if operation.enabled and source_path_id:
                sketch_id = self.find_sketch_id_for_path(str(source_path_id))
                if sketch_id:
                    ids.add(sketch_id)
        return ids

    def used_input_operation_ids(self) -> set[str]:
        ids: set[str] = set()
        operation_ids = {operation.id for operation in self.operations}
        for operation in self.operations:
            if not operation.enabled or operation.kind not in BOOLEAN_OPERATION_KINDS:
                continue
            for input_id in operation.inputs:
                if input_id in operation_ids:
                    ids.add(input_id)
        return ids

    def add_extrude_operation(
        self,
        height: float = 1.0,
        contour_ids: list[str] | None = None,
        vector: Vec3Data | None = None,
    ) -> OperationDocument | None:
        inputs = contour_ids if contour_ids is not None else self.contour_ids()
        if not inputs:
            log.error("[ProceduralMeshDocument] cannot create extrude operation: no contours")
            return None
        extrusion_vector = (0.0, 0.0, float(height)) if vector is None else _as_vec3(vector)
        operation = OperationDocument(
            name=f"Extrude {len(self.operations) + 1}",
            kind="extrude",
            inputs=inputs[:],
            params=extrude_default_params(extrusion_vector),
        )
        self.operations.append(operation)
        return operation

    def add_extrude_operation_for_sketch(
        self,
        sketch_id: str,
        height: float = 1.0,
        vector: Vec3Data | None = None,
    ) -> OperationDocument | None:
        sketch = self.find_sketch(sketch_id)
        if sketch is None:
            log.error(f"[ProceduralMeshDocument] cannot create extrude operation: sketch not found '{sketch_id}'")
            return None
        contour_ids = [contour.id for contour in sketch.outer_contours()]
        if not contour_ids:
            log.error(f"[ProceduralMeshDocument] cannot create extrude operation: sketch has no outer contours '{sketch_id}'")
            return None
        extrusion_vector = _v_mul(sketch.plane.normal, float(height)) if vector is None else _as_vec3(vector)
        operation = self.add_extrude_operation(
            height=height,
            contour_ids=contour_ids,
            vector=extrusion_vector,
        )
        if operation is None:
            return None
        operation.params["source_sketch_id"] = sketch.id
        return operation

    def add_wall_operation_for_path(
        self,
        path_id: str,
        height: float = 3.0,
        thickness: float = 0.2,
        alignment: str = "center",
    ) -> OperationDocument | None:
        path_ref = self.find_path_ref(path_id)
        if path_ref is None:
            log.error(f"[ProceduralMeshDocument] cannot create wall operation: path not found '{path_id}'")
            return None
        sketch, path = path_ref
        if len(path.points) < 2:
            log.error(
                "[ProceduralMeshDocument] cannot create wall operation: "
                f"path needs at least 2 points path='{path.id}'"
            )
            return None
        operation = OperationDocument(
            name=f"Wall {len(self.operations) + 1}",
            kind=OPERATION_KIND_WALL,
            inputs=[path.id],
            params={
                **wall_default_params(height=height, thickness=thickness, alignment=alignment),
                "source_path_id": path.id,
                "source_sketch_id": sketch.id,
            },
        )
        self.operations.append(operation)
        return operation

    def add_primitive_operation(
        self,
        kind: str,
        params: dict | None = None,
    ) -> OperationDocument | None:
        primitive_kind = _validated_primitive_kind(kind)
        if not primitive_kind:
            return None
        operation_params = primitive_default_params(primitive_kind)
        if params:
            operation_params.update(dict(params))
            operation_params["primitive_kind"] = primitive_kind
        label = primitive_label(primitive_kind)
        operation = OperationDocument(
            name=f"{label} {len(self.operations) + 1}",
            kind=PRIMITIVE_OPERATION_KIND,
            inputs=[],
            params=operation_params,
        )
        self.operations.append(operation)
        return operation

    def add_boolean_operation(
        self,
        kind: str,
        input_operation_ids: list[str],
    ) -> OperationDocument | None:
        operation_kind = "subtract" if kind == "substract" else str(kind)
        if operation_kind not in BOOLEAN_OPERATION_KINDS:
            log.error(f"[ProceduralMeshDocument] cannot create boolean operation: invalid kind '{kind}'")
            return None
        if len(input_operation_ids) < 2:
            log.error(
                "[ProceduralMeshDocument] cannot create boolean operation: "
                f"need at least 2 operation inputs, got {len(input_operation_ids)}"
            )
            return None
        existing_ids = {operation.id for operation in self.operations}
        missing = [operation_id for operation_id in input_operation_ids if operation_id not in existing_ids]
        if missing:
            log.error(f"[ProceduralMeshDocument] cannot create boolean operation: missing inputs {missing}")
            return None
        label = boolean_operation_label(operation_kind)
        operation = OperationDocument(
            name=f"{label} {len(self.operations) + 1}",
            kind=operation_kind,
            inputs=input_operation_ids[:],
            params=operation_transform_defaults(),
        )
        self.operations.append(operation)
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
    "BOOLEAN_OPERATION_KINDS",
    "CONTOUR_ROLE_HOLE",
    "CONTOUR_ROLE_OUTER",
    "CONTOUR_ROLES",
    "OperationDocument",
    "OPERATION_KIND_WALL",
    "PRIMITIVE_KINDS",
    "PRIMITIVE_OPERATION_KIND",
    "ProceduralMeshDocument",
    "ProceduralPlane",
    "SketchItemDocument",
    "SketchPathDocument",
]
