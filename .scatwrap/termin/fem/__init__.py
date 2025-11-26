<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
FEM&nbsp;(Finite&nbsp;Element&nbsp;Method)&nbsp;модуль&nbsp;для&nbsp;мультифизического&nbsp;моделирования.<br>
<br>
Содержит&nbsp;инструменты&nbsp;для:<br>
-&nbsp;Сборки&nbsp;и&nbsp;решения&nbsp;систем&nbsp;линейных&nbsp;уравнений&nbsp;методом&nbsp;конечных&nbsp;элементов<br>
-&nbsp;Моделирования&nbsp;механических&nbsp;систем&nbsp;(стержни,&nbsp;балки,&nbsp;треугольные&nbsp;элементы)<br>
-&nbsp;Моделирования&nbsp;электрических&nbsp;цепей&nbsp;(резисторы,&nbsp;конденсаторы,&nbsp;индуктивности)<br>
-&nbsp;Моделирования&nbsp;многотельной&nbsp;динамики&nbsp;(инерции,&nbsp;пружины,&nbsp;демпферы)<br>
-&nbsp;Моделирования&nbsp;электромеханических&nbsp;систем&nbsp;(двигатели&nbsp;постоянного&nbsp;тока)<br>
&quot;&quot;&quot;<br>
<br>
#&nbsp;Базовые&nbsp;классы&nbsp;для&nbsp;сборки&nbsp;систем<br>
from&nbsp;.assembler&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;Variable,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Contribution,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Constraint,<br>
&nbsp;&nbsp;&nbsp;&nbsp;MatrixAssembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;BilinearContribution,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LoadContribution,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ConstraintContribution,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LagrangeConstraint,<br>
)<br>
<br>
#&nbsp;Механические&nbsp;элементы<br>
from&nbsp;.mechanic&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;BarElement,<br>
&nbsp;&nbsp;&nbsp;&nbsp;BeamElement2D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;DistributedLoad,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Triangle3Node,<br>
&nbsp;&nbsp;&nbsp;&nbsp;BodyForce,<br>
)<br>
<br>
<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Assembler<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Variable',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Contribution',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'MatrixAssembler',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'BilinearContribution',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'LoadContribution',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'ConstraintContribution',<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Mechanic<br>
&nbsp;&nbsp;&nbsp;&nbsp;'BarElement',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'BeamElement2D',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'DistributedLoad',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Triangle3Node',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'BodyForce',<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Electromechanical<br>
&nbsp;&nbsp;&nbsp;&nbsp;'DCMotor',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
