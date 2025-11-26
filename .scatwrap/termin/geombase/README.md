<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;Geombase&nbsp;Module<br>
<br>
Модуль&nbsp;базовых&nbsp;геометрических&nbsp;классов&nbsp;для&nbsp;представления&nbsp;поз&nbsp;и&nbsp;винтовых&nbsp;преобразований.<br>
<br>
##&nbsp;Содержание<br>
<br>
###&nbsp;`pose2.py`<br>
<br>
####&nbsp;Pose2<br>
Класс&nbsp;для&nbsp;представления&nbsp;позы&nbsp;в&nbsp;2D&nbsp;пространстве&nbsp;(положение&nbsp;+&nbsp;ориентация).<br>
<br>
Поза&nbsp;хранится&nbsp;в&nbsp;виде:<br>
-&nbsp;**ang**&nbsp;(angle)&nbsp;-&nbsp;угол&nbsp;поворота&nbsp;в&nbsp;радианах<br>
-&nbsp;**lin**&nbsp;(linear)&nbsp;-&nbsp;вектор&nbsp;положения&nbsp;[x,&nbsp;y]<br>
<br>
**Представление:**<br>
-&nbsp;Использует&nbsp;**угол**&nbsp;для&nbsp;представления&nbsp;ориентации&nbsp;(простое&nbsp;и&nbsp;эффективное&nbsp;для&nbsp;2D)<br>
-&nbsp;Предоставляет&nbsp;методы&nbsp;для&nbsp;получения&nbsp;матриц&nbsp;вращения&nbsp;2×2&nbsp;и&nbsp;трансформации&nbsp;3×3<br>
-&nbsp;Подходит&nbsp;для&nbsp;2D&nbsp;робототехники,&nbsp;планирования&nbsp;траекторий<br>
-&nbsp;Поддерживает&nbsp;композицию&nbsp;через&nbsp;оператор&nbsp;умножения<br>
<br>
###&nbsp;`pose3.py`<br>
<br>
####&nbsp;Pose3<br>
Класс&nbsp;для&nbsp;представления&nbsp;позы&nbsp;в&nbsp;3D&nbsp;пространстве&nbsp;(положение&nbsp;+&nbsp;ориентация).<br>
<br>
Поза&nbsp;хранится&nbsp;в&nbsp;виде:<br>
-&nbsp;**ang**&nbsp;(angle)&nbsp;-&nbsp;кватернион&nbsp;вращения&nbsp;[x,&nbsp;y,&nbsp;z,&nbsp;w]<br>
-&nbsp;**lin**&nbsp;(linear)&nbsp;-&nbsp;вектор&nbsp;положения&nbsp;[x,&nbsp;y,&nbsp;z]<br>
<br>
**Представление:**<br>
-&nbsp;Использует&nbsp;**кватернионы**&nbsp;для&nbsp;представления&nbsp;ориентации&nbsp;(компактно,&nbsp;без&nbsp;gimbal&nbsp;lock)<br>
-&nbsp;Предоставляет&nbsp;методы&nbsp;для&nbsp;получения&nbsp;матриц&nbsp;вращения&nbsp;при&nbsp;необходимости<br>
-&nbsp;Подходит&nbsp;для&nbsp;интерполяции&nbsp;и&nbsp;кинематических&nbsp;цепей<br>
-&nbsp;Поддерживает&nbsp;композицию&nbsp;через&nbsp;оператор&nbsp;умножения<br>
<br>
**Новые&nbsp;возможности:**<br>
-&nbsp;**Properties&nbsp;x,&nbsp;y,&nbsp;z**&nbsp;-&nbsp;прямой&nbsp;доступ&nbsp;к&nbsp;координатам&nbsp;положения<br>
-&nbsp;**normalize()**&nbsp;-&nbsp;нормализация&nbsp;кватерниона&nbsp;к&nbsp;единичной&nbsp;длине<br>
-&nbsp;**distance(other)**&nbsp;-&nbsp;расстояние&nbsp;между&nbsp;двумя&nbsp;позами<br>
-&nbsp;**to_axis_angle()&nbsp;/&nbsp;from_axis_angle()**&nbsp;-&nbsp;конвертация&nbsp;axis-angle&nbsp;↔&nbsp;quaternion<br>
-&nbsp;**to_euler()&nbsp;/&nbsp;from_euler()**&nbsp;-&nbsp;конвертация&nbsp;Euler&nbsp;angles&nbsp;↔&nbsp;quaternion&nbsp;(порядок&nbsp;'xyz')<br>
-&nbsp;**looking_at()**&nbsp;-&nbsp;создать&nbsp;позу,&nbsp;направленную&nbsp;на&nbsp;заданную&nbsp;точку<br>
-&nbsp;**as_matrix34()**&nbsp;-&nbsp;получить&nbsp;3×4&nbsp;матрицу&nbsp;трансформации<br>
<br>
###&nbsp;`screw.py`<br>
<br>
Классы&nbsp;для&nbsp;винтовых&nbsp;преобразований&nbsp;(твистов&nbsp;и&nbsp;ренчей).<br>
<br>
####&nbsp;Screw<br>
Базовый&nbsp;класс&nbsp;винта&nbsp;-&nbsp;пара&nbsp;(угловая&nbsp;часть,&nbsp;линейная&nbsp;часть).<br>
<br>
**Применение:**<br>
-&nbsp;Твисты&nbsp;(twist)&nbsp;-&nbsp;мгновенные&nbsp;скорости<br>
-&nbsp;Ренчи&nbsp;(wrench)&nbsp;-&nbsp;силы&nbsp;и&nbsp;моменты<br>
-&nbsp;Якобианы&nbsp;кинематических&nbsp;цепей<br>
<br>
####&nbsp;Screw2<br>
Винт&nbsp;в&nbsp;2D&nbsp;пространстве&nbsp;(плоский&nbsp;случай).<br>
<br>
####&nbsp;Screw3<br>
Винт&nbsp;в&nbsp;3D&nbsp;пространстве.<br>
<br>
Винт&nbsp;представляет:<br>
-&nbsp;**Твист**&nbsp;(twist,&nbsp;velocity&nbsp;screw):&nbsp;мгновенная&nbsp;скорость&nbsp;твердого&nbsp;тела&nbsp;(ang&nbsp;=&nbsp;угловая&nbsp;скорость&nbsp;ω,&nbsp;lin&nbsp;=&nbsp;линейная&nbsp;скорость&nbsp;v)<br>
-&nbsp;**Ренч**&nbsp;(wrench,&nbsp;force&nbsp;screw):&nbsp;система&nbsp;сил&nbsp;на&nbsp;твердом&nbsp;теле&nbsp;(ang&nbsp;=&nbsp;момент&nbsp;M,&nbsp;lin&nbsp;=&nbsp;сила&nbsp;F)<br>
<br>
##&nbsp;Связь&nbsp;с&nbsp;другими&nbsp;модулями<br>
<br>
-&nbsp;**kinematics**&nbsp;-&nbsp;использует&nbsp;Pose2/Pose3&nbsp;для&nbsp;Transform2/Transform3<br>
-&nbsp;**ga201**&nbsp;-&nbsp;использует&nbsp;Screw2/Screw3&nbsp;для&nbsp;геометрической&nbsp;алгебры<br>
-&nbsp;**physics**&nbsp;-&nbsp;использует&nbsp;винты&nbsp;для&nbsp;описания&nbsp;движения&nbsp;и&nbsp;сил<br>
-&nbsp;**fem**&nbsp;-&nbsp;использует&nbsp;Pose2/Pose3&nbsp;для&nbsp;коллайдеров&nbsp;и&nbsp;многотельной&nbsp;механики<br>
<br>
##&nbsp;Тесты<br>
<br>
-&nbsp;`utest/pose2_test.py`&nbsp;-&nbsp;тесты&nbsp;Pose2&nbsp;(14&nbsp;тестов)<br>
-&nbsp;`utest/pose_test.py`&nbsp;-&nbsp;тесты&nbsp;Pose3&nbsp;(23&nbsp;теста)<br>
-&nbsp;`utest/screw_test.py`&nbsp;-&nbsp;тесты&nbsp;Screw2&nbsp;(из&nbsp;ga201,&nbsp;6&nbsp;тестов)<br>
<br>
##&nbsp;Зависимости<br>
<br>
-&nbsp;**numpy**&nbsp;-&nbsp;для&nbsp;матричных&nbsp;и&nbsp;векторных&nbsp;операций<br>
-&nbsp;**math**&nbsp;-&nbsp;для&nbsp;тригонометрических&nbsp;функций<br>
<!-- END SCAT CODE -->
</body>
</html>
