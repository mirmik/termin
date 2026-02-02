<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;Kinematics&nbsp;Module<br>
<br>
Модуль&nbsp;кинематики&nbsp;и&nbsp;трансформаций&nbsp;для&nbsp;робототехнических&nbsp;приложений.<br>
<br>
##&nbsp;Содержание<br>
<br>
###&nbsp;`transform.py`<br>
Классы&nbsp;для&nbsp;представления&nbsp;трансформаций&nbsp;в&nbsp;2D&nbsp;и&nbsp;3D&nbsp;пространстве:<br>
-&nbsp;**Transform**&nbsp;-&nbsp;базовый&nbsp;класс&nbsp;для&nbsp;иерархии&nbsp;трансформаций<br>
-&nbsp;**Transform3**&nbsp;-&nbsp;трансформации&nbsp;в&nbsp;3D&nbsp;пространстве&nbsp;с&nbsp;позой&nbsp;и&nbsp;иерархией<br>
<br>
###&nbsp;`kinematic.py`<br>
Кинематические&nbsp;преобразования:<br>
-&nbsp;**KinematicTransform3**&nbsp;-&nbsp;базовый&nbsp;класс&nbsp;кинематических&nbsp;трансформаций<br>
-&nbsp;**KinematicTransform3OneScrew**&nbsp;-&nbsp;кинематика&nbsp;на&nbsp;основе&nbsp;одного&nbsp;винта<br>
-&nbsp;**Rotator3**&nbsp;-&nbsp;вращательное&nbsp;сочленение&nbsp;(joint)<br>
-&nbsp;**Actuator3**&nbsp;-&nbsp;линейное&nbsp;сочленение&nbsp;(prismatic&nbsp;joint)<br>
<br>
###&nbsp;`kinchain.py`<br>
Кинематические&nbsp;цепи:<br>
-&nbsp;**KinematicChain3**&nbsp;-&nbsp;класс&nbsp;для&nbsp;работы&nbsp;с&nbsp;кинематическими&nbsp;цепями<br>
&nbsp;&nbsp;-&nbsp;Построение&nbsp;цепей&nbsp;из&nbsp;звеньев<br>
&nbsp;&nbsp;-&nbsp;Вычисление&nbsp;прямой&nbsp;кинематики<br>
&nbsp;&nbsp;-&nbsp;Вычисление&nbsp;якобианов<br>
&nbsp;&nbsp;-&nbsp;Анализ&nbsp;твистов&nbsp;чувствительности<br>
<br>
##&nbsp;Зависимости<br>
<br>
-&nbsp;`termin.pose3`&nbsp;-&nbsp;класс&nbsp;Pose3&nbsp;для&nbsp;представления&nbsp;поз<br>
-&nbsp;`termin.screw`&nbsp;-&nbsp;классы&nbsp;Screw&nbsp;для&nbsp;винтовых&nbsp;преобразований<br>
-&nbsp;`numpy`&nbsp;-&nbsp;для&nbsp;матричных&nbsp;операций<br>
<br>
##&nbsp;Тесты<br>
<br>
Тесты&nbsp;находятся&nbsp;в&nbsp;`utest/kinematics/`:<br>
-&nbsp;`transform_test.py`&nbsp;-&nbsp;тесты&nbsp;Transform3<br>
-&nbsp;`kinematic_test.py`&nbsp;-&nbsp;тесты&nbsp;Rotator3<br>
-&nbsp;`kinematic_chain_test.py`&nbsp;-&nbsp;тесты&nbsp;KinematicChain3<br>
<!-- END SCAT CODE -->
</body>
</html>
