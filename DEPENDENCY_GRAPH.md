# Termin-env Dependency Graph

Документ фиксирует зависимости в формате:
- `Пакет A` **зависит от** `Пакет B`

Актуально на 2026-03-05.

## 1) C/C++ зависимости (кто от кого зависит)

- `termin-base` зависит от: _нет внутренних зависимостей termin-env_.
- `termin-mesh` зависит от: `termin-base`.
- `termin-graphics` зависит от: `termin-base`, `termin-mesh`.
- `termin-inspect` зависит от: `termin-base`.
- `termin-scene` зависит от: `termin-base`, `termin-inspect`.
- `termin-collision` зависит от: `termin-base`, `termin-mesh`, `termin-inspect`, `termin-scene`.
- `termin/core_c (termin_core)` зависит от: `termin-base`, `termin-graphics`, `termin-inspect`, `termin-scene`.
- `termin/cpp + termin (app)` зависит от: `termin-graphics`, `termin-inspect`, `termin-scene`, `termin-collision`, `termin/core_c`.

## 2) Python зависимости (кто от кого зависит)

- `tcbase` (из `termin-base`) зависит от: _нет внутренних python-зависимостей termin-env_.
- `tmesh` (из `termin-mesh`) зависит от: `tcbase` (+ `numpy` как внешний пакет).
- `tgfx` (из `termin-graphics`) зависит от: `tcbase`, `tmesh` (+ `numpy` как внешний пакет).
- `tcgui` (из `termin-gui`) зависит от: `tcbase`, `tgfx` (+ `Pillow`, `PyYAML` как внешние пакеты).
- `termin-nodegraph` (из `termin-nodegraph`) зависит от: `tcbase`, `tgfx`, `tcgui`.
- `diffusion-editor` (из `diffusion-editor`) зависит от: `tcbase`, `tgfx`, `tcgui` (+ `numpy`, `Pillow`, `diffusers`, `simple-lama-inpainting`, `torch` как внешние пакеты/транзитивные зависимости ML-стека).

## 3) Рекомендуемый порядок сборки (topological order)

1. `termin-base`
2. `termin-mesh`
3. `termin-graphics`
4. `termin-inspect`
5. `termin-scene`
6. `termin-collision`
7. `termin-gui`
8. `termin-nodegraph`
9. `termin`
10. `diffusion-editor` (как отдельное приложение поверх python-стека termin)

## 4) Опциональные зависимости

- `termin-inspect` при `TI_BUILD_PYTHON=ON` дополнительно зависит от `Python::Python` и `nanobind`.
- `termin-scene` при `TERMIN_SCENE_ENABLE_PYTHON=ON` дополнительно зависит от `Python::Python` и `nanobind`.
- `termin-collision` при `TERMIN_COLLISION_ENABLE_PYTHON=ON` дополнительно зависит от `Python::Python` и `nanobind`.

## 5) Пакеты вне основного графа

- `termin-modules`: явный граф зависимостей пока не оформлен.
