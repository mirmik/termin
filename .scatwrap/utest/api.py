<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/api.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
#&nbsp;coding:utf-8<br>
<br>
import&nbsp;sys<br>
import&nbsp;traceback<br>
import&nbsp;motor_test<br>
<br>
def&nbsp;execute_test(test):<br>
&nbsp;&nbsp;&nbsp;&nbsp;result&nbsp;=&nbsp;unittest.TextTestRunner(verbosity=2).run(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;unittest.TestLoader().loadTestsFromModule(test)<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;len(result.errors)&nbsp;!=&nbsp;0&nbsp;or&nbsp;len(result.failures)&nbsp;!=&nbsp;0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;sys.exit(-1)<br>
<br>
<br>
if&nbsp;__name__&nbsp;==&nbsp;&quot;__main__&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;execute_test(motor_test)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
<!-- END SCAT CODE -->
</body>
</html>
