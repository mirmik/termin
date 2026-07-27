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
- solver problem/result contracts ещё не зафиксированы;
- Python реализация пока остаётся reference implementation.

Инициатива ведётся в Kanboard swimlane `Native QOpt, FEM & Robotics`,
umbrella #980. Foundation закрыт в #981; следующий executable шаг — oracle #984.

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
3. Перенести `solve_qp_equalities`.
4. Перенести `solve_qp_active_set`.
5. Перенести nullspace helpers: QR basis first, SVD basis only where needed.
6. Перенести `HQPSolver`, `Level`, `QuadraticTask`, constraints.
7. Перенести multibody/FEM assembler поверх того же solver API.
8. Добавить Python re-export/bindings только после стабилизации C++ контрактов.
9. Отдельно оценить sparse backend для больших FEM-систем.

Предварительные views намеренно не задают ownership, allocation, QP problem
layout или result/error model. Они нужны как нейтральная граница между
caller-owned buffers и private backend. Конкретные solver entry points должны
добавлять shape, finite-value и aliasing validation.

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
