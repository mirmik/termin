<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
FEM (Finite Element Method) модуль для мультифизического моделирования.<br>
<br>
Содержит инструменты для:<br>
- Сборки и решения систем линейных уравнений методом конечных элементов<br>
- Моделирования механических систем (стержни, балки, треугольные элементы)<br>
- Моделирования электрических цепей (резисторы, конденсаторы, индуктивности)<br>
- Моделирования многотельной динамики (инерции, пружины, демпферы)<br>
- Моделирования электромеханических систем (двигатели постоянного тока)<br>
&quot;&quot;&quot;<br>
<br>
# Базовые классы для сборки систем<br>
from .assembler import (<br>
&#9;Variable,<br>
&#9;Contribution,<br>
&#9;Constraint,<br>
&#9;MatrixAssembler,<br>
&#9;BilinearContribution,<br>
&#9;LoadContribution,<br>
&#9;ConstraintContribution,<br>
&#9;LagrangeConstraint,<br>
)<br>
<br>
# Механические элементы<br>
from .mechanic import (<br>
&#9;BarElement,<br>
&#9;BeamElement2D,<br>
&#9;DistributedLoad,<br>
&#9;Triangle3Node,<br>
&#9;BodyForce,<br>
)<br>
<br>
<br>
<br>
__all__ = [<br>
&#9;# Assembler<br>
&#9;'Variable',<br>
&#9;'Contribution',<br>
&#9;'MatrixAssembler',<br>
&#9;'BilinearContribution',<br>
&#9;'LoadContribution',<br>
&#9;'ConstraintContribution',<br>
&#9;<br>
&#9;# Mechanic<br>
&#9;'BarElement',<br>
&#9;'BeamElement2D',<br>
&#9;'DistributedLoad',<br>
&#9;'Triangle3Node',<br>
&#9;'BodyForce',<br>
&#9;<br>
&#9;# Electromechanical<br>
&#9;'DCMotor',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
