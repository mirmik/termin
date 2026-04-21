# Рефакторинг редактора: Model/View decoupling

## Контекст

В проекте две реализации редактора:
- `termin/editor/` — Qt6, "золотой стандарт", работает лучше
- `termin/editor_tcgui/` — tcgui, активная миграция (см. `migration-tcgui.md`), местами расходится с Qt

Цель — вынести бизнес-логику в UI-agnostic слой, чтобы оба view делили одну модель и отличались только рендером/ивентами. Устранить дублирование и причину расхождений поведения между редакторами.

## Цели

- UI-agnostic модель в `termin/editor_core/`
- Qt и tcgui view используют одни и те же Controller/Model/Services
- Удалить дублирование логики между `editor/` и `editor_tcgui/`

## Не-цели

- Не переписываем Qt редактор — он остаётся, пока tcgui не догонит
- Не трогаем уже чистые модули: `undo_stack`, `editor_commands`, `editor_state_io`, `file_processors/`
- Не меняем C++ core

## Архитектура

```
  View(Qt)  View(tcgui)           — widgets, layouts, event→action
      \      /
       Controller                 — тонкий: переводит view events в model calls
           │
         Model  ──→ Observers     — состояние + бизнес-логика, наблюдаемое
           │
       Services                   — DialogService, FileService — интерфейсы
           │                        с двумя реализациями (Qt/tcgui)
       Engine core (C++)
```

### Строительные блоки

- **Observable/Signal** — маленький pub/sub, без Qt, без tcgui
- **DialogService** (abstract): `show_message / show_confirm / show_input / open_file / save_file`
- **FileService** (abstract): watcher, external editor launch
- **Model** классы — чистый Python, только engine API + наблюдатели

## Фазы

### Фаза 0 — Подготовка (1-2 дня)

- Создать `termin/editor_core/` — новый UI-agnostic слой
- Observable/Signal примитив (взять из tcbase если есть, иначе ~50 строк)
- Интерфейсы `DialogService`, `FileService` (только сигнатуры)
- Qt и tcgui реализации интерфейсов (обёртки поверх существующего)

### Фаза 1 — Pilot: SceneTree (3-4 дня)

- `editor_core/scene_tree_model.py`: `EntityOperations` (create/delete/rename/reparent/duplicate), наблюдаемый список entity
- `SceneTreeController` (Qt) → `EntityOperations` + `DialogService`
- `SceneTreeControllerTcgui` — тот же код операций
- **Done когда**: одинаковое поведение add/delete/rename в обоих редакторах (smoke-test)
- **Ценность**: отработать паттерн до применения на большом

### Фаза 2 — Inspector Model (2 дня)

- `editor_core/inspector_model.py`: какой инспектор активен, какая entity/asset редактируется
- Qt `InspectorController` и tcgui `InspectorControllerTcgui` подписываются на модель
- Убираем дублирование выбора "какой инспектор показать"

### Фаза 3 — Rendering Model (неделя+, самая рискованная)

- Предварительно: портировать `ViewportListWidget` на tcgui (сейчас заглушка `_NoOpViewportList`)
- `editor_core/rendering_model.py`: Display/Viewport state + CRUD (~500 LOC из 1398)
- Qt `RenderingController` усыхает до view: табы, QWindow embed, сигналы
- tcgui `RenderingController` дотягивается до паритета с Qt
- Резерв времени 50% — может вылезти SDL embedding, shared device, сигналы

### Фаза 4 — Диалоги (параллельно с 1-3 по мере надобности)

- Все `QDialog` → `DialogService` API
- Стартуем с view-specific реализаций (каждый диалог пишется дважды, просто)
- К универсальному form-builder переходим только если обнаружится реальная польза

### Фаза 5 — Cleanup (2-3 дня)

- Сверка паритета Qt vs tcgui (панели, диалоги, поведение)
- Удаление дубликатов из `editor/` и `editor_tcgui/`
- Короткий doc про новую архитектуру

## Оценка и риски

| Фаза | Срок | Риск |
|------|------|------|
| 0 | 1-2 д | низкий |
| 1 (pilot) | 3-4 д | средний (отрабатываем паттерн) |
| 2 | 2 д | низкий |
| 3 | 7-10 д | **высокий** (RenderingController, SDL embed) |
| 4 | 5-7 д | средний (рутина) |
| 5 | 2-3 д | низкий |

**Итого: ~4 недели на одного dev** + запас 30-50% на неожиданное.

### Главные риски

1. **RenderingController** — возможно потребуется пересобрать Фазу 3 после аналитики
2. **Threading** — engine тикает в своём цикле, view в своём; Observable должен быть thread-safe или callbacks marshalled в UI thread
3. **Паритет инспекторов** — Qt показывает debug info, которого нет в tcgui; надо решить что считать правдой

## Что уже разделено (не трогаем)

- `undo_stack.py`, `editor_commands.py` — чистые, без Qt
- `editor_state_io.py` — callback-based
- `scene_manager.py`, `project_file_watcher.py`, `settings.py` — UI-agnostic обёртки
- `file_processors/` — полностью UI-agnostic
- `EntityInspector` (базовый) — в tcgui уже callback-based
- `FieldWidgets` — в tcgui уже UI-agnostic версия

## Где логика вшита в UI (топ-5)

1. **`editor/rendering_controller.py`** (1398 LOC) — QTabWidget + QWindow + SDL embedding + CRUD всё вместе
2. **`editor/scene_tree_controller.py`** — 80% чисто, `QMessageBox`/`QInputDialog` вшиты в handlers
3. **`editor/inspector_controller.py`** — логика выбора инспектора прибита к `QStackedWidget` индексам
4. **Диалоги (15+ штук)** — каждый `QDialog` с внутренней логикой; tcgui часть уже дублирует
5. **`ViewportListWidget` (Qt)** vs `_NoOpViewportList` заглушка в tcgui — прямая причина расхождений в панелях рендеринга

## Журнал

Начат: 2026-04-21.
