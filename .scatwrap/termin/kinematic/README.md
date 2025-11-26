<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# Kinematics Module<br>
<br>
Модуль кинематики и трансформаций для робототехнических приложений.<br>
<br>
## Содержание<br>
<br>
### `transform.py`<br>
Классы для представления трансформаций в 2D и 3D пространстве:<br>
- **Transform** - базовый класс для иерархии трансформаций<br>
- **Transform3** - трансформации в 3D пространстве с позой и иерархией<br>
<br>
### `kinematic.py`<br>
Кинематические преобразования:<br>
- **KinematicTransform3** - базовый класс кинематических трансформаций<br>
- **KinematicTransform3OneScrew** - кинематика на основе одного винта<br>
- **Rotator3** - вращательное сочленение (joint)<br>
- **Actuator3** - линейное сочленение (prismatic joint)<br>
<br>
### `kinchain.py`<br>
Кинематические цепи:<br>
- **KinematicChain3** - класс для работы с кинематическими цепями<br>
  - Построение цепей из звеньев<br>
  - Вычисление прямой кинематики<br>
  - Вычисление якобианов<br>
  - Анализ твистов чувствительности<br>
<br>
## Зависимости<br>
<br>
- `termin.pose3` - класс Pose3 для представления поз<br>
- `termin.screw` - классы Screw для винтовых преобразований<br>
- `numpy` - для матричных операций<br>
<br>
## Тесты<br>
<br>
Тесты находятся в `utest/kinematics/`:<br>
- `transform_test.py` - тесты Transform3<br>
- `kinematic_test.py` - тесты Rotator3<br>
- `kinematic_chain_test.py` - тесты KinematicChain3<br>
<!-- END SCAT CODE -->
</body>
</html>
