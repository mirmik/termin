# Scene recipes

`termin.scene_recipe` синхронизирует размещения из JSON-рецепта с живой сценой
Termin. Механика перенесена из ChronoSquad `tools/scene_recipe`.

## Размещение кода

- `model.py`: формат версии 1, стабильные ID, трёхстороннее слияние.
- `service.py`: операции `list`, `plan`, `sync`, `replace`, `reset-transform`
  через явный `SceneRecipeBackend`, без импортов движка или GUI.
- `cli.py`: команды для явно выбранной MCP-сессии и проекта.
- `termin.editor_core.scene_recipe_adapter`: сцена, native prefab, проверка
  ссылок, Undo/Redo и обновление редактора.

Пакет включён в SDK через общий manifest. Сборка — `task build`.
Проверки — `task test:python:setup`, затем
`task test:python -- editor/termin-scene-recipe/tests editor/termin-app/tests/test_scene_recipe_adapter.py`.

## Использование

Открыть проект в редакторе с MCP. Команды используют установленный SDK и не
требуют исходников ChronoSquad или изменения `sys.path`:

```bash
sdk/bin/termin_python -m termin.scene_recipe plan recipe.json \
  --session /path/to/session.json --project /path/to/project
sdk/bin/termin_python -m termin.scene_recipe sync recipe.json \
  --session /path/to/session.json --project /path/to/project
```

`--project` принимает директорию либо `.terminproj`; проект проверяется внутри
редактора до операции. Синхронизация не сохраняет сцену на диск: Save остаётся
отдельным действием. В Python/MCP-контексте редактора доступен тот же сервис:

```python
result = scene_recipe.run("plan", recipe)
result = scene_recipe.run("sync", recipe, resolutions={"cover": {"position": "scene"}})
result = scene_recipe.run("replace", recipe, selector="cover", prefab=prefab_uuid)
result = scene_recipe.run("reset-transform", recipe, selector="cover")
```

CLI поддерживает `--resolutions resolutions.json` для `sync`, `--id` для
адресных операций и `--prefab` для `replace`. Конфликты возвращают ненулевой
код. `plan` не меняет сцену, `sync` заново вычисляет план по текущему состоянию.

## Рецепт и состояние

```json
{
  "version": 1,
  "namespace": "e8dc4116-b591-43a5-8aba-28d38f7584fd",
  "objects": [{
    "id": "cover",
    "prefab": "64323ec8-a734-5003-bf60-6cd3d453c25c",
    "name": "Укрытие",
    "position": [1, 2, 0],
    "rotation": [0, 0, 0, 1],
    "scale": [1, 1, 1],
    "role": "cover",
    "zone": "south"
  }]
}
```

`namespace` и `id` постоянны. UUID контейнера вычисляется как
`UUID5(namespace, "placement/" + id)`; имя не является идентификатором.
В контейнере находится native prefab instance. Замена меняет содержимое,
сохраняя контейнер, его трансформ и ссылки на него.

Рецепт задаёт желаемые размещения. Metadata сцены `scene_recipe_v1` хранит
предыдущий рецепт и сведения о принадлежности объектов. Текущая сцена может
содержать ручные изменения. Prefab overrides отдельно управляют содержимым
экземпляров. Формат metadata и UUID сохранены при переносе.

Изменение только рецепта применяется, изменение только сцены сохраняется.
Различные изменения одного поля создают конфликт; весь sync остаётся без
изменений. Решение `scene` или `recipe` продвигает базу к новому рецепту.
Ручное удаление не восстанавливается неизменённым рецептом. При удалении из
рецепта можно сохранить изменённый объект и отвязать его от синхронизации.

Каждый sync/replacement/reset — одна команда Undo вместе с metadata.
Префабы проверяются перед изменениями; ошибка применения откатывает операцию.
`reset-transform` адресно сбрасывает трансформ контейнера и трансформы
source-owned сущностей текущего prefab, сохраняя остальные overrides.

## Сохранённые ограничения первого переноса

- Один namespace на сцену, размещения только в корне.
- Слияние полей размещения; произвольные компоненты рецептом не управляются.
- Fingerprint содержимого консервативен: обновление prefab source также может
  блокировать замену/удаление. Доработка учтена в ChronoSquad #2267.
- Защита ссылок видит типизированные `entity`/`list[entity]`, не UUID в строках
  или внешних файлах. Разрешение конфликта не отключает проверки безопасности.
- Генераторы геометрии, наборы ассетов, сборка акторов и NavMesh bake остаются
  обязанностью проекта.
