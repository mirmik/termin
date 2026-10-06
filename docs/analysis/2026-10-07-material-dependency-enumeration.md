# Material dependency enumeration — #2895

Планировщик больше не собирает RenderItems для поиска material texture sources.
Обязательный C/C++/Python callback перечисляет выбранные материалы; producers
разделяют выбор с настоящим сбором. Runtime использует подготовленные target
views и scene/masks, GPU resources привязывает после зависимостей. DFS сохраняет
рёбра до рекурсии. Штатные producers и ChronoSquad мигрированы.

CargoTerminal проверен на Vulkan, окно 1600×1000, viewport 1052×614, Display0.
Chronosphere остановлена на step0/time0, выбран Arthur, проекции отключены.
Для сравнения изображения дополнительно остановлены AnimationController и
AnimationPlayer; SkeletonController продолжает подготовку skinning matrices.
Профайлер включён, его UI скрыт. Каждый sample содержит 120 прогретых кадров.

Контроль временно подменяет только material enumeration полным
RenderSceneItemCollector, сохраняя тот же контекст. Переключение между полным
и штатным лёгким callback выполнено в одном процессе на одной неподвижной сцене.
Контрольная библиотека находится только в `/tmp`, в SDK не установлена.

| CPU wall span, среднее за кадр | Полный сбор | Лёгкий callback |
| --- | ---: | ---: |
| Обход dependencies, 3 вызова | 2,464 мс | 0,365 мс |
| Настоящий Drawable collection, 3 вызова | 2,452 мс | 2,564 мс |
| SceneManager Render | 24,767 мс | 24,370 мс |
| Активная часть кадра | 26,551 мс | 26,230 мс |
| Encode mesh draw | 3128 | 3128 |

Стоимость самого обхода уменьшилась на 85%. Итоговое время кадра зависит от
нагрузки машины; выигрыш всей сцены не следует приравнивать к разнице двух
collection spans. GPU timings и allocations не измерялись.

RGB pixels игрового viewport совпали побитово, различающихся пикселей — 0.
SHA256: `212bd1caaebae273085585d79cb603e06d1d960b07bb5636865ca9974783c76b`.
Текущий scene state даёт 3128 draw calls, исторический захват #2893 давал 2008:
его суммарные timings напрямую с этим paired comparison не сравниваются.

SDK собран через `task build` с заполненным offline wheelhouse. `task test`:
native 268/268; Python 3687 passed и единственный прежний отказ #2885
(`test_native_textured_pixal3d_geometry_reference`, degenerate tangent vertex0).
Новые bridge/producer/planner regressions проходят. ChronoSquad controllers
пересобраны, CTest 13/13; CargoTerminal входит в Play и работает с новым ABI.

Отдельная проблема фаз OffMeshLink сохранена и записана в #2897. Повторные
наблюдения RingUBO overflow и отсутствующей transparent-фазы TimeSpirit добавлены
в существующие #2300 и ChronoSquad #190.

Полные агрегаты профайлера, методика и исходник контрольной подмены:
[JSON](2026-10-07-material-dependency-enumeration.json).
Логи сборки и тестов: `/tmp/termin-2895-build-complete.log`,
`/tmp/termin-2895-test-final.log`. Снимки и диагностические скрипты:
`/tmp/termin-2895-editor/`. Собственные сессии редактора закрыты.
