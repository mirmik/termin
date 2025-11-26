<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/force.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
from termin.ga201.screw import Screw2<br>
from termin.physics.indexed_matrix import IndexedVector<br>
<br>
<br>
class Force:<br>
    def __init__(self, v=[0, 0], m=0):<br>
        self._screw = Screw2(v=v, m=m)<br>
        self._linked_object = None<br>
        self._is_right_global = False<br>
        self._is_right = False<br>
<br>
    @staticmethod<br>
    def from_screw(scr):<br>
        return Force(v=scr.v, m=scr.m)<br>
<br>
    def set_right_global_type(self):<br>
        self._is_right_global = True<br>
<br>
    def set_right_type(self):<br>
        self._is_right = True<br>
<br>
    def is_right_global(self):<br>
        return self._is_right_global<br>
<br>
    def is_right(self):<br>
        return self._is_right<br>
<br>
    def set_linked_object(self, obj):<br>
        self._linked_object = obj<br>
<br>
    def screw(self):<br>
        return self._screw<br>
<br>
    def set_vector(self, v):<br>
        self._screw.set_vector(v)<br>
<br>
    def set_moment(self, m):<br>
        self._screw.set_moment(v)<br>
<br>
    def to_indexed_vector(self):<br>
        return IndexedVector(self._screw.toarray(), self._linked_object.equation_indexes())<br>
<br>
    def to_indexed_vector_rotated_by(self, motor):<br>
        return IndexedVector((self._screw.rotate_by(motor)).toarray(), self._linked_object.equation_indexes())<br>
<br>
    def unbind(self):<br>
        self._linked_object.unbind_force(self)<br>
<br>
    def clean_bind_information(self):<br>
        self._linked_object = None<br>
        self._is_left = False<br>
        self._is_right = False<br>
<br>
    def is_binded(self):<br>
        return self._linked_object is not None<br>
<br>
    def is_linked_to(self, obj):<br>
        return obj == self._linked_object<br>
<!-- END SCAT CODE -->
</body>
</html>
