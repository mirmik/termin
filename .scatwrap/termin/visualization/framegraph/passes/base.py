<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/framegraph/passes/base.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.framegraph.core&nbsp;import&nbsp;FramePass<br>
from&nbsp;termin.visualization.framegraph.context&nbsp;import&nbsp;FrameExecutionContext<br>
<br>
<br>
class&nbsp;RenderFramePass(FramePass):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;execute(self,&nbsp;ctx:&nbsp;FrameExecutionContext):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;NotImplementedError<br>
<!-- END SCAT CODE -->
</body>
</html>
