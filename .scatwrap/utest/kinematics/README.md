<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/kinematics/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;Kinematics&nbsp;Tests<br>
<br>
Тесты&nbsp;для&nbsp;модуля&nbsp;кинематики&nbsp;и&nbsp;трансформаций.<br>
<br>
##&nbsp;Структура<br>
<br>
###&nbsp;`transform_test.py`&nbsp;(3&nbsp;теста)<br>
Тесты&nbsp;для&nbsp;класса&nbsp;Transform3:<br>
-&nbsp;**test_hierarchy_global_pose**&nbsp;-&nbsp;иерархия&nbsp;трансформаций&nbsp;и&nbsp;глобальные&nbsp;позы<br>
-&nbsp;**test_relocate_and_global_pose**&nbsp;-&nbsp;перемещение&nbsp;и&nbsp;вычисление&nbsp;глобальных&nbsp;поз<br>
-&nbsp;**test_transform_point**&nbsp;-&nbsp;трансформация&nbsp;точек<br>
<br>
###&nbsp;`kinematic_test.py`&nbsp;(1&nbsp;тест)<br>
Тесты&nbsp;для&nbsp;кинематических&nbsp;преобразований:<br>
-&nbsp;**TestRotator3::test_rotation**&nbsp;-&nbsp;вращательные&nbsp;преобразования<br>
<br>
###&nbsp;`kinematic_chain_test.py`&nbsp;(4&nbsp;теста)<br>
Тесты&nbsp;для&nbsp;кинематических&nbsp;цепей:<br>
-&nbsp;**test_chain_construction**&nbsp;-&nbsp;построение&nbsp;кинематической&nbsp;цепи<br>
-&nbsp;**test_apply_coordinate_changes**&nbsp;-&nbsp;применение&nbsp;изменений&nbsp;координат<br>
-&nbsp;**test_sensitivity_twists**&nbsp;-&nbsp;вычисление&nbsp;твистов&nbsp;чувствительности<br>
-&nbsp;**test_sensitivity_twists_with_basis**&nbsp;-&nbsp;твисты&nbsp;чувствительности&nbsp;с&nbsp;базисом<br>
<br>
##&nbsp;Запуск&nbsp;тестов<br>
<br>
```bash<br>
#&nbsp;Все&nbsp;тесты&nbsp;кинематики<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/kinematics/&nbsp;-v<br>
<br>
#&nbsp;Конкретный&nbsp;модуль<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/kinematics/kinematic_chain_test.py&nbsp;-v<br>
<br>
#&nbsp;Конкретный&nbsp;тест<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/kinematics/transform_test.py::TestTransform3::test_hierarchy_global_pose&nbsp;-v<br>
```<br>
<br>
##&nbsp;Итого<br>
<br>
**8&nbsp;тестов**&nbsp;для&nbsp;модуля&nbsp;кинематики:<br>
-&nbsp;**3&nbsp;теста**&nbsp;Transform3&nbsp;-&nbsp;трансформации&nbsp;в&nbsp;3D&nbsp;пространстве<br>
-&nbsp;**1&nbsp;тест**&nbsp;Rotator3&nbsp;-&nbsp;кинематические&nbsp;преобразования&nbsp;(вращения)<br>
-&nbsp;**4&nbsp;теста**&nbsp;KinematicChain&nbsp;-&nbsp;кинематические&nbsp;цепи,&nbsp;якобианы&nbsp;и&nbsp;твисты&nbsp;чувствительности<br>
<!-- END SCAT CODE -->
</body>
</html>
