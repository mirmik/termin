import numpy
from termin.ga201.screw import Screw2
from termin.physics.indexed_matrix import IndexedVector


class Force:
    def __init__(self, v=[0, 0], m=0):
        self._screw = Screw2(v=v, m=m)
        self._linked_object = None
        self._is_right_global = False
        self._is_right = False

    @staticmethod
    def from_screw(scr):
        return Force(v=scr.v, m=scr.m)

    def set_right_global_type(self):
        self._is_right_global = True

    def set_right_type(self):
        self._is_right = True

    def is_right_global(self):
        return self._is_right_global

    def is_right(self):
        return self._is_right

    def set_linked_object(self, obj):
        self._linked_object = obj

    def screw(self):
        return self._screw

    def set_vector(self, v):
        self._screw.set_vector(v)

    def set_moment(self, m):
        self._screw.set_moment(v)

    def to_indexed_vector(self):
        return IndexedVector(self._screw.toarray(), self._linked_object.equation_indexes())

    def to_indexed_vector_rotated_by(self, motor):
        return IndexedVector((self._screw.rotate_by(motor)).toarray(), self._linked_object.equation_indexes())

    def unbind(self):
        self._linked_object.unbind_force(self)

    def clean_bind_information(self):
        self._linked_object = None
        self._is_left = False
        self._is_right = False

    def is_binded(self):
        return self._linked_object is not None

    def is_linked_to(self, obj):
        return obj == self._linked_object
