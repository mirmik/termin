<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/skeleton/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Skeleton&nbsp;module&nbsp;for&nbsp;skeletal&nbsp;animation&nbsp;support.&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
from&nbsp;termin.skeleton._skeleton_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcSkeleton,<br>
&nbsp;&nbsp;&nbsp;&nbsp;SkeletonInstance,<br>
&nbsp;&nbsp;&nbsp;&nbsp;SkeletonController,<br>
)<br>
from&nbsp;termin.skeleton.skeleton_asset&nbsp;import&nbsp;SkeletonAsset<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcSkeleton&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;SkeletonInstance&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;SkeletonController&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;SkeletonAsset&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
