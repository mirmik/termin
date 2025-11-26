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
    Variable,<br>
    Contribution,<br>
    Constraint,<br>
    MatrixAssembler,<br>
    BilinearContribution,<br>
    LoadContribution,<br>
    ConstraintContribution,<br>
    LagrangeConstraint,<br>
)<br>
<br>
# Механические элементы<br>
from .mechanic import (<br>
    BarElement,<br>
    BeamElement2D,<br>
    DistributedLoad,<br>
    Triangle3Node,<br>
    BodyForce,<br>
)<br>
<br>
<br>
<br>
__all__ = [<br>
    # Assembler<br>
    'Variable',<br>
    'Contribution',<br>
    'MatrixAssembler',<br>
    'BilinearContribution',<br>
    'LoadContribution',<br>
    'ConstraintContribution',<br>
    <br>
    # Mechanic<br>
    'BarElement',<br>
    'BeamElement2D',<br>
    'DistributedLoad',<br>
    'Triangle3Node',<br>
    'BodyForce',<br>
    <br>
    # Electromechanical<br>
    'DCMotor',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
