<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/fem/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;FEM&nbsp;Tests<br>
<br>
Тесты&nbsp;для&nbsp;модуля&nbsp;конечных&nbsp;элементов&nbsp;(Finite&nbsp;Element&nbsp;Method).<br>
<br>
##&nbsp;Структура<br>
<br>
###&nbsp;`fem_test.py`&nbsp;(20&nbsp;тестов)<br>
Базовые&nbsp;тесты&nbsp;системы&nbsp;сборки&nbsp;матриц:<br>
-&nbsp;**MatrixAssembler**&nbsp;-&nbsp;сборка&nbsp;переменных&nbsp;и&nbsp;вкладов<br>
-&nbsp;**Conditioning**&nbsp;-&nbsp;диагностика&nbsp;состояния&nbsp;матриц,&nbsp;сингулярность<br>
-&nbsp;**SpringSystem**&nbsp;-&nbsp;простые&nbsp;пружинные&nbsp;элементы<br>
-&nbsp;**ElectricalCircuit**&nbsp;-&nbsp;базовые&nbsp;электрические&nbsp;цепи<br>
-&nbsp;**MultiDimensional**&nbsp;-&nbsp;многомерные&nbsp;элементы<br>
<br>
###&nbsp;`mechanic_test.py`&nbsp;(10&nbsp;тестов)<br>
Механические&nbsp;конечные&nbsp;элементы:<br>
-&nbsp;**BarElement**&nbsp;-&nbsp;стержневые&nbsp;элементы&nbsp;(одномерные&nbsp;и&nbsp;двумерные&nbsp;фермы)<br>
-&nbsp;**BeamElement**&nbsp;-&nbsp;балочные&nbsp;элементы&nbsp;(консоль,&nbsp;равномерная&nbsp;нагрузка)<br>
-&nbsp;**TriangleElement**&nbsp;-&nbsp;плоские&nbsp;треугольные&nbsp;элементы&nbsp;(растяжение,&nbsp;сдвиг)<br>
<br>
###&nbsp;`electrical_test.py`&nbsp;(15&nbsp;тестов)<br>
Электрические&nbsp;цепи:<br>
-&nbsp;**Resistor**&nbsp;-&nbsp;резисторы&nbsp;(проводимость,&nbsp;мощность,&nbsp;ток)<br>
-&nbsp;**VoltageDivider**&nbsp;-&nbsp;делители&nbsp;напряжения<br>
-&nbsp;**CurrentSource**&nbsp;-&nbsp;источники&nbsp;тока<br>
-&nbsp;**Capacitor**&nbsp;-&nbsp;конденсаторы&nbsp;(статика&nbsp;и&nbsp;динамика,&nbsp;зарядка&nbsp;RC)<br>
-&nbsp;**Inductor**&nbsp;-&nbsp;индуктивности&nbsp;(статика&nbsp;и&nbsp;динамика&nbsp;RL&nbsp;цепей)<br>
-&nbsp;**ComplexCircuit**&nbsp;-&nbsp;сложные&nbsp;схемы&nbsp;(мостовые&nbsp;цепи)<br>
<br>
###&nbsp;`multibody_test.py`&nbsp;(4&nbsp;теста)<br>
Многотельная&nbsp;механика:<br>
-&nbsp;**RotationalInertia**&nbsp;-&nbsp;вращательная&nbsp;инерция&nbsp;(статика&nbsp;и&nbsp;динамика)<br>
-&nbsp;**RotationalSpring**&nbsp;-&nbsp;вращательные&nbsp;пружины&nbsp;(связь&nbsp;инерций)<br>
-&nbsp;**FixedRotation**&nbsp;-&nbsp;граничные&nbsp;условия&nbsp;(фиксация&nbsp;скорости)<br>
<br>
###&nbsp;`electromechanical_test.py`&nbsp;(4&nbsp;теста)<br>
Электромеханическая&nbsp;связь:<br>
-&nbsp;**DCMotor**&nbsp;-&nbsp;двигатель&nbsp;постоянного&nbsp;тока<br>
&nbsp;&nbsp;-&nbsp;Статический&nbsp;режим&nbsp;без&nbsp;нагрузки<br>
&nbsp;&nbsp;-&nbsp;Эффект&nbsp;противо-ЭДС&nbsp;(back-EMF)<br>
-&nbsp;**MotorWithLoad**&nbsp;-&nbsp;двигатель&nbsp;с&nbsp;механической&nbsp;нагрузкой<br>
&nbsp;&nbsp;-&nbsp;Установившийся&nbsp;режим<br>
&nbsp;&nbsp;-&nbsp;Динамика&nbsp;разгона<br>
<br>
##&nbsp;Запуск&nbsp;тестов<br>
<br>
```bash<br>
#&nbsp;Все&nbsp;FEM&nbsp;тесты<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/fem/&nbsp;-v<br>
<br>
#&nbsp;Конкретный&nbsp;модуль<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/fem/electrical_test.py&nbsp;-v<br>
<br>
#&nbsp;Конкретный&nbsp;тест<br>
python3&nbsp;-m&nbsp;pytest&nbsp;utest/fem/electrical_test.py::TestCapacitor::test_rc_charging&nbsp;-v<br>
```<br>
<br>
##&nbsp;Итого<br>
<br>
**53&nbsp;теста**&nbsp;для&nbsp;модуля&nbsp;конечных&nbsp;элементов,&nbsp;охватывающие:<br>
-&nbsp;Механику&nbsp;(стержни,&nbsp;балки,&nbsp;треугольники)<br>
-&nbsp;Электрические&nbsp;цепи&nbsp;(R,&nbsp;L,&nbsp;C&nbsp;элементы)<br>
-&nbsp;Многотельную&nbsp;динамику&nbsp;(инерции,&nbsp;пружины)<br>
-&nbsp;Электромеханическую&nbsp;связь&nbsp;(двигатели)<br>
<!-- END SCAT CODE -->
</body>
</html>
