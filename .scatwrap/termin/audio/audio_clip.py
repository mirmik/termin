<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/audio/audio_clip.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;AudioClip&nbsp;-&nbsp;audio&nbsp;data&nbsp;wrapper.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
import&nbsp;ctypes<br>
<br>
<br>
class&nbsp;AudioClip:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Audio&nbsp;clip&nbsp;data&nbsp;-&nbsp;wrapper&nbsp;around&nbsp;SDL_mixer&nbsp;Mix_Chunk.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;This&nbsp;is&nbsp;the&nbsp;actual&nbsp;audio&nbsp;resource&nbsp;that&nbsp;components&nbsp;work&nbsp;with.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Does&nbsp;not&nbsp;know&nbsp;about&nbsp;UUIDs,&nbsp;file&nbsp;paths,&nbsp;or&nbsp;asset&nbsp;management.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;chunk:&nbsp;ctypes.c_void_p,&nbsp;duration_ms:&nbsp;int&nbsp;=&nbsp;0):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Initialize&nbsp;AudioClip.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;chunk:&nbsp;Mix_Chunk&nbsp;pointer&nbsp;from&nbsp;SDL_mixer<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;duration_ms:&nbsp;Duration&nbsp;in&nbsp;milliseconds&nbsp;(0&nbsp;if&nbsp;unknown)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._chunk:&nbsp;ctypes.c_void_p&nbsp;=&nbsp;chunk<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._duration_ms:&nbsp;int&nbsp;=&nbsp;duration_ms<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;chunk(self)&nbsp;-&gt;&nbsp;ctypes.c_void_p:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;Mix_Chunk&nbsp;pointer&nbsp;for&nbsp;SDL_mixer&nbsp;operations.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._chunk<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;duration_ms(self)&nbsp;-&gt;&nbsp;int:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Duration&nbsp;in&nbsp;milliseconds.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._duration_ms<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;duration(self)&nbsp;-&gt;&nbsp;float:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Duration&nbsp;in&nbsp;seconds.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._duration_ms&nbsp;/&nbsp;1000.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;is_valid(self)&nbsp;-&gt;&nbsp;bool:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Check&nbsp;if&nbsp;clip&nbsp;has&nbsp;valid&nbsp;audio&nbsp;data.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._chunk&nbsp;is&nbsp;not&nbsp;None<br>
<!-- END SCAT CODE -->
</body>
</html>
