<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;Colliders&nbsp;Module<br>
<br>
Модуль&nbsp;для&nbsp;обнаружения&nbsp;столкновений&nbsp;и&nbsp;вычисления&nbsp;расстояний&nbsp;между&nbsp;геометрическими&nbsp;примитивами.<br>
<br>
##&nbsp;Назначение<br>
<br>
Модуль&nbsp;предоставляет&nbsp;набор&nbsp;коллайдеров&nbsp;для:<br>
-&nbsp;Вычисления&nbsp;ближайших&nbsp;точек&nbsp;между&nbsp;объектами<br>
-&nbsp;Определения&nbsp;расстояния&nbsp;между&nbsp;объектами<br>
-&nbsp;Вычисления&nbsp;векторов&nbsp;избегания&nbsp;столкновений<br>
-&nbsp;Трансформации&nbsp;коллайдеров&nbsp;в&nbsp;пространстве<br>
<br>
##&nbsp;Классы<br>
<br>
###&nbsp;Примитивы<br>
-&nbsp;`SphereCollider`&nbsp;-&nbsp;сферический&nbsp;коллайдер&nbsp;(центр,&nbsp;радиус)<br>
-&nbsp;`BoxCollider`&nbsp;-&nbsp;прямоугольный&nbsp;коллайдер&nbsp;(центр,&nbsp;размеры,&nbsp;поза)<br>
-&nbsp;`CapsuleCollider`&nbsp;-&nbsp;капсула&nbsp;(отрезок&nbsp;оси,&nbsp;радиус)<br>
<br>
###&nbsp;Специальные<br>
-&nbsp;`AttachedCollider`&nbsp;-&nbsp;коллайдер,&nbsp;привязанный&nbsp;к&nbsp;Transform3&nbsp;(для&nbsp;динамических&nbsp;объектов)<br>
-&nbsp;`UnionCollider`&nbsp;-&nbsp;объединение&nbsp;нескольких&nbsp;коллайдеров&nbsp;в&nbsp;один<br>
<br>
##&nbsp;API<br>
<br>
Все&nbsp;коллайдеры&nbsp;поддерживают:<br>
-&nbsp;`transform_by(pose)`&nbsp;-&nbsp;возвращает&nbsp;трансформированный&nbsp;коллайдер<br>
-&nbsp;`closest_to_collider(other)`&nbsp;-&nbsp;возвращает&nbsp;`(p_near,&nbsp;q_near,&nbsp;distance)`<br>
-&nbsp;`avoidance(other)`&nbsp;-&nbsp;возвращает&nbsp;`(direction,&nbsp;distance,&nbsp;point)`<br>
<br>
Расстояние:<br>
-&nbsp;`dist&nbsp;&gt;&nbsp;0`&nbsp;-&nbsp;коллайдеры&nbsp;разделены<br>
-&nbsp;`dist&nbsp;=&nbsp;0`&nbsp;-&nbsp;коллайдеры&nbsp;касаются<br>
-&nbsp;`dist&nbsp;&lt;&nbsp;0`&nbsp;-&nbsp;коллайдеры&nbsp;пересекаются<br>
<br>
##&nbsp;Связь&nbsp;с&nbsp;другими&nbsp;модулями<br>
<br>
-&nbsp;**kinematics**&nbsp;-&nbsp;AttachedCollider&nbsp;следует&nbsp;за&nbsp;Transform3<br>
-&nbsp;**geombase**&nbsp;-&nbsp;использует&nbsp;Pose3&nbsp;для&nbsp;трансформаций<br>
-&nbsp;**physics**&nbsp;-&nbsp;коллайдеры&nbsp;для&nbsp;динамических&nbsp;тел<br>
<!-- END SCAT CODE -->
</body>
</html>
