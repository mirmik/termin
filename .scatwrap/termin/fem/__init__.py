<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
FEM (Finite Element Method) модуль для мультифизического моделирования.

Содержит инструменты для:
- Сборки и решения систем линейных уравнений методом конечных элементов
- Моделирования механических систем (стержни, балки, треугольные элементы)
- Моделирования электрических цепей (резисторы, конденсаторы, индуктивности)
- Моделирования многотельной динамики (инерции, пружины, демпферы)
- Моделирования электромеханических систем (двигатели постоянного тока)
&quot;&quot;&quot;

# Базовые классы для сборки систем
from .assembler import (
    Variable,
    Contribution,
    Constraint,
    MatrixAssembler,
    BilinearContribution,
    LoadContribution,
    ConstraintContribution,
    LagrangeConstraint,
)

# Механические элементы
from .mechanic import (
    BarElement,
    BeamElement2D,
    DistributedLoad,
    Triangle3Node,
    BodyForce,
)



__all__ = [
    # Assembler
    'Variable',
    'Contribution',
    'MatrixAssembler',
    'BilinearContribution',
    'LoadContribution',
    'ConstraintContribution',
    
    # Mechanic
    'BarElement',
    'BeamElement2D',
    'DistributedLoad',
    'Triangle3Node',
    'BodyForce',
    
    # Electromechanical
    'DCMotor',
]

</code></pre>
</body>
</html>
