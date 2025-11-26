<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# Colliders Module<br>
<br>
Модуль для обнаружения столкновений и вычисления расстояний между геометрическими примитивами.<br>
<br>
## Назначение<br>
<br>
Модуль предоставляет набор коллайдеров для:<br>
- Вычисления ближайших точек между объектами<br>
- Определения расстояния между объектами<br>
- Вычисления векторов избегания столкновений<br>
- Трансформации коллайдеров в пространстве<br>
<br>
## Классы<br>
<br>
### Примитивы<br>
- `SphereCollider` - сферический коллайдер (центр, радиус)<br>
- `BoxCollider` - прямоугольный коллайдер (центр, размеры, поза)<br>
- `CapsuleCollider` - капсула (отрезок оси, радиус)<br>
<br>
### Специальные<br>
- `AttachedCollider` - коллайдер, привязанный к Transform3 (для динамических объектов)<br>
- `UnionCollider` - объединение нескольких коллайдеров в один<br>
<br>
## API<br>
<br>
Все коллайдеры поддерживают:<br>
- `transform_by(pose)` - возвращает трансформированный коллайдер<br>
- `closest_to_collider(other)` - возвращает `(p_near, q_near, distance)`<br>
- `avoidance(other)` - возвращает `(direction, distance, point)`<br>
<br>
Расстояние:<br>
- `dist &gt; 0` - коллайдеры разделены<br>
- `dist = 0` - коллайдеры касаются<br>
- `dist &lt; 0` - коллайдеры пересекаются<br>
<br>
## Связь с другими модулями<br>
<br>
- **kinematics** - AttachedCollider следует за Transform3<br>
- **geombase** - использует Pose3 для трансформаций<br>
- **physics** - коллайдеры для динамических тел<br>
<!-- END SCAT CODE -->
</body>
</html>
