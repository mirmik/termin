# Анализ классов-дубликатов

Дата: 2026-04-29
Скрипт: `dublicate-search.py`

## 🔴 Высокий приоритет — точные дубликаты

### RaycastHit
- **termin-app/termin/colliders/raycast_hit.py**
- **termin-collision/python/termin/colliders/raycast_hit.py**

Байт-в-байт одинаковые (15 строк). Один нужно удалить, импортировать из termin-collision.

### PhysicsWorldComponent (тройная копия)
- **termin-physics/python/termin/physics/physics_world_component.py** (205 строк)
- **termin-components/termin-components-physics/python/termin/physics/physics_world_component.py** (205 строк) — идентична termin-physics
- **termin-app/termin/physics_components/physics_world_component.py** (209 строк) — почти копия, docstring "canonical import path", добавлен `log.error`

termin-physics и termin-components-physics — байт-в-байт одинаковые. termin-app — почти копия с minor drift.

### RigidBodyComponent (тройная копия)
- **termin-physics/python/termin/physics/rigid_body_component.py** (211 строк)
- **termin-components/termin-components-physics/python/termin/physics/rigid_body_component.py** (211 строк) — идентична termin-physics
- **termin-app/termin/physics_components/rigid_body_component.py** (211 строк) — docstring "canonical import path", reorder импортов

Та же картина — тройная копия.

---

## 🟡 Средний приоритет

### VoxelizeSource (enum)
- **termin-navmesh/python/termin/navmesh/builder_component.py** — внутри `NavMeshBuilderComponent`
- **termin-app/termin/voxels/voxelizer_component.py** — внутри `VoxelizerComponent`

Одинаковые значения (`CURRENT_MESH=0`, `ALL_DESCENDANTS=1`), разные docstrings (EN vs RU). Нужно вынести enum в общее место.

### _DropListWidget (маленький дубликат)
- **termin-app/termin/editor/widgets/entity_list_widget.py** — хардкод для entity drops
- **termin-app/termin/editor/widgets/generic_list_widget.py** — generic версия с callback-ами

~30 строк. Entity-версию можно заменить на generic с правильными callback-ами.

---

## 🟢 Шум — не проблемы

| Класс | Причина |
|-------|---------|
| **BuildExt** в setup.py | По одному на модуль, паттерн |
| **BackendWindowManager** | parent/child (editor_tcgui наследуется от termin-display) |
| **NodeGraphView** | разные UI фреймворки: tcgui vs PyQt6 |
| **ColorDialog** | параллельные реализации: tcgui (367 строк) vs PyQt6 (818 строк) |
| **FrameTimeGraph** | та же логика, разные API рендера: tcgui vs QPainter |
| **SpinBox** | tcgui — полноценный виджет (344 строки), app — тонкий Qt wrapper (20 строк) |
| **FieldWidgets\*** (13 классов) | intentional parallel: PyQt6 версия в `editor/` и tcgui версия в `editor_tcgui/` |
| **EntityInspector, ProfilerPanel, TransformInspector, ModulesPanel...** | та же картина: Qt vs tcgui бэкенды |
| **Portal** | разные классы с одинаковым именем в разных модулях navmesh |
| **Screw2** | разные модули geombase vs ga201 |
| **World** | один в ARCHIVE/ |
| **Settings, EditorWindow** | разные проекты (diffusion-editor vs termin-app) |
| **TransformationProbe, _Pipeline, _Viewport, DummyPass** | тестовые хелперы |
| **Jacobian, SensorPoint, Link, Manipulator** | в `expers/` — эксперименты |
| **MyComponent** | один в `project/`, другой в `аааа/` (мусорная папка) |

---

## Контекст: два UI бэкенда в termin-app

`termin-app/termin/editor/` — PyQt6 бэкенд (legacy fallback, `--ui=qt`)
`termin-app/termin/editor_tcgui/` — tcgui бэкенд (новый дефолт, `--ui=tcgui`)

editor_tcgui импортирует из editor (UndoStack, SceneManager, EditorSettings и т.д.), но не наоборот.
Последняя активность: editor_tcgui — 2026-04-29, editor — 2026-04-28.

Дубликаты виджетов между этими директориями — **интенциональные** параллельные реализации для разных UI фреймворков.
