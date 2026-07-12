# Аудит миграции UI редактора на termin-gui-native

Дата: 2026-07-12

Обновление после первого parity milestone: canonical menu/chrome, editor log и
session status, external hierarchy observation, Profiler docking и все native
resource/tool inspector projections восстановлены. Исторические находки ниже
сохранены как основание миграции; актуальный остаток отмечен в матрице.

## Область аудита

Аудит сравнивает именно пользовательский интерфейс редактора в
`termin.editor_tcgui` и `termin.editor_native`: состав панелей, доступные
действия, маршрутизацию выбора, компоновку и визуальную иерархию. Возможности
самих `termin-gui` и `termin-gui-native` как библиотек здесь не сравниваются.

Источники:

- production-композиции `editor_tcgui/editor_window.py` и
  `editor_native/run_editor.py`;
- старый layout `editor_tcgui/editor_window_layout.py` и новый shell
  `editor_native/shell.py`;
- общие editor-core модели и обе их UI-проекции;
- live smoke нового редактора на проекте ChronoSquad через editor MCP;
- текущие карточки миграции #261 и #301–#306.

## Краткий вывод

Native-редактор уже пригоден для базового редактирования сцены: viewport,
иерархия, выбор сущностей, transform/component inspector, Rendering tree,
Display/Viewport/Render Target inspectors, Play/Stop, основные настройки и
диагностические окна работают.

Функциональные разрывы первого аудита закрыты: shell проецирует каноническое
меню, Project Browser поддерживает routing/mutations/drag-and-drop, все виды
Inspector имеют native projection, восстановлены editor log, side-docked
Profiler, Modules и базовый prefab workflow. Оставшаяся работа теперь относится
к завершению визуальной системы, production parity gates и формальному удалению
legacy `termin-gui` frontend после финального smoke.

## Матрица паритета панелей

| Область | Состояние | Что перенесено | Что отсутствует или разошлось |
|---|---|---|---|
| Scene hierarchy | Готово | Выбор, rename, duplicate, delete, visibility, reparent/reorder, collapse, GLB/prefab file drop и deferred observation внешних structure changes | Toolbar остаётся более явно командным, чем legacy; это визуальный, не функциональный остаток. |
| Rendering tree | В основном готово | Displays, viewports, internal entities, render targets, add/remove/rename, selection sync | Это один из наиболее полных срезов после последних исправлений. Нужен только общий parity smoke вместе с layout/selection regression gate. |
| Editor viewport | Готово | Рендер в native-resolution, resize, camera/input, picking, gizmo, display tabs, project drag-and-drop, overlays, fullscreen, Pause/Resume и prefab toolbar | Требуется финальный screenshot smoke после применения composition metrics. |
| Entity inspector | В основном готово | Name, UUID, layer, transform, component/SoA list, typed fields, undo-backed edits, material inline view, Foliage и Procedural Mesh projections | Add Component доступен только через context menu списка и хуже обнаруживается. Auxiliary/left panel extension contract не поддержан; native production код явно отвергает `left_panel`. |
| Resource/tool inspectors | Готово | Native host поддерживает все `InspectorKind`: самостоятельные Material, Texture preview/import, Mesh statistics/import, GLB statistics/reimport, Pipeline summary/editor handoff и lifecycle Tool panels | Длинные asset paths требуют общей truncation/tooltip policy на визуальном этапе. |
| Project Browser | Готово | Tree/grid/breadcrumb, routing, create/rename/delete/reveal/extract, scene/prefab activation и threshold drag payload в hierarchy/viewport | Финальный parity gate должен сохранить эти end-to-end сценарии. |
| Console | Готово | Отдельные накопительный editor/build log и Python Console | Разделение старых поверхностей восстановлено. |
| Profiler | Готово | Sampling, graph, table, controls и отдельный resizable right-side debug dock | Делит tabbed debug dock с Modules. |
| Modules | Готово | Состояния/dirty/stale, Rescan, Reload, Build, Clean, Rebuild, Unload, async build output и owner-thread commit | Live ChronoSquad показал пять загруженных модулей; операции покрыты controller/UI тестами. |
| Dialogs | В основном готово | Settings, Project Settings, About, scene properties, layers/flags, shadows, navigation settings, SpaceMouse, Scene Manager, Undo History, Audio, Framegraph, Quest/OpenXR | Layers & Flags заменил 64 индексированных поля двумя multiline areas; функционально возможно, но хуже видна связь строки с индексом. Build Profiles всё ещё не портирован, но это общий незавершённый feature, а не потеря уже доступного пункта основного старого меню. |
| Pipeline editor | Готово | Native node graph, open/save, context actions и file inspector/editor handoff | Покрыт общим resource routing. |
| Project extensions | Готово для production surface | Project menu/dialogs, interceptors, overlays, selection и lifecycle tool inspector registration | ChronoSquad адаптирован и проверен на native surface. |

## Актуальный остаток

1. Распространить `EditorUiMetrics` на оставшиеся dialogs и специализированные
   extension panels; основные shell/collection/inspector/debug поверхности уже
   используют общий контракт.
2. Добавить editor-level parity fixture, проверяющий canonical menu inventory,
   ключевые stable IDs, panel bounds, активный inspector kind и debug docking.
3. Выполнить финальный live smoke на ChronoSquad и тестовом проекте. Production
   переключатель `--ui=tcgui` и legacy frontend wiring уже удалены; последующее
   физическое удаление source-only `editor_tcgui` не блокирует runtime migration.

Разделы ниже описывают исходные находки аудита и сохранены как история причин;
они не являются текущим списком открытых дефектов.

## Конкретные функциональные регрессии

### P0/P1: основные команды редактора

Native shell не использует `build_editor_menu_spec()`, хотя эта спецификация уже
является каноническим описанием старого меню. Вместо неё в `shell.py` вручную
собран второй набор команд.

Следствия:

- отсутствуют Undo и Redo; `UndoStack` наполняется, а Undo History показывает
  историю, но применить undo/redo из native UI нельзя;
- видимые `Open Project`, `Quit`, `Scene Tree` и `Inspector` не подключены к
  обработчикам;
- отсутствуют New Project, Close Scene, Load Material, Load Components и Deploy
  Standard Library;
- отсутствует Fullscreen;
- отдельное Navigation menu исчезло, Agent Types и NavMesh Areas перенесены в
  Scene;
- Pipeline Editor перенесён из Scene в Debug;
- отсутствуют Modules, Camera Frustums, Surface Edge Debug Tool и Raw Detour
  Path Debug;
- изменены shortcut semantics: старый F6 запускал standalone build, в native F6
  закреплён за Python Console.

Это не просто различие оформления: часть пунктов выглядит интерактивной, но
является dead UI.

### P1: Project Browser не завершает пользовательские сценарии

Toolkit-neutral `ProjectBrowserController` уже умеет selection/activation и
часть context actions, но production native wiring задаёт callbacks, которые
только пишут путь в лог. Старый `ProjectFileActionController` выполнял
маршрутизацию по расширениям:

- `.scene` открывал сцену;
- `.prefab` входил в prefab editing;
- остальные файлы открывались во внешнем редакторе;
- selection материала, pipeline, texture, mesh и GLB переключал Inspector.

Старый browser также предоставлял create/rename/delete/reveal/extract и drag
payload. В native projection эти действия либо не представлены моделью, либо
не переданы в controller, либо не подключены к `FileGridWidget`.

### P1: Inspector Host охватывает не всю модель

Общий `InspectorModel` по-прежнему объявляет десять видов инспектора: Entity,
Material, Display, Viewport, Pipeline, Texture, Mesh, GLB, Render Target и Tool.
Native host обрабатывает четыре. Для любого другого вида он пишет error и
возвращает пустой Entity Inspector.

Это оставляет недоступными уже существовавшие UI:

- texture preview и flip/transpose import settings;
- mesh statistics и import axis/scale/UV settings;
- GLB statistics и reimport settings;
- pipeline passes/resource specs inspector;
- отдельный material inspector из Project Browser;
- tool-supplied inspector panels.

### P1: scene hierarchy не наблюдает внешние изменения

Legacy frontend подписывается на `tc.scene.structure_changed`, откладывает
rebuild до безопасной точки кадра и обновляет tree. Native frontend передаёт в
`SceneFileController` пустой `observe_scene_events` callback и больше нигде не
ставит аналогичную подписку. Собственные операции controller обновляют tree,
но сущности, созданные project code, Python console или runtime/editor tools,
могут оставаться невидимыми до ручного Refresh.

### P1: режимы редактирования и debug tooling

- `GameModeModel.toggle_pause()` существует, но native toolbar/controller не
  проецирует Pause/Resume;
- `PrefabEditController` и Save/Exit prefab toolbar не создаются;
- Modules panel отсутствует;
- встроенные tool inspector/debug panels отсутствуют;
- Fullscreen mode отсутствует.

### P1/P2: Console, status и title

Legacy frontend хранил editor log во вкладке Console и показывал
`Project | Scene | Edit/Play` в status bar и window title. Native frontend:

- использует Console как Python REPL;
- выводит build messages только в logger и временно перезаписывает status bar;
- передаёт `update_window_title=lambda: None`;
- передаёт `set_project_state=lambda ...: None`;
- оставляет фиксированный title `Termin Editor — Native UI`.

В результате теряется постоянный контекст проекта/сцены/режима и история
сообщений внутри приложения.

## Расхождения компоновки и визуальной системы

### Что уже улучшено

- базовая геометрия shell теперь близка к старому редактору: отдельные left,
  right и bottom splitters, узкие визуальные divider lines и широкий hit area;
- widths hierarchy/inspector и доля bottom panel подобраны по старому reference
  layout;
- foundational controls получили спокойные fills, небольшие radii и менее
  тяжёлые borders;
- Rendering inspectors и material/color controls стали визуально согласованнее
  с остальным inspector.

### Что ещё системно расходится

1. **Profiler расположен не в том измерении.** Документация называет его
   right-side slice, но production code вставляет его в вертикальный
   `workspace_host` перед display tabs.
2. **Toolbar workspace выше старого:** native резервирует 40 px, legacy — 32 px.
3. **Scene toolbar шумнее:** три текстовые команды вместо заголовка и одной
   небольшой collapse-кнопки.
4. **Inspector grid не единый:** label widths одновременно равны 72, 104, 112,
   130 и 150 px в разных native forms. Визуальные колонки прыгают при переходе
   между Entity, component fields, Rendering inspectors и dialogs.
5. **Density не токенизирована:** панели локально задают 22/24/26/28/30/32/36 px
   rows, padding 2/4/5/6 px и собственные fixed extents. Style guide описывает
   общую систему, но production composition почти не потребляет theme metrics.
6. **Слишком много status-like полос:** они используются не только как
   настоящий status, но и как read-only field, breadcrumb, subtitle и prompt.
   Это создаёт дополнительные горизонтальные линии и смешивает семантику.
7. **Нет editor-level visual regression gate.** Showcase/pixel tests проверяют
   primitives, но не ловят перемещение Profiler, исчезновение menu items,
   дрейф inspector columns или лишние полосы в production shell.

## Архитектурные причины

1. **Две спецификации меню.** `editor_core.menu_bar_model` каноничен только для
   tcgui; native shell держит собственный список и собственную маршрутизацию.
2. **Skeleton считался завершённой миграцией surface.** Project Browser и
   Inspector получили native widgets раньше, чем были подключены end-to-end
   workflows.
3. **Composition state живёт в огромном `init_editor_native()`.** Из-за этого
   title, console, project actions, scene observation и panel docking легко
   остаются локальными lambdas/no-op boundaries.
4. **Нет декларативной parity contract.** Checklist отмечает widget slices как
   ported, но не перечисляет старые пользовательские сценарии и не проверяет их
   через обе frontend projections.

## Рекомендуемый порядок завершения

### Этап 1 — вернуть базовые editor workflows

1. Сделать общий UI-neutral command/menu model источником истины для обеих
   frontend implementations.
2. Вернуть Undo/Redo, project lifecycle, Quit, Close Scene, Fullscreen,
   Pause/Resume и корректные shortcuts.
3. Разделить editor log Console и Python Console.
4. Восстановить project/scene/mode title/status model.

### Этап 2 — закончить Project и Inspector вертикальным срезом

1. Вынести `ProjectFileActionController` из tcgui package в editor_core.
2. Подключить selection/activation, create/rename/delete/reveal/extract и drag
   payload.
3. Добавить native resource/tool inspector projections и полный dispatch всех
   `InspectorKind`.
4. Вернуть prefab edit session и toolbar.

### Этап 3 — вернуть reactive/debug surfaces

1. Подписать native hierarchy на scene structure events с safe deferred rebuild.
2. Портировать Modules panel и asynchronous module operation dialog.
3. Вернуть Camera Frustums и встроенные debug/tool inspectors.
4. Перестроить Profiler как отдельный dock/splitter peer, а не child viewport.

### Этап 4 — довести визуальную систему

1. Ввести editor composition metrics: chrome heights, inspector label column,
   form row heights, panel padding, collection density и dock extents.
2. Убрать локальные размеры из панелей, где они выражают один и тот же token.
3. Добавить production editor screenshot/layout fixtures для обычного состояния,
   Entity Inspector, Rendering Inspector, Project/Console, Profiler и dialogs.
4. Проверять не только pixels, но и semantic inventory: top-level menus,
   command IDs, panel bounds и active inspector kind.

## Документационные несоответствия

- `docs/plans/2026-07-09-termin-gui-native-porting-checklist.md` помечает Project
  Browser и inspector slices выполненными, хотя end-to-end workflows выше ещё
  отсутствуют.
- тот же документ утверждает, что Profiler является fixed right-side slice;
  production layout показывает vertical workspace child.
- карточка #261 формулирует завершение как отсутствие production tcgui imports,
  но этого недостаточно: перед удалением legacy frontend нужен parity gate по
  пользовательским сценариям, перечисленным в этом аудите.
