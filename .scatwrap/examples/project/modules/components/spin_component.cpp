<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/modules/components/spin_component.cpp</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#include&nbsp;&quot;spin_component.hpp&quot;<br>
#include&nbsp;&lt;iostream&gt;<br>
<br>
namespace&nbsp;game&nbsp;{<br>
<br>
void&nbsp;SpinComponent::update(float&nbsp;dt)&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;(!entity().valid()&nbsp;||&nbsp;!entity().transform().valid())&nbsp;return;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;termin::GeneralPose3&nbsp;pose&nbsp;=&nbsp;entity().transform().local_pose();<br>
&nbsp;&nbsp;&nbsp;&nbsp;float&nbsp;rad_speed&nbsp;=&nbsp;speed&nbsp;*&nbsp;3.14159265f&nbsp;/&nbsp;180.0f;<br>
&nbsp;&nbsp;&nbsp;&nbsp;auto&nbsp;screw&nbsp;=&nbsp;termin::Screw3{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;termin::Vec3{0.0,&nbsp;0.0,&nbsp;rad_speed},<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;termin::Vec3{0.0,&nbsp;0.0,&nbsp;0.0}<br>
&nbsp;&nbsp;&nbsp;&nbsp;}.scaled(dt);<br>
&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;(pose&nbsp;*&nbsp;screw.to_pose()).normalized();<br>
&nbsp;&nbsp;&nbsp;&nbsp;entity().transform().relocate(pose);<br>
}<br>
<br>
}&nbsp;//&nbsp;namespace&nbsp;game<br>
<!-- END SCAT CODE -->
</body>
</html>
