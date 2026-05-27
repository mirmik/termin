# termin-qopt C++ migration intent

Дата: 2026-05-27

Статус: декларация намерений. Это не финальная спецификация API, а рабочая
рамка для будущего переноса `termin-qopt` из Python/NumPy/SciPy в C++.

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

1. Добавить C++ target `termin-qopt`.
2. Ввести минимальные public data contracts для dense vector/matrix views.
3. Перенести `solve_qp_equalities`.
4. Перенести `solve_qp_active_set`.
5. Перенести nullspace helpers: QR basis first, SVD basis only where needed.
6. Перенести `HQPSolver`, `Level`, `QuadraticTask`, constraints.
7. Перенести multibody/FEM assembler поверх того же solver API.
8. Добавить Python re-export/bindings только после стабилизации C++ контрактов.
9. Отдельно оценить sparse backend для больших FEM-систем.

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
