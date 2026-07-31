# Архитектура редактора

Редактор имеет один production frontend: `termin-gui-native`. Старые Qt/PyQt и
tcgui frontend-проекции удалены. Библиотека `termin-gui` остаётся отдельным
toolkit для non-editor consumers и не входит в editor application payload.

Cross-module ownership между application host, `EditorSession` и `EngineCore`
зафиксирован в
[протоколе архитектурного совета](https://github.com/mirmik/termin-monorepo/blob/master/docs/architecture-council/2026-07-19-engine-loop-client-and-editor-session.md).

## Слои

```text
termin_editor C++ host
  └─ termin.editor.run_editor
       └─ termin.editor_native        native widgets and composition
            └─ termin.editor_core     UI-neutral models and services
                 └─ scene/render/assets/domain packages
```

`termin/editor/run_editor.py` является тонким canonical entrypoint. Он не
выбирает frontend и не владеет альтернативным UI lifecycle.

`termin/editor_native/` владеет:

- native widget projections, dialogs и panel composition;
- window/content registration через `EditorWindowRegistry`;
- binding widget events к UI-neutral models;
- native multi-window и offscreen presentation adapters;
- `EditorSession` и упорядоченным teardown application-level ресурсов.

`termin/editor_core/` владеет:

- editor state и models;
- project/scene/resource operations;
- menu command inventory;
- UI-neutral controller/service contracts;
- сериализуемое состояние editor camera и других editor-only сущностей.

Правило границы: `editor_core` не импортирует `termin.gui_native`, `tcgui` или
любой другой widget toolkit. Frontend вызывает core; core не знает о типах
виджетов.

## Composition и lifecycle

C++ host создаёт `EngineCore` и передаёт borrowed engine capsule в Python
entrypoint. `init_editor_native()` собирает session и возвращает её host-у.
Engine loop принадлежит host/engine, а session отвечает за editor resources:

1. `prepare_engine_shutdown()` отсоединяет editor participation до остановки
   engine;
2. `EngineCore.shutdown()` завершает runtime;
3. `EditorSession.close()` освобождает окна, documents и Python-owned state.

Ошибки teardown не замалчиваются: каждая фаза выполняется через `finally`, а
первичная ошибка сохраняется.

## Основные composition roots

- `editor_native/run_editor.py` — сборка production editor session;
- `editor_native/shell.py` — главное меню и shell;
- `editor_native/ui_host.py` — widget content, rendering и input;
- `editor_native/project_session_controller.py` — native projection общего
  project lifecycle;
- `editor_native/inspector_host.py` — routing всех `InspectorKind`;
- `editor_native/project_browser.py` — project tree/grid и file actions;
- `editor_native/rendering_inspectors.py` — displays, viewports и render
  targets;
- `editor_native/editor_session.py` — explicit staged teardown.

UI-neutral models и операции остаются в `editor_core`, например
`entity_operations.py`, `inspector_model.py`, `rendering_model.py`,
`project_session_controller.py`, `menu_bar_model.py` и
`framegraph_debugger_service.py`.

## Состояние редактора в сцене

Сериализуемое editor-only состояние хранится в верхнеуровневой секции
`editor` файла `.scene`. Состояние editor camera имеет единственный
канонический путь `editor.camera`; `scene.metadata` не используется как его
вторая копия.

Старый путь `scene.metadata.termin.editor.entities_data` поддерживается только
для однократного чтения: при присоединении сцены данные извлекаются и удаляются
из metadata. Между переключениями сцен несохранённое состояние камер держит
`EditorSceneAttachment`, адресуя его поколенческим handle сцены. Это не
возвращает служебные editor entities в пользовательскую metadata и не смешивает
сцены при повторном использовании slot-а.

## Как расширять редактор

### Новая scene-операция

1. Добавить UI-neutral действие в `editor_core`.
2. Передать все fallible domain errors через лог и явный result/exception.
3. Добавить undo command, если операция меняет пользовательские данные.
4. Спроецировать действие в native hierarchy, viewport или menu.
5. Покрыть отдельно model behavior и native binding.

### Новый inspector kind

1. Добавить `InspectorKind` и request API в `editor_core/inspector_model.py`.
2. Реализовать native projection в `editor_native`.
3. Подключить routing в `inspector_host.py`.
4. Проверить selection sync, lifecycle target-а и отсутствие пустого fallback.

### Новый диалог

Если диалог вызывается core-операцией, расширить UI-neutral service contract и
реализовать его в native composition. UI-specific окна можно создавать в
`editor_native`, не протаскивая widget types в core.

## Presentation

Локальные настройки редактора независимо управляют:

- `VSync` — presentation mode окна;
- `FPS Limit` — программный лимит главного цикла `EngineCore`.

`FPS Limit = 0` означает Unlimited. Значение по умолчанию — 60 FPS: при
отсутствии repaint VSync сам по себе не обязан ограничивать пустой editor tick.

## SDK и тестовое окружение

Редактор запускается из проверенного SDK:

```bash
./build-sdk.sh
./sdk/bin/termin_editor /path/to/Project.terminproj
```

Python-тесты используют bundled Python и checkout overlay, создаваемый
`./setup-sdk-python-env.sh`. Копировать Python или native modules вручную в SDK
либо исходники не требуется.
