<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/assets/resources/_serialization.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Serialization&nbsp;mixin&nbsp;for&nbsp;ResourceManager.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;TYPE_CHECKING<br>
<br>
if&nbsp;TYPE_CHECKING:<br>
&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.assets.texture_asset&nbsp;import&nbsp;TextureAsset<br>
<br>
<br>
class&nbsp;SerializationMixin:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Mixin&nbsp;for&nbsp;serialization/deserialization.&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;serialize(self)&nbsp;-&gt;&nbsp;dict:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Сериализует&nbsp;все&nbsp;ресурсы&nbsp;ResourceManager.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Материалы&nbsp;и&nbsp;меши&nbsp;не&nbsp;сериализуются&nbsp;—&nbsp;они&nbsp;загружаются&nbsp;из&nbsp;файлов&nbsp;проекта.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;textures&quot;:&nbsp;{name:&nbsp;self._serialize_texture_asset(asset)&nbsp;for&nbsp;name,&nbsp;asset&nbsp;in&nbsp;self._texture_assets.items()},<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;_serialize_texture_asset(self,&nbsp;asset:&nbsp;&quot;TextureAsset&quot;)&nbsp;-&gt;&nbsp;dict:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Сериализует&nbsp;TextureAsset.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;source_path&nbsp;=&nbsp;str(asset.source_path)&nbsp;if&nbsp;asset.source_path&nbsp;else&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;source_path:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;{&quot;type&quot;:&nbsp;&quot;file&quot;,&nbsp;&quot;source_path&quot;:&nbsp;source_path}<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;{&quot;type&quot;:&nbsp;&quot;unknown&quot;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@classmethod<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;deserialize(cls,&nbsp;data:&nbsp;dict,&nbsp;context=None)&nbsp;-&gt;&nbsp;&quot;SerializationMixin&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Восстанавливает&nbsp;ресурсы&nbsp;из&nbsp;сериализованных&nbsp;данных&nbsp;в&nbsp;синглтон.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавляет&nbsp;десериализованные&nbsp;ресурсы&nbsp;к&nbsp;существующему&nbsp;синглтону.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Меши&nbsp;и&nbsp;материалы&nbsp;загружаются&nbsp;из&nbsp;файлов&nbsp;проекта,&nbsp;не&nbsp;из&nbsp;сцены.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;cls.instance()<br>
<!-- END SCAT CODE -->
</body>
</html>
