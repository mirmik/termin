<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/kinematic.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from .transform import Transform3<br>
from termin.geombase import Pose3, Screw3<br>
import numpy<br>
<br>
class KinematicTransform3(Transform3):<br>
    &quot;&quot;&quot;A Transform3 specialized for kinematic chains.&quot;&quot;&quot;<br>
    def __init__(self, name=&quot;ktrans&quot;, parent: Transform3 = None, manual_output: bool = False, local_pose=Pose3.identity()):<br>
        super().__init__(parent=None, name=name, local_pose=local_pose)<br>
<br>
        if not manual_output:<br>
            self.output = Transform3(parent=self, name=f&quot;{name}_output&quot;, local_pose=Pose3.identity())<br>
        else:<br>
            self.output = None<br>
<br>
        self.kinematic_parent = None<br>
        if parent:<br>
            parent.link(self)<br>
<br>
    def init_output(self, output: Transform3):<br>
        &quot;&quot;&quot;Initialize the output Transform3 if manual_output was set to True.&quot;&quot;&quot;<br>
        if self.output is not None:<br>
            raise RuntimeError(&quot;Output Transform3 is already initialized.&quot;)<br>
        self.output = output<br>
        self.add_child(self.output)<br>
<br>
    def senses(self) -&gt; [Screw3]:<br>
        &quot;&quot;&quot;Return the list of screws representing the sensitivities of this kinematic transform.<br>
        Для совместимости с KinematicChain3 чувствительности возвращаются в порядке от дистального к проксимальному.&quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;senses method must be implemented by subclasses.&quot;)<br>
<br>
    def link(self, child: 'Transform3'):<br>
        &quot;&quot;&quot;Link a child Transform3 to this KinematicTransform3 output.&quot;&quot;&quot;<br>
        self.output.add_child(child)<br>
<br>
    @staticmethod<br>
    def found_first_kinematic_unit_in_parent_tree(body, ignore_self: bool = True) -&gt; 'KinematicTransform3':<br>
        if ignore_self:<br>
            body = body.parent<br>
<br>
        link = body<br>
        while link is not None:<br>
            if isinstance(link, KinematicTransform3):<br>
                return link<br>
            link = link.parent<br>
        return None<br>
<br>
    def update_kinematic_parent(self):<br>
        &quot;&quot;&quot;Update the kinematic parent of this transform.&quot;&quot;&quot;<br>
        self.kinematic_parent = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(self, ignore_self=True)<br>
<br>
    def update_kinematic_parent_recursively(self):<br>
        &quot;&quot;&quot;Recursively update the kinematic parent for this transform and its children.&quot;&quot;&quot;<br>
        self.update_kinematic_parent()<br>
        if self.kinematic_parent is not None:<br>
            self.kinematic_parent.update_kinematic_parent_recursively()<br>
<br>
    def to_trent_with_children(self) -&gt; str:<br>
        dct = {<br>
            &quot;type&quot; : &quot;transform&quot;,<br>
            &quot;pose&quot; : {<br>
                &quot;position&quot;: self._local_pose.lin.tolist(),<br>
                &quot;orientation&quot;: self._local_pose.ang.tolist()<br>
            },<br>
            &quot;name&quot;: self.name,<br>
            &quot;children&quot;: [child.to_trent_with_children(top_without_pose=True) for child in self.children]<br>
        }<br>
        return dct<br>
<br>
class KinematicTransform3OneScrew(KinematicTransform3):<br>
    &quot;&quot;&quot;A Transform3 specialized for 1-DOF kinematic chains.&quot;&quot;&quot;<br>
    def __init__(self, parent: Transform3 = None, name=&quot;kunit_oa&quot;, manual_output: bool = False, local_pose=Pose3.identity()):<br>
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)<br>
        self._sens = None  # To be defined in subclasses<br>
        self._coord = 0.0  # Current coordinate value<br>
<br>
    def sensitivity_for_basis(self, basis: numpy.ndarray) -&gt; Screw3:<br>
        &quot;&quot;&quot;Описывает, как влияет изменение координаты влияет на тело связанное с системой basis в системе отсчета самого basis.&quot;&quot;&quot;<br>
        my_pose = self.global_pose()<br>
        my_pose_in_basis = basis.inverse() * my_pose<br>
        return self._sens.transform_as_twist_by(my_pose_in_basis)<br>
<br>
    def senses(self) -&gt; [Screw3]:<br>
        return [self._sens]<br>
<br>
    def senses_for_basis(self, basis: numpy.ndarray) -&gt; [Screw3]:<br>
        return [self.sensitivity_for_basis(basis)]<br>
<br>
    def sensivity(self) -&gt; Screw3:<br>
        &quot;&quot;&quot;Return the screw representing the sensitivity of this kinematic transform.&quot;&quot;&quot;<br>
        return self._sens<br>
<br>
    def set_coord(self, coord: float):<br>
        &quot;&quot;&quot;Set the coordinate of this kinematic transform.&quot;&quot;&quot;<br>
        self.output.relocate((self._sens * coord).as_pose3())<br>
        self._coord = coord<br>
<br>
    def coord(self) -&gt; float:<br>
        &quot;&quot;&quot;Get the current coordinate of this kinematic transform.&quot;&quot;&quot;<br>
        return self._coord<br>
    <br>
    def get_coord(self) -&gt; float:<br>
        &quot;&quot;&quot;Get the current coordinate of this kinematic transform.&quot;&quot;&quot;<br>
        return self._coord<br>
    <br>
<br>
class Rotator3(KinematicTransform3OneScrew):<br>
    def __init__(self, axis: numpy.ndarray, parent: Transform3 = None, manual_output: bool = False, name=&quot;rotator&quot;, local_pose=Pose3.identity()):<br>
        &quot;&quot;&quot;Initialize a Rotator that rotates around a given axis by angle_rad.&quot;&quot;&quot;<br>
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)<br>
        self._sens = Screw3(ang=numpy.array(axis), lin=numpy.array([0.0, 0.0, 0.0]))<br>
<br>
    def to_trent_with_children(self):<br>
        dct = super().to_trent_with_children()<br>
        dct[&quot;type&quot;] = &quot;rotator&quot;<br>
        dct[&quot;axis&quot;] = self._sens.ang.tolist()<br>
        return dct<br>
<br>
class Actuator3(KinematicTransform3OneScrew):<br>
    def __init__(self, axis: numpy.ndarray, parent: Transform3 = None, manual_output: bool = False, name=&quot;actuator&quot;, local_pose=Pose3.identity()):<br>
        &quot;&quot;&quot;Initialize an Actuator that moves along a given screw.&quot;&quot;&quot;<br>
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)<br>
        self._sens = Screw3(lin=numpy.array(axis), ang=numpy.array([0.0, 0.0, 0.0]))<br>
<br>
    def to_trent_with_children(self):<br>
        dct = super().to_trent_with_children()<br>
        dct[&quot;type&quot;] = &quot;actuator&quot;<br>
        dct[&quot;axis&quot;] = self._sens.lin.tolist()<br>
        return dct<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
