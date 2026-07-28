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
- Python реализация пока остаётся reference implementation.

Инициатива ведётся в Kanboard swimlane `Native QOpt, FEM & Robotics`,
umbrella #980. Foundation закрыт в #981, solver oracle — в #984.

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
6. Перенести nullspace helpers: QR basis first, SVD basis only where needed.
7. Перенести `HQPSolver`, `Level`, `QuadraticTask`, constraints.
8. Перенести multibody/FEM assembler поверх того же solver API.
9. Добавить Python re-export/bindings только после стабилизации C++ контрактов.
10. Отдельно оценить sparse backend для больших FEM-систем.

Oracle не объявляет текущее Python-поведение правильным по умолчанию.
Оптимальные случаи проверяются через primal/KKT bounds, nullspace — через
инварианты подпространства, HQP — через сохранение старших приоритетов.
`infeasible`, `unbounded` и `invalid_input` имеют независимые certificates или
структурную диагностику; текущий Python API не считается совместимым с ними,
пока не начнёт возвращать semantic status.

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
