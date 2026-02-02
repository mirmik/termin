<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/editor/render_request.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Global&nbsp;render&nbsp;update&nbsp;request.<br>
<br>
Allows&nbsp;components&nbsp;to&nbsp;request&nbsp;viewport&nbsp;redraw&nbsp;from&nbsp;anywhere.<br>
The&nbsp;callback&nbsp;is&nbsp;set&nbsp;by&nbsp;EditorWindow&nbsp;on&nbsp;startup.<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;Callable<br>
<br>
_request_update_callback:&nbsp;Callable[[],&nbsp;None]&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<br>
<br>
def&nbsp;set_request_update_callback(callback:&nbsp;Callable[[],&nbsp;None]&nbsp;|&nbsp;None)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Set&nbsp;the&nbsp;global&nbsp;render&nbsp;update&nbsp;callback.&nbsp;Called&nbsp;by&nbsp;EditorWindow.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;global&nbsp;_request_update_callback<br>
&nbsp;&nbsp;&nbsp;&nbsp;_request_update_callback&nbsp;=&nbsp;callback<br>
<br>
<br>
def&nbsp;request_render_update()&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Request&nbsp;viewport&nbsp;redraw.&nbsp;Can&nbsp;be&nbsp;called&nbsp;from&nbsp;anywhere.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;_request_update_callback&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_request_update_callback()<br>
<!-- END SCAT CODE -->
</body>
</html>
