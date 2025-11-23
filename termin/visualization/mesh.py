"""GPU mesh helper built on top of :mod:`termin.mesh` geometry."""

from __future__ import annotations

from typing import Dict

from termin.mesh.mesh import Mesh3
from .entity import RenderContext
from .backends.base import MeshHandle


class MeshDrawable:
    """Uploads CPU mesh data to GPU buffers and issues draw commands."""

    def __init__(self, mesh: Mesh3):
        self._mesh = mesh
        if self._mesh.vertex_normals is None:
            self._mesh.compute_vertex_normals()
        self._context_resources: Dict[int, MeshHandle] = {}

    def upload(self, context: RenderContext):
        ctx = context.context_key
        if ctx in self._context_resources:
            return
        handle = context.graphics.create_mesh(self._mesh)
        self._context_resources[ctx] = handle

    def draw(self, context: RenderContext):
        ctx = context.context_key
        if ctx not in self._context_resources:
            self.upload(context)
        handle = self._context_resources[ctx]
        handle.draw()

    def delete(self):
        for handle in self._context_resources.values():
            handle.delete()
        self._context_resources.clear()
    
    def serialize(self):
        return {"mesh": self._mesh.source_path}

    @classmethod
    def deserialize(cls, data, context):
        mesh = context.load_mesh(data["mesh"])
        return cls(mesh)

    @staticmethod
    def from_vertices_indices(vertices, indices, primitive_type="triangles"):
        mesh = Mesh(vertices, indices)
        return MeshDrawable(mesh)

    def interleaved_buffer(self):
        return self._mesh.interleaved_buffer()
    
    def get_vertex_layout(self):
        return self._mesh.get_vertex_layout()

class Mesh2Drawable:
    """GPU mesh helper for 2D meshes."""

    def __init__(self, mesh: Mesh2):
        self._mesh = mesh
        self._context_resources: Dict[int, MeshHandle] = {}

    def upload(self, context: RenderContext):
        ctx = context.context_key
        if ctx in self._context_resources:
            return
        handle = context.graphics.create_mesh(self._mesh)
        self._context_resources[ctx] = handle

    def draw(self, context: RenderContext):
        ctx = context.context_key
        if ctx not in self._context_resources:
            self.upload(context)
        handle = self._context_resources[ctx]
        handle.draw()

    def delete(self):
        for handle in self._context_resources.values():
            handle.delete()
        self._context_resources.clear()

    def serialize(self):
        return {"mesh": self._mesh.source_path}

    @classmethod
    def deserialize(cls, data, context):
        mesh = context.load_mesh(data["mesh"])
        return cls(mesh)

    @staticmethod
    def from_vertices_indices(vertices, indices, primitive_type="lines"):
        mesh = Mesh2(vertices, indices)
        return Mesh2Drawable(mesh)

    def interleaved_buffer(self):
        return self._mesh.interleaved_buffer()
    
    def get_vertex_layout(self):
        return self._mesh.get_vertex_layout()