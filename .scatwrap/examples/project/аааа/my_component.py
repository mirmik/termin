<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/аааа/my_component.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
MyComponent&nbsp;component.<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.core.component&nbsp;import&nbsp;Component<br>
<br>
<br>
class&nbsp;MyComponent(Component):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Custom&nbsp;component.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Attributes:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;speed:&nbsp;Movement&nbsp;speed.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;speed:&nbsp;float&nbsp;=&nbsp;1.0):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.speed&nbsp;=&nbsp;speed<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;on_start(self)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Called&nbsp;when&nbsp;the&nbsp;component&nbsp;is&nbsp;first&nbsp;activated.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;on_update(self,&nbsp;dt:&nbsp;float)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Called&nbsp;every&nbsp;frame.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dt:&nbsp;Delta&nbsp;time&nbsp;in&nbsp;seconds.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;on_destroy(self)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Called&nbsp;when&nbsp;the&nbsp;component&nbsp;is&nbsp;destroyed.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<!-- END SCAT CODE -->
</body>
</html>
