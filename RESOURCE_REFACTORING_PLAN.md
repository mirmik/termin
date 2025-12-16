# План рефакторинга ресурсной системы

## Этап 1: Identifiable ✅
- [x] Создать `Identifiable` базовый класс (uuid, runtime_id)
- [x] Подмешать в `Entity`, `Scene`, `Display`, `Viewport`
- [x] Обновить сериализацию — писать uuid (но не использовать для ссылок)

## Этап 2: Asset базовый класс ✅
- [x] Создать `Asset(Identifiable)` с version, source_path, ленивой загрузкой
- [x] Базовый класс готов, логика Keeper'ов будет перенесена в конкретные Asset'ы

## Этап 3: MeshAsset ✅
- [x] Создать `MeshAsset` (хранит Mesh3)
- [x] Создать `MeshGPU` (временное решение для GPU handles)
- [x] Обновить `MeshHandle` → ссылается на `MeshAsset`
- [x] `MeshDrawable` = `MeshHandle` + `MeshGPU` (обёртка для обратной совместимости)
- [x] Удалить inline сериализацию меша
- [ ] (позже) Удалить `MeshDrawable` когда не нужна обратная совместимость

## Этап 4: TextureAsset ✅
- [x] Создать `TextureData` (numpy массив, сырые данные)
- [x] Создать `TextureAsset` (хранит TextureData)
- [x] Создать `TextureGPU` (временное решение)
- [x] Обновить `TextureHandle` → ссылается на `TextureAsset`
- [x] `Texture` = `TextureHandle` + `TextureGPU` (обёртка для обратной совместимости)
- [ ] (позже) Удалить `Texture` когда не нужна обратная совместимость

## Этап 5: MaterialAsset ✅
- [x] Создать `MaterialAsset` (хранит Material)
- [x] Обновить `MaterialHandle` → ссылается на `MaterialAsset`
- [x] Удалить `MaterialKeeper`

## Этап 6: ShaderAsset ✅
- [x] Создать `ShaderAsset` (хранит ShaderMultyPhaseProgramm)
- [x] Создать `ShaderHandle`
- [x] Удалить `ShaderKeeper`

## Этап 7: Убрать Keeper'ы ✅
- [x] `MeshHandle` → напрямую ищет в ResourceManager
- [x] `TextureHandle` → напрямую ищет в ResourceManager
- [x] `MaterialHandle` → напрямую ищет в ResourceManager
- [x] `ShaderHandle` → напрямую ищет в ResourceManager
- [x] `VoxelGridHandle` → через `VoxelGridAsset`
- [x] `NavMeshHandle` → через `NavMeshAsset`
- [x] `AnimationClipHandle` → через `AnimationClipAsset`
- [x] Обновить `ResourceManager` — хранить Asset'ы напрямую

## Этап 8: Остальные Asset'ы ✅
- [x] `VoxelGridAsset` + убрать `VoxelGridKeeper`
- [x] `NavMeshAsset` + убрать `NavMeshKeeper`
- [x] `AnimationClipAsset` + убрать `AnimationClipKeeper`

## Этап 9: ResourceManager
- [ ] Убрать дублирование (dict ресурсов + dict keeper'ов)
- [ ] Единое хранение Asset'ов
- [ ] Обновить hot-reload логику

## Этап 9: Встроенные примитивы
- [ ] Зарегистрировать cube, sphere, plane с фиксированными uuid
