<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/components/skybox_renderer.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
from&nbsp;typing&nbsp;import&nbsp;Optional<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;..entity&nbsp;import&nbsp;RenderContext<br>
from&nbsp;..material&nbsp;import&nbsp;Material<br>
from&nbsp;..mesh&nbsp;import&nbsp;MeshDrawable<br>
from&nbsp;..entity&nbsp;import&nbsp;Component<br>
from&nbsp;.mesh_renderer&nbsp;import&nbsp;MeshRenderer<br>
from&nbsp;termin.geombase.pose3&nbsp;import&nbsp;Pose3<br>
<br>
class&nbsp;SkyboxRenderer(MeshRenderer):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Specialized&nbsp;renderer&nbsp;for&nbsp;skyboxes&nbsp;(no&nbsp;depth&nbsp;writes&nbsp;and&nbsp;view&nbsp;without&nbsp;translation).&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;draw(self,&nbsp;context:&nbsp;RenderContext):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.entity&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;camera_entity&nbsp;=&nbsp;context.camera.entity&nbsp;if&nbsp;context.camera&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;camera_entity&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#self.entity.transform.local_pose.lin&nbsp;=&nbsp;camera_entity.transform.global_pose().lin.copy()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.entity.transform.relocate(Pose3(lin&nbsp;=&nbsp;camera_entity.transform.global_pose().lin))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;original_view&nbsp;=&nbsp;context.view<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;view_no_translation&nbsp;=&nbsp;np.array(original_view,&nbsp;copy=True)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;view_no_translation[:3,&nbsp;3]&nbsp;=&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;context.graphics.set_depth_mask(False)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;context.graphics.set_depth_func(&quot;lequal&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.material.apply(self.entity.model_matrix(),&nbsp;view_no_translation,&nbsp;context.projection,&nbsp;graphics=context.graphics,&nbsp;context_key=context.context_key)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.mesh.draw(context)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;context.graphics.set_depth_func(&quot;less&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;context.graphics.set_depth_mask(True)<br>
<!-- END SCAT CODE -->
</body>
</html>
