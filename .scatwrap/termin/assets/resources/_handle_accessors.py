<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/assets/resources/_handle_accessors.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;HandleAccessors&nbsp;class&nbsp;for&nbsp;unified&nbsp;resource&nbsp;access.&quot;&quot;&quot;<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;Any,&nbsp;Callable,&nbsp;List,&nbsp;Optional,&nbsp;Tuple<br>
<br>
<br>
class&nbsp;HandleAccessors:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Unified&nbsp;accessors&nbsp;for&nbsp;handle-based&nbsp;resource&nbsp;types.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Provides&nbsp;a&nbsp;consistent&nbsp;interface&nbsp;for&nbsp;listing,&nbsp;getting,&nbsp;and&nbsp;finding<br>
&nbsp;&nbsp;&nbsp;&nbsp;resources&nbsp;by&nbsp;name/handle&nbsp;for&nbsp;use&nbsp;in&nbsp;generic&nbsp;selector&nbsp;widgets.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;list_names:&nbsp;Callable[[],&nbsp;list[str]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;get_by_name:&nbsp;Callable[[str],&nbsp;Any],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;find_name:&nbsp;Callable[[Any],&nbsp;Optional[str]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;find_uuid:&nbsp;Callable[[str],&nbsp;Optional[str]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;allow_none:&nbsp;bool&nbsp;=&nbsp;True,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.list_names&nbsp;=&nbsp;list_names<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.get_by_name&nbsp;=&nbsp;get_by_name<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.find_name&nbsp;=&nbsp;find_name<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.find_uuid&nbsp;=&nbsp;find_uuid<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.allow_none&nbsp;=&nbsp;allow_none<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;list_items(self)&nbsp;-&gt;&nbsp;List[Tuple[str,&nbsp;Optional[str]]]:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;list&nbsp;of&nbsp;(name,&nbsp;uuid)&nbsp;tuples&nbsp;for&nbsp;all&nbsp;items.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result&nbsp;=&nbsp;[]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;name&nbsp;in&nbsp;self.list_names():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;uuid&nbsp;=&nbsp;self.find_uuid(name)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result.append((name,&nbsp;uuid))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;result<br>
<!-- END SCAT CODE -->
</body>
</html>
