<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/modules/components/spin_component.hpp</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#pragma&nbsp;once<br>
<br>
#include&nbsp;&lt;cstdio&gt;<br>
#include&nbsp;&lt;termin/entity/component.hpp&gt;<br>
#include&nbsp;&lt;termin/entity/component_registry.hpp&gt;<br>
#include&nbsp;&lt;termin/entity/entity.hpp&gt;<br>
#include&nbsp;&lt;termin/geom/geom.hpp&gt;<br>
<br>
namespace&nbsp;game&nbsp;{<br>
<br>
class&nbsp;SpinComponent&nbsp;:&nbsp;public&nbsp;termin::CxxComponent&nbsp;{<br>
public:<br>
&nbsp;&nbsp;&nbsp;&nbsp;float&nbsp;speed&nbsp;=&nbsp;90.0f;&nbsp;&nbsp;//&nbsp;degrees&nbsp;per&nbsp;second<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;INSPECT_FIELD(SpinComponent,&nbsp;speed,&nbsp;&quot;Speed&quot;,&nbsp;&quot;float&quot;,&nbsp;-360.0,&nbsp;360.0,&nbsp;1.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;SpinComponent()&nbsp;{}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;void&nbsp;update(float&nbsp;dt)&nbsp;override;<br>
};<br>
<br>
REGISTER_COMPONENT(SpinComponent,&nbsp;Component);<br>
<br>
}&nbsp;//&nbsp;namespace&nbsp;game<br>
<!-- END SCAT CODE -->
</body>
</html>
