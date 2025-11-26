<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/kinematic.py</title>
</head>
<body>
<pre><code>
from .transform import Transform3
from termin.geombase import Pose3, Screw3
import numpy

class KinematicTransform3(Transform3):
    &quot;&quot;&quot;A Transform3 specialized for kinematic chains.&quot;&quot;&quot;
    def __init__(self, name=&quot;ktrans&quot;, parent: Transform3 = None, manual_output: bool = False, local_pose=Pose3.identity()):
        super().__init__(parent=None, name=name, local_pose=local_pose)

        if not manual_output:
            self.output = Transform3(parent=self, name=f&quot;{name}_output&quot;, local_pose=Pose3.identity())
        else:
            self.output = None

        self.kinematic_parent = None
        if parent:
            parent.link(self)

    def init_output(self, output: Transform3):
        &quot;&quot;&quot;Initialize the output Transform3 if manual_output was set to True.&quot;&quot;&quot;
        if self.output is not None:
            raise RuntimeError(&quot;Output Transform3 is already initialized.&quot;)
        self.output = output
        self.add_child(self.output)

    def senses(self) -&gt; [Screw3]:
        &quot;&quot;&quot;Return the list of screws representing the sensitivities of this kinematic transform.
        Для совместимости с KinematicChain3 чувствительности возвращаются в порядке от дистального к проксимальному.&quot;&quot;&quot;
        raise NotImplementedError(&quot;senses method must be implemented by subclasses.&quot;)

    def link(self, child: 'Transform3'):
        &quot;&quot;&quot;Link a child Transform3 to this KinematicTransform3 output.&quot;&quot;&quot;
        self.output.add_child(child)

    @staticmethod
    def found_first_kinematic_unit_in_parent_tree(body, ignore_self: bool = True) -&gt; 'KinematicTransform3':
        if ignore_self:
            body = body.parent

        link = body
        while link is not None:
            if isinstance(link, KinematicTransform3):
                return link
            link = link.parent
        return None

    def update_kinematic_parent(self):
        &quot;&quot;&quot;Update the kinematic parent of this transform.&quot;&quot;&quot;
        self.kinematic_parent = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(self, ignore_self=True)

    def update_kinematic_parent_recursively(self):
        &quot;&quot;&quot;Recursively update the kinematic parent for this transform and its children.&quot;&quot;&quot;
        self.update_kinematic_parent()
        if self.kinematic_parent is not None:
            self.kinematic_parent.update_kinematic_parent_recursively()

    def to_trent_with_children(self) -&gt; str:
        dct = {
            &quot;type&quot; : &quot;transform&quot;,
            &quot;pose&quot; : {
                &quot;position&quot;: self._local_pose.lin.tolist(),
                &quot;orientation&quot;: self._local_pose.ang.tolist()
            },
            &quot;name&quot;: self.name,
            &quot;children&quot;: [child.to_trent_with_children(top_without_pose=True) for child in self.children]
        }
        return dct

class KinematicTransform3OneScrew(KinematicTransform3):
    &quot;&quot;&quot;A Transform3 specialized for 1-DOF kinematic chains.&quot;&quot;&quot;
    def __init__(self, parent: Transform3 = None, name=&quot;kunit_oa&quot;, manual_output: bool = False, local_pose=Pose3.identity()):
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)
        self._sens = None  # To be defined in subclasses
        self._coord = 0.0  # Current coordinate value

    def sensitivity_for_basis(self, basis: numpy.ndarray) -&gt; Screw3:
        &quot;&quot;&quot;Описывает, как влияет изменение координаты влияет на тело связанное с системой basis в системе отсчета самого basis.&quot;&quot;&quot;
        my_pose = self.global_pose()
        my_pose_in_basis = basis.inverse() * my_pose
        return self._sens.transform_as_twist_by(my_pose_in_basis)

    def senses(self) -&gt; [Screw3]:
        return [self._sens]

    def senses_for_basis(self, basis: numpy.ndarray) -&gt; [Screw3]:
        return [self.sensitivity_for_basis(basis)]

    def sensivity(self) -&gt; Screw3:
        &quot;&quot;&quot;Return the screw representing the sensitivity of this kinematic transform.&quot;&quot;&quot;
        return self._sens

    def set_coord(self, coord: float):
        &quot;&quot;&quot;Set the coordinate of this kinematic transform.&quot;&quot;&quot;
        self.output.relocate((self._sens * coord).as_pose3())
        self._coord = coord

    def coord(self) -&gt; float:
        &quot;&quot;&quot;Get the current coordinate of this kinematic transform.&quot;&quot;&quot;
        return self._coord
    
    def get_coord(self) -&gt; float:
        &quot;&quot;&quot;Get the current coordinate of this kinematic transform.&quot;&quot;&quot;
        return self._coord
    

class Rotator3(KinematicTransform3OneScrew):
    def __init__(self, axis: numpy.ndarray, parent: Transform3 = None, manual_output: bool = False, name=&quot;rotator&quot;, local_pose=Pose3.identity()):
        &quot;&quot;&quot;Initialize a Rotator that rotates around a given axis by angle_rad.&quot;&quot;&quot;
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)
        self._sens = Screw3(ang=numpy.array(axis), lin=numpy.array([0.0, 0.0, 0.0]))

    def to_trent_with_children(self):
        dct = super().to_trent_with_children()
        dct[&quot;type&quot;] = &quot;rotator&quot;
        dct[&quot;axis&quot;] = self._sens.ang.tolist()
        return dct

class Actuator3(KinematicTransform3OneScrew):
    def __init__(self, axis: numpy.ndarray, parent: Transform3 = None, manual_output: bool = False, name=&quot;actuator&quot;, local_pose=Pose3.identity()):
        &quot;&quot;&quot;Initialize an Actuator that moves along a given screw.&quot;&quot;&quot;
        super().__init__(parent=parent, manual_output=manual_output, name=name, local_pose=local_pose)
        self._sens = Screw3(lin=numpy.array(axis), ang=numpy.array([0.0, 0.0, 0.0]))

    def to_trent_with_children(self):
        dct = super().to_trent_with_children()
        dct[&quot;type&quot;] = &quot;actuator&quot;
        dct[&quot;axis&quot;] = self._sens.lin.tolist()
        return dct


</code></pre>
</body>
</html>
