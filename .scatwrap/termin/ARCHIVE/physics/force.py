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
&#9;def __init__(self, v=[0, 0], m=0):<br>
&#9;&#9;self._screw = Screw2(v=v, m=m)<br>
&#9;&#9;self._linked_object = None<br>
&#9;&#9;self._is_right_global = False<br>
&#9;&#9;self._is_right = False<br>
<br>
&#9;@staticmethod<br>
&#9;def from_screw(scr):<br>
&#9;&#9;return Force(v=scr.v, m=scr.m)<br>
<br>
&#9;def set_right_global_type(self):<br>
&#9;&#9;self._is_right_global = True<br>
<br>
&#9;def set_right_type(self):<br>
&#9;&#9;self._is_right = True<br>
<br>
&#9;def is_right_global(self):<br>
&#9;&#9;return self._is_right_global<br>
<br>
&#9;def is_right(self):<br>
&#9;&#9;return self._is_right<br>
<br>
&#9;def set_linked_object(self, obj):<br>
&#9;&#9;self._linked_object = obj<br>
<br>
&#9;def screw(self):<br>
&#9;&#9;return self._screw<br>
<br>
&#9;def set_vector(self, v):<br>
&#9;&#9;self._screw.set_vector(v)<br>
<br>
&#9;def set_moment(self, m):<br>
&#9;&#9;self._screw.set_moment(v)<br>
<br>
&#9;def to_indexed_vector(self):<br>
&#9;&#9;return IndexedVector(self._screw.toarray(), self._linked_object.equation_indexes())<br>
<br>
&#9;def to_indexed_vector_rotated_by(self, motor):<br>
&#9;&#9;return IndexedVector((self._screw.rotate_by(motor)).toarray(), self._linked_object.equation_indexes())<br>
<br>
&#9;def unbind(self):<br>
&#9;&#9;self._linked_object.unbind_force(self)<br>
<br>
&#9;def clean_bind_information(self):<br>
&#9;&#9;self._linked_object = None<br>
&#9;&#9;self._is_left = False<br>
&#9;&#9;self._is_right = False<br>
<br>
&#9;def is_binded(self):<br>
&#9;&#9;return self._linked_object is not None<br>
<br>
&#9;def is_linked_to(self, obj):<br>
&#9;&#9;return obj == self._linked_object<br>
<!-- END SCAT CODE -->
</body>
</html>
