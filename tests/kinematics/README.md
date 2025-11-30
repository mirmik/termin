# Kinematics Tests

Тесты для модуля кинематики и трансформаций.

## Структура

### `transform_test.py` (3 теста)
Тесты для класса Transform3:
- **test_hierarchy_global_pose** - иерархия трансформаций и глобальные позы
- **test_relocate_and_global_pose** - перемещение и вычисление глобальных поз
- **test_transform_point** - трансформация точек

### `kinematic_test.py` (1 тест)
Тесты для кинематических преобразований:
- **TestRotator3::test_rotation** - вращательные преобразования

### `kinematic_chain_test.py` (4 теста)
Тесты для кинематических цепей:
- **test_chain_construction** - построение кинематической цепи
- **test_apply_coordinate_changes** - применение изменений координат
- **test_sensitivity_twists** - вычисление твистов чувствительности
- **test_sensitivity_twists_with_basis** - твисты чувствительности с базисом

## Запуск тестов

```bash
# Все тесты кинематики
python3 -m pytest utest/kinematics/ -v

# Конкретный модуль
python3 -m pytest utest/kinematics/kinematic_chain_test.py -v

# Конкретный тест
python3 -m pytest utest/kinematics/transform_test.py::TestTransform3::test_hierarchy_global_pose -v
```

## Итого

**8 тестов** для модуля кинематики:
- **3 теста** Transform3 - трансформации в 3D пространстве
- **1 тест** Rotator3 - кинематические преобразования (вращения)
- **4 теста** KinematicChain - кинематические цепи, якобианы и твисты чувствительности
