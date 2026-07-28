# termin-qopt C++ migration intent

Дата: 2026-05-27
Обновлено: 2026-07-28

Статус: native foundation добавлен. Это не финальная спецификация solver API, а
рабочая рамка для переноса `termin-qopt` из Python/NumPy/SciPy в C++.

Текущее состояние:

- добавлен native shared target `termin_qopt`;
- Eigen подключён только как private dependency target;
- добавлены предварительные `DenseVectorView`/`DenseMatrixView` контракты с
  явными element strides;
- публичные headers, install/export и CMake package contract не требуют Eigen;
- добавлен language-neutral JSON oracle с analytic/KKT contracts для QP,
  nullspace и HQP;
- добавлен provisional native equality-QP contract с caller-owned buffers,
  semantic statuses, diagnostics и residuals;
- добавлен provisional native active-set QP contract для `Cx <= d` и
  lower/upper bounds с Phase I, warm start и полными dual-векторами;
- добавлены native nullspace basis/projector helpers: rank-revealing QR по
  умолчанию, SVD только как явно выбранная rank policy;
- добавлен native `HierarchicalQpSolver` с typed levels, quadratic tasks,
  equality/inequality constraints, сохранением старших task values и явными
  статусами несовместимого младшего уровня;
- добавлен deterministic dense block assembler со стабильными typed handles и
  caller-owned storage;
- добавлен dynamics contract для сборки и решения `M a = f + Jᵀ λ`,
  `J a = γ`;
- добавлена maximal-coordinate 2D multibody-модель на canonical
  `termin-base` types: тела, fixed-point/revolute joints, проекция constraints
  и reactions;
- double pendulum проходит общий JSON oracle из Python и C++, а внешний
  installed-SDK consumer не видит Eigen и собранные матрицы;
- добавлена maximal-coordinate 3D foundation: principal-axis spatial inertia,
  world-frame `[linear, angular]` ordering, quaternion exponential update,
  fixed и two-body point/ball joints;
- добавлены настоящие fixed/two-body 3D revolute joints: три anchor-строки и
  две axis-alignment строки оставляют ровно одну относительную twist DOF;
- старый `RevoluteJoint3D` не переносится под прежней семантикой: его
  point/ball поведение соответствует `PointJoint3D`, а новый
  `RevoluteJoint3DHandle` означает axis-constrained шарнир;
- Python реализация пока остаётся reference implementation.

Инициатива ведётся в Kanboard swimlane `Native QOpt, FEM & Robotics`,
umbrella #980. Foundation закрыт в #981, solver oracle — в #984, первый
multibody vertical slice — в #993–#997.

## Мотивация

`termin-qopt` содержит альтернативный физический и оптимизационный стек:

- dense QP solver для равенств;
- active-set QP solver для неравенств;
- HQP solver поверх nullspace-проекций;
- FEM/multibody matrix assembly;
- электромеханические и механические расширенные системы.

Текущая Python-реализация удобна для прототипирования, но для runtime,
Android/OpenXR и интеграции с C++ сценой со временем нужен native слой.

## Выбор линейной алгебры

Для первого C++ переноса принимается Eigen как базовая библиотека линейной
алгебры.

Причины:

- нужны динамические матрицы и векторы, а не только `Vec3`/`Mat44`;
- нужны Cholesky/LDLT, QR, SVD и least-squares;
- текущие QP/HQP задачи плотные и небольшие;
- FEM-сборка позже может перейти на sparse-путь;
- Eigen проще переносить между Windows, Linux, Android и OpenXR, чем
  runtime-зависимости BLAS/LAPACK на первом этапе.

## Граница зависимости

Eigen не должен становиться публичным SDK API.

Правило:

- в публичных headers `termin-qopt` не должно быть `#include <Eigen/...>`;
- Eigen-типы не должны появляться в exported C++ API;
- Eigen подключается только внутри `.cpp` backend-файлов;
- публичный API использует собственные lightweight view/value типы:
  `VectorView`, `MatrixView`, `QpProblem`, `QpResult` и подобные структуры;
- при необходимости Python bindings мапят NumPy arrays в эти view-типы.

Так стоимость header-only Eigen остается локальной для `termin-qopt`, а
остальной SDK не получает лавину шаблонов в каждый translation unit.

## Предлагаемый порядок переноса

1. [x] Добавить C++ target `termin_qopt`.
2. [x] Ввести минимальные public data contracts для dense vector/matrix views.
3. [x] Зафиксировать независимый solver oracle и semantic statuses.
4. [x] Перенести `solve_qp_equalities`.
5. [x] Перенести `solve_qp_active_set`.
6. [x] Перенести nullspace helpers: QR basis first, SVD basis only where needed.
7. [x] Перенести `HQPSolver`, `Level`, `QuadraticTask`, constraints.
8. [~] Перенести multibody/FEM assembler поверх того же solver API:
   dense block/dynamics assembly, 2D double pendulum и 3D point-joint
   foundation готовы; FEM и axis-constrained 3D joints остаются отдельными
   следующими срезами.
9. Добавить Python re-export/bindings только после стабилизации C++ контрактов.
10. Отдельно оценить sparse backend для больших FEM-систем.

Oracle не объявляет текущее Python-поведение правильным по умолчанию.
Оптимальные случаи проверяются через primal/KKT bounds, nullspace — через
инварианты подпространства, HQP — через сохранение старших приоритетов.
`infeasible`, `unbounded` и `invalid_input` имеют независимые certificates или
структурную диагностику; текущий Python API не считается совместимым с ними,
пока не начнёт возвращать semantic status.

## Provisional nullspace/HQP contract

`write_nullspace_basis` и `write_nullspace_projector` принимают strided input
и caller-owned `n x n` output. Для basis значимы первые `nullity` столбцов,
остальные обнуляются. Контракт фиксирует rank/nullity и
residual/orthogonality bounds, но не знаки и порядок basis vectors.
Rank-revealing QR — штатный путь; SVD включается вызывающим кодом явно.

`HierarchicalQpSolver` копирует зарегистрированные `QuadraticTaskView`,
`EqualityConstraintView` и `InequalityConstraintView`, поэтому их исходные
buffers не обязаны жить до `solve`. Уровни исполняются по числовому priority.
Hard constraints накапливаются, а после каждого уровня допустимые направления
пересекаются с nullspace его равенств и task Jacobians. Поэтому младший уровень
не меняет достигнутые старшие task values. Если nullspace исчерпан, новые
несовместимые constraints дают `Infeasible/LevelSolveFailure`, а не молча
игнорируются. Output buffers изменяются только при полном `Optimal`.

## Provisional equality-QP contract

`solve_equality_qp` решает convex dense задачу
`min 0.5 xᵀHx + gᵀx` при `Ax = b`. Контракт пока не объявлен стабильным SDK
API, но уже соблюдает будущую ABI-границу:

- Eigen-типы не выходят из `.cpp`;
- входы и выходы передаются через strided views;
- input buffers snapshot-ятся до записи результата, поэтому input/output
  aliasing имеет определённую семантику;
- primal и equality-dual output buffers не должны пересекаться;
- outputs меняются только при `QpStatus::Optimal`;
- result содержит semantic status, diagnostic code, rank и KKT residuals.

Первый backend сознательно использует SVD равенств и spectral decomposition
reduced Hessian. Для текущих малых dense задач это даёт простой
rank-revealing путь и позволяет различать inconsistent equalities, линейное
unbounded направление, negative curvature и numerical failure. Быстрый
SPD-path через Cholesky/LDLT можно добавить позже как внутреннюю оптимизацию,
не меняя контракт.

Предварительные views намеренно не задают ownership, allocation, QP problem
layout или result/error model. Они нужны как нейтральная граница между
caller-owned buffers и private backend. Конкретные solver entry points должны
добавлять shape, finite-value и aliasing validation.

## Provisional active-set QP contract

`solve_active_set_qp` расширяет тот же контракт до convex dense задачи с
равенствами, общими неравенствами `Cx <= d` и отдельными lower/upper bounds.
Отсутствующее индивидуальное ограничение кодируется как `-inf` для lower и
`+inf` для upper; пустой view отключает всё семейство.

Основные свойства:

- equality, inequality, lower-bound и upper-bound duals возвращаются полными
  векторами фиксированного размера; неактивные множители равны нулю;
- warm primal принимается только как проверяемая допустимая точка, а optional
  active masks должны ссылаться на действительно tight constraints;
- без warm start допустимая точка строится отдельной Phase I QP с одной общей
  slack-переменной; положительный оптимальный slack означает `Infeasible`;
- рабочее множество обновляется детерминированно: blocking constraint
  добавляется ratio test-ом, отрицательный active multiplier удаляется;
- линейное recession direction проходит тот же ratio test: отсутствие blocker
  даёт `Unbounded`, а blocker превращается в новое active constraint;
- iteration limit и numerical residual failure различаются diagnostics;
- как и equality solver, функция snapshot-ит входы, запрещает пересекающиеся
  output buffers и записывает outputs только при `Optimal`.

Контракт предназначен для convex QP. Backend консервативно требует
положительную полуопределённость Hessian на nullspace исходных равенств, а не
пытается объявлять частный ограниченный срез неконвексной задачи допустимым.
Первый backend ориентирован на небольшие dense robotics/HQP задачи. Shared
oracle проверяет semantic statuses и KKT bounds, а дополнительный
детерминированный 2D corpus сравнивает результат с перебором active subsets,
не фиксируя число итераций или порядок рабочего множества.

## Native dense assembly и 2D multibody contract

`DenseBlockTopology` регистрирует именованные блоки до `finalize()` и выдаёт
стабильные topology-bound handles. Матрицы и векторы остаются caller-owned:
assembler только проверяет shape/stride/finite values и детерминированно
добавляет вклады в переданные views. Очистка storage всегда явная.

`DynamicsTopology` разделяет DOF и constraint blocks, а
`DynamicsAssembly` собирает:

- mass matrix `M`;
- generalized load `f`;
- constraint Jacobian `J`;
- acceleration-level right-hand side `γ`.

`solve_constrained_dynamics` решает equality QP, публикует физические reactions
с согласованным знаком и меняет output buffers только при `Optimal`. Таким
образом FEM, robotics и multibody могут переиспользовать один assembly/solver
слой, не завися от Eigen в публичном API.

`Multibody2DSystem` — первый пользователь этого слоя. Он использует world-frame
maximal velocities `[vₓ, vᵧ, ω]`, spatial inertia с локальным центром масс,
gravity/external loads, fixed-point и revolute constraints. Шаг состоит из
acceleration solve, semi-implicit integration, mass-metric position projection
и velocity projection. При ошибке состояние шага откатывается.

Публичный model API принимает `termin::Pose2`/`Vec2`, тела и joints через
typed handles. Ни `M`, ни `J`, ни Eigen не нужны обычному consumer-у.
Модель остаётся отдельной от игровой `termin-physics`: общий контракт между
движками появится только при доказанном runtime-сценарии.

`Multibody3DSystem` продолжает ту же maximal-coordinate модель с шестью DOF на
тело в порядке `[vₓ,vᵧ,v_z,ωₓ,ωᵧ,ω_z]`. `Pose3` и явные linear/angular поля
задают семантику; физический layout `Screw3` не используется как неявный
buffer contract. Spatial inertia хранится как масса, principal moments и
локальный inertia frame, где translation задаёт COM, а quaternion — главные
оси. Публичный helper записывает 6x6 матрицу в checked dense view без Eigen.

World-frame bias выводится в той же системе координат, что и generalized
velocities: центростремительный член для COM и `ω×(Iω)` для центральной
инерции. Body-frame spatial cross-force formula сюда напрямую неприменима.
Orientation интегрируется левым quaternion exponential update и нормализуется.
Fixed/two-body point joints дают три translational constraints и оставляют все
три относительных вращения свободными. Fixed/two-body revolute joints добавляют
две независимые строки выравнивания локальных hinge axes. Их position residual
строится через cross product осей, поэтому не зависит от знака quaternion;
acceleration RHS включает centripetal и смешанный velocity bias. Публичная
reaction для revolute разделена на anchor force и поперечный constraint torque;
его проекция на разрешённую hinge axis равна нулю.

Общий multibody oracle задаёт world-coordinate convention, `J a = γ`, знак
reactions, gravity convention, quaternion equivalence и допустимые invariant
bounds для 2D и 3D. Старый Python
`RevoluteJoint3D` классифицирован как reference-only/retire-name: фактически
это point/ball joint. Его данные можно перенести в `PointJoint3D`; для нового
native revolute вызывающий код обязан дополнительно задать ненулевые локальные
оси обоих joint frames. Нулевая ось отвергается как rank-deficient setup с
`InvalidJointAxis`.

## Что не делаем на первом этапе

- Не заменяем весь `termin-qopt` внешним QP solver-ом.
- Не делаем Eigen публичной частью ABI.
- Не переносим Python API один-в-один, если C++ модель требует более строгих
  типов и явных контрактов.
- Не добавляем fallback-слои без конкретного runtime-сценария.
- Не смешиваем этот стек с игровой физикой `termin-physics`, пока не появится
  осознанный общий контракт.

## Будущий sparse-вопрос

Текущий FEM assembler концептуально sparse, но в Python собирает плотные
`np.zeros(...)` матрицы. Это приемлемо для тестов и малых multibody-сцен, но
не масштабируется на реальные сетки.

После dense-порта нужно отдельно решить:

- какие системы остаются dense;
- какие матрицы собираются сразу как sparse;
- нужен ли внешний sparse/QP backend;
- где проходит граница между solver-ом и physics/FEM model assembly.

Eigen выбран так, чтобы этот переход был возможен без смены публичного API.
