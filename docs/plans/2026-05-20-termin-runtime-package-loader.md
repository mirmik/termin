# termin-runtime package loader

Дата: 2026-05-20

## Цель

`termin-runtime` - C++ слой для запуска собранного билда без Python. Первый практический сценарий: Android player получает каталог package artifacts, загружает ресурсы и создает `TcSceneRef`, после чего сцена рендерится обычным `MeshComponent` / `MeshRenderer` путем.

Это не замена `termin-assets`: editor/build side по-прежнему может жить в Python. `termin-runtime` должен читать уже собранные runtime artifacts.

## Текущий контракт пакета

Корень пакета содержит:

- `manifest.json`
- `scene.json`
- `meshes/*.tmesh.json`
- `materials/*.tmat.json`
- `shaders/*.shader.json`
- `shaders/vulkan/*.spv`

`manifest.json` задает `shader_artifact_root`, список resources и путь к scene.

## Реализовано

- Новый C++ target `termin_runtime`.
- `termin::runtime::RuntimePackageLoader`.
- Загрузка shader/material/mesh JSON ресурсов.
- Установка `tgfx2` shader artifact root для поиска SPIR-V.
- Создание runtime scene через C++ компоненты:
  - `MeshComponent`
  - `MeshRenderer`
  - `CameraComponent`
  - `LightComponent`
- Android player сначала пробует runtime package из assets, затем использует старую hardcoded сцену как fallback.
- Sample package для текущего Android triangle test лежит в `termin-android/assets`.

## Ограничения

- Scene JSON пока не проходит через штатный `TcSceneRef::from_json_string()`.
- Причина: C++ kind path для resource handles еще неполный, особенно для `TcMesh`.
- Mesh artifact пока JSON с interleaved float32 vertices и uint32 indices.
- Binary mesh/material artifacts и полноценная сцена из editor export - следующий слой.

## Следующие шаги

- Добавить C++ kind serialization/deserialization для `TcMesh`.
- Решить, будет ли runtime scene format совпадать со штатным `TcSceneRef` JSON или станет compiled scene format поверх тех же компонентов.
- Добавить build-side exporter из editor/build pipeline.
- На Android заменить fallback test scene на обязательную загрузку package, когда exporter будет готов.
