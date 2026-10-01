# Состояние Termin и приоритеты открытой доски

Аудит от 30 сентября 2026 года по checkout `0090a078f` и актуальной доске Termin. Цель — определить полезную следующую работу для платформы, на которой уже разрабатываются приложения.

Главный вывод: следующие вложения стоит направить в надёжность повторного использования редактора, ресурсов и модулей, затем в поставку самостоятельных приложений и завершение уже начатых миграций. Большая доска преувеличивает объём отсутствующих возможностей: она одновременно содержит реальные дефекты, выполненные этапы, остатки миграций и несколько самостоятельных будущих продуктов.

Обновление после начала реализации: #1869 исправлена и закрыта. Handle-based loading и потребители защищены от перемещения/замены registry storage через callbacks; добавлены регрессии, штатные `task build` и `task test` прошли на Linux/lavapipe. Актуальный контракт описан в [документации ресурсного слоя](../canonical-c-layer-resource-storage.md). Ниже сохранён исходный срез аудита, включая состояния доски до реализации.

Прочитана выгрузка всех активных карточек; для выбранных направлений проверены исходники, комментарии и закрытые дочерние задачи. Это статический аудит и сверка истории. Полная сборка, тесты, Windows/Quest/GPU smoke и воспроизведение зависаний в этой сессии не выполнялись. Исторические результаты проверок ниже принадлежат соответствующим карточкам, а не этому аудиту.

## Состояние доски

На начало аудита: 205 активных и 1323 закрытые карточки. Закрытые включают выполненные, отменённые и объединённые задачи; это не счётчик реализованных возможностей.

| Колонка | Количество на начало |
| --- | ---: |
| Backlog | 173 |
| Blocked | 9 |
| Ready | 18 |
| In Progress | 2 |
| On Test | 3 |

Среди открытых: 55 с тегом `bug`, 43 `umbrella`, 17 `decision`. Категории пересекаются. Тег bug сам по себе не доказывает воспроизводимость: часть карточек содержит наблюдение или гипотезу.

Обе карточки In Progress — крупные зонты: #1640 декомпозиция больших исходников и #1501 native nodegraph. Поэтому колонка плохо показывает конкретную текущую работу. `Common` содержит 69 карточек, `Architecture` — 39, `Graphics & Render` — 29; технические дефекты распределены между этими полосами и не имеют единого видимого приоритета.

## Что уже работает и почему объём доски вводит в заблуждение

В сентябрьской истории есть native bindings пользовательских библиотек, навигация между stitched surfaces, retained 3D и сферические графики, static mesh batching, обновления профайлера и shader handles. Платформа продолжает развиваться через потребляющие проекты.

| Направление | Фактическое состояние | Что делать с планом |
| --- | --- | --- |
| Standalone desktop, #27 | Pipeline, runtime package, Python runtime, relocatable foundation и прежние shutdown fixes уже выполнены по карточке | Работать с остатками #32/#39/#109/#116, не начинать standalone заново |
| Native GLB, #1407 | Все #1408–1413 закрыты; #1413 фиксирует cgltf default для `.glb`, 64 теста, corpus и editor reload checks | Сильный кандидат закрыть umbrella после сверки финального acceptance; `.gltf` и explicit validation override намеренно сохраняют Python parser |
| Навигация сцен, #1802 | #1803 и визуальный acceptance #1796 закрыты; есть WorldContext.transition_to и test-projects/world-controller-scene-cycle | Кандидат закрыть родителя; поздние lifecycle баги вести отдельно |
| Monorepo, #1631–1634 | Core/Graphics уже внутри общей root build/test инфраструктуры; профили и Task interface присутствуют | Сверить остаточный acceptance и завершить старую migration bookkeeping |
| Цветовой тракт, #1045/#1398 | Typed SrgbColor/LinearColor, UBO decode и export metadata уже существуют; #1400–1405 закрыты | #1398 — кандидат закрыть; #1045 сузить до оставшегося, включая #1047 HDR/EXR |
| Retained charts, #1095/#1102/#1348 | Есть native и C# MultiChart2D, retained 3D, spherical mode и WPF examples | Уточнить недостающие операции и consumers; не создавать composer повторно |
| Native QOpt, #980 | Native QP/active-set/HQP/dense assembly уже есть, robotics/physics-qopt выделены | Обновить устаревшее описание Python-only; bindings/sparse/FEM/platform work оценивать отдельно |
| Web, #1235 | Есть packaged runtime, WebGPU, input/canvas lifecycle и Chromium gate | Переписать umbrella на остаток; viewer foundation не означает готовый project gameplay contract |

Существование реализации не равно проверке всего acceptance. В частности, #1102 нельзя закрывать только по наличию MultiChart2D: произвольные insert/remove/reorder панелей не подтверждены. #2537 уже правильно ждёт interactive Windows D3DImage smoke.

## Что чинить в первую очередь

### Безопасность ресурсов и сохранение данных

**#1869 — риск обращения к освобождённой памяти при lazy load.** В [tc_resource.h](https://github.com/mirmik/termin/blob/master/core/termin-base/include/tcbase/tc_resource.h) helper вызывает пользовательскую загрузку и затем пишет `header->is_loaded` через прежний указатель (строки 80–87). Загрузчик может расширить перемещаемый pool. Небезопасный helper всё ещё вызывается для mesh, texture и animation; это подтверждено текущими исходниками. Исправление должно reacquire handle после callback и охватить потребителей animation, удерживающих указатели через callbacks. Это ограниченная работа по корректности, без необходимости сначала переделывать всю архитектуру ресурсов.

**#1871 — `.tanim` не сохраняет содержимое анимации.** [clip_io.py](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/python/termin/animation/clip_io.py) пишет результат `clip.serialize()`, а [animation_module.cpp](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/cpp/bindings/animation_module.cpp) на строках 348–358 возвращает только UUID, имя и тип ссылки. Tracks/channels в файл не попадают. В том же процессе поиск уже живого clip по UUID способен скрыть проблему; приёмку следует проводить с очисткой registry либо в другом процессе. Нужен настоящий файловый round-trip typed tracks с проверкой STEP/CUBICSPLINE/weights и повреждённых данных. Дефект подтверждён чтением кода; новый runtime round-trip не запускался.

**#1931 — shutdown при удержанных Python wrappers.** Карточка содержит минимальный crash reproduction Entity + PerspectiveCameraComponent + shutdown_player. Это отдельный важный lifecycle contract. В данном аудите crash не воспроизводился, поэтому сначала следует повторить короткий сценарий на актуальном SDK. #629 дополнительно описывает невыраженные ошибки/повтор shutdown; `_run_shutdown_step` по-прежнему логирует и подавляет исключения. Не смешивать crash fix с большой дискуссией обо всех lifecycle API.

### Длительная работа редактора и hot reload

**#2608 — зависания оконного редактора.** В карточке повторные наблюдения 23, 26 и 27 сентября: зависает запуск, reload или работа уже открытой сцены; MCP перестаёт обслуживаться, SIGTERM не завершает процесс. Headless сценарии проходили. Причина не установлена, и название «на загрузке C++ модуля» описывает лишь часть фактических наблюдений. Следующий результат — диагностируемое минимальное воспроизведение с фазой ожидания и стеками, затем конкретный фикс. Не считать headless workaround решением оконного дефекта.

**#2471 — следующий Play блокируется после Stop и reload.** Повторно наблюдалось в Avalon и ChronoSquad; ошибки `Entity is invalid` при отзыве component facets. Удержанные MCP/Python ссылки — предполагаемый триггер, не установленная причина. Сценарий с внешними ссылками стоит включить в lifecycle regressions вместе с обычным Play/Stop.

**#2674 — внешняя сборка модуля не гарантирует reload.** Подтверждено статически: [module_types.hpp](https://github.com/mirmik/termin/blob/master/engine/termin-modules/include/termin_modules/module_types.hpp) хранит пути загруженного artifact без его fingerprint; [module_cpp_backend.cpp](https://github.com/mirmik/termin/blob/master/engine/termin-modules/src/module_cpp_backend.cpp) сравнивает inputs только с artifact на диске; [runtime.py](https://github.com/mirmik/termin/blob/master/editor/termin-project-modules/python/termin/project_modules/runtime.py) объединяет dirty и needs_rebuild. Уже собранный внешним процессом B может считаться актуальным, хотя в памяти A. Карточка готова к реализации: разделить need-to-build и need-to-reload, проверить A → external B → Play и dependent closure.

**#1814/#1075/#2730 — согласованность asset registry и watcher.** Материалы могут сталкиваться со своим UUID, native handles — переживать Python asset membership, новый GLB — попадать в ошибки canonical registration при status=ok. Это сходный класс рисков, но разные reproductions; объединять в один предполагаемый диагноз преждевременно. #2730 особенно свежая, от 30 сентября. #2313 отдельно требует уточнить обновление prefab instances с сохранением overrides.

**#2675 — удержание старых native mappings.** Пока ниже crash/hang/reload failures: старая mapping наблюдалась, но новые функции уже вызывались из новой копии. GNU_UNIQUE как причина не доказана. Сначала измерить рост памяти/static-state эффекты, затем менять build policy.

### Графика и производительность

| Карточка | Приоритет и следующий результат |
| --- | --- |
| #2527 | Ближайший конкретный фикс: не повторять неудачную dev shader compilation на каждом draw. Нужен failure cache с корректной invalidation после изменения shader/artifacts. Статический путь подтверждён |
| #2683 | Воспроизвести physical attachment ошибки Bloom в ChronoSquad. Inplace alias/clear path — наводка, не доказанный диагноз |
| #2636 | Измерить деградацию Vulkan после заполнения VRAM: в карточке около 60 мс вместо 8 мс. Добавить достаточную диагностику allocations/residency; не объяснять заранее всё вытеснением |
| #2246 | Проверить синхронизацию reusable mapped uniform buffers при нескольких кадрах in flight; прямой memcpy не гарантирует безопасность всех consumers |
| #2212 | Сузить на lifetime ResourceSetHandle и invalidation. Старый фиксированный descriptor capacity cliff уже устранён растущими pool pages |
| #2254 | Определить retirement presentation resources; делать после воспроизводимых рабочих дефектов, без заявления о доказанном текущем crash |

Серию #554–562 выполнять по замерам. #555/#558/#559 уже закрыты. #561 уже получила descriptor/upload reuse: не повторять сделанную оптимизацию. Из оставшегося #554 (повторная компиляция execution descriptor) и #557 (достижимость output roots) выглядят полезными следующими шагами при подтверждённом CPU overhead. #556 backend-frame ownership и #562 dirty-target scheduling крупнее и нужны прежде всего нескольким targets/scenes. #2312 frustum culling явно отложена пользователем до соответствующей большой сцены; этот аудит решения не меняет.

### Доверие к штатным проверкам

**#2540 — первый инфраструктурный приоритет.** Центральный Python runner импортирует termin_modules без учёта Core/Graphics product closure (`scripts/test/python.sh:207`, `python.ps1:241`). Существующие SDK-продукты должны проверяться штатной командой в своём составе.

Далее небольшие конкретные исправления: #2541 Windows MAX_PATH, #2446 сброс cached ccache launcher и оставшаяся часть #1646 про производные cached CMake options. У #1646 пример robotics option остаётся актуальным, а часть старых editor toggles уже изменена.

#2542 shader artifact root уже выставляется обоими C++ runners; требуется контрольный прогон, а не повторная реализация. #2663 уже на On Test и ждёт Windows подтверждения последнего fixture fix. Его заголовок про 19 ошибок не описывает текущий остаток.

## Развитие с наибольшей практической отдачей

**Поставка приложения без исходников.** Если ближайшая цель — отдавать собранные игры/приложения, основной следующий срез: #39 явные dynamic includes и #1745 packaged prefab closure под #32. Важно проверить реальный проект, который динамически создаёт prefab и получает вложенные mesh/material resources после relocation и удаления доступа к source tree. #1230 Python factories и #1313 robotics dependency уже имеют реализацию и тесты; прежде чем переписывать их, выполнить недостающий packaged smoke.

**Завершить native nodegraph migration.** #1507 всё ещё полезна: C++ view/projection готовы, но pipeline editor импортирует Python native_view с собственной большой реализацией отображения и взаимодействий. Это устранение живого дублирования. #1511 переписать аккуратно: часть Python model/controller/io уже служит нормальными фасадами, и удалять их только по старому списку нельзя.

**Завершить chart consumer cutover.** #1352/#1104 должны переводить конкретные старые PlotView3D/WPF controls на уже существующий retained API. #1351 частично выполнена: grid/colorbar/labels открыты; richer annotations/picking ещё не подтверждены. #2537 быстрее довести до Windows приёмки и закрыть.

**Общий native-document host для C#/WPF.** Если C# — используемый потребитель, #1265 и общий host из #1508 дают основу сразу нескольким направлениям. #1103 должна проверять интеграцию charts/widgets поверх того же host. Не разрабатывать два параллельных WPF host для почти одной потребности.

**Текстовый ввод.** #863 IME и grapheme-safe editing важнее дальнейших украшений GUI при расширении пользовательской аудитории. Сейчас движение курсора опирается на UTF-8 codepoints, committed SDL_TEXTINPUT есть, composition/preedit не подтверждена. Комбинированные символы и emoji требуют отдельного контракта редактирования.

## Что продолжать только при конкретном потребителе

| Направление | Условие продолжения |
| --- | --- |
| Полная 2D программа #922 | Реальная игра требует tilemap/physics/authoring. #928 flipbook можно взять отдельным полезным срезом |
| Полный native FEM/sparse/robotics порт #980/#987/#989 | Конкретная задача упирается в текущий dense solver или Python overhead; сначала измерить её |
| Web gameplay #2102 | Есть цель запускать игру в браузере. До неё достаточно поддерживать viewer и исправлять конкретные #1256/#1260 shader gaps |
| Deferred rendering #1012 и его children | Есть визуальная/световая задача и измеримый выигрыш относительно текущего renderer |
| Богатые 3D annotations, streaming и spatial acceleration | Есть пользовательский сценарий и объём данных, на котором текущий retained chart не справляется |
| Общие архитектурные зонты #769/#684/#641/#95 | Выделять конечную subsystem задачу, связанную с подтверждённой проблемой; не запускать сразу четыре широкие миграции |
| Quest #7/#1316/#1317 и связанные regressions | Планируется поставка/демо на устройстве; тогда нужен цельный device acceptance, desktop smoke его не заменяет |
| Windows Python release #2149, NuGet roadmap #2151 | Нужен внешний потребитель этого канала; проверить фактические gates, не путать существующие publisher tools с принятой поставкой |

## Очередь для следующего рабочего цикла

Предлагаемый порядок, а не оценка календарных сроков:

1. Исправить #1869 и #2674; разобраться с файловым round-trip #1871. Результат — безопасность ресурсов, актуальный код после внешней сборки, отсутствие потери animation payload.
2. Отдельным диагностическим проходом локализовать #2608 и #2471, повторить #1931. Получить автоматические сценарии повторного Play/Stop/reload/scene replacement, где это технически возможно.
3. Исправить #2527 и #2540; завершить конкретные Windows проверки #2542/#2663/#2537 на Windows.
4. Выбрать один потребительский срез: standalone prefab/dynamic resources, nodegraph cutover либо общий C#/WPF document host. Завершить его до начала следующей крупной миграции.

Успех такого цикла измеряется рабочими сценариями: длительная сессия без перезапуска, сохранённые данные читаются в новом процессе, внешний rebuild действительно обновляет Play, выбранный SDK проверяется штатно, пакет запускается без исходников. Число закрытых карточек вторично.

## Кандидаты на очистку старого scope

| Карточки | Основание | Следующее действие |
| --- | --- | --- |
| #1407, #1802, #1398 | Закрытые children, исторические acceptance checks, согласующаяся реализация | Финальная сверка и закрытие родителей |
| #1632/#1633/#1634 | Monorepo структура и root profiles уже есть | Закрыть сделанный scope после профильной сверки |
| #1645 | Linux runner уже использует общий aggregate build | Проверить приёмку и закрыть |
| #1865, #2284 | SDK exclusions и conditional Vulkan inventory уже в manifest | Проверить соответствующий inventory gate и закрыть |
| #1230, #1313 | Policy/dependency реализация и tests есть | Relocated packaged smoke; закрыть или выделить конкретный остаток |
| #1629 | Требует прежней split-repository архитектуры | Retire либо переписать под сегодняшнюю потребность monorepo |
| #1639 | Старые split симптомы; все 129 перечисленных suite roots существуют | Переписать вокруг подтверждённых текущих test gaps |
| #1045, #1095, #1102, #1348, #980, #1235 | Значительная часть уже существует | Обновить Current state/Remaining; не расширять остаток автоматически |

#428 «сделать хорошо» — намеренная mission-карточка. Её незакрываемость явно описана; это не дефект дисциплины доски.

## Изменения в ходе аудита

- #1643 закрыта как точный дубль #1646; исправление не объявлено выполненным.
- #2148 закрыта как точный дубль #2150; решение freeze/yank остаётся открытым, внешние публикации не менялись.
- #1869 описание дополнено текущей статической проверкой и уже существовавшим замечанием об animation consumer loops; переведена в Ready.
- #2674 получила комментарий со статическим подтверждением и переведена в Ready.
- Новые bug-карточки не создавались: подтверждённые проблемы уже представлены на доске.

Контрольное чтение доски после изменений: 204 активных, Backlog 170, Ready 20, Blocked 9, In Progress 2, On Test 3. Во время аудита независимо появилась #2741 про передачу sampler state TcTexture в material bindings tgfx2; она не вошла в подробную проверку этого среза. Собственные изменения аудита закрыли две карточки и перевели две в Ready. Массовое закрытие предполагаемо выполненных реализаций не проводилось.

## Основные исходники для перепроверки

- Ресурсы: [tc_resource.h](https://github.com/mirmik/termin/blob/master/core/termin-base/include/tcbase/tc_resource.h), [tc_pool.c](https://github.com/mirmik/termin/blob/master/core/termin-base/src/tc_pool.c), [tc_mesh_registry.c](https://github.com/mirmik/termin/blob/master/graphics/termin-mesh/src/resources/tc_mesh_registry.c).
- Анимации: [clip_io.py](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/python/termin/animation/clip_io.py), [animation_module.cpp](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/cpp/bindings/animation_module.cpp).
- Модули: [module_types.hpp](https://github.com/mirmik/termin/blob/master/engine/termin-modules/include/termin_modules/module_types.hpp), [module_cpp_backend.cpp](https://github.com/mirmik/termin/blob/master/engine/termin-modules/src/module_cpp_backend.cpp), [project runtime.py](https://github.com/mirmik/termin/blob/master/editor/termin-project-modules/python/termin/project_modules/runtime.py).
- Проверки: [test manifest](https://github.com/mirmik/termin/blob/master/build-system/test-suites.json), [Python runner](https://github.com/mirmik/termin/blob/master/scripts/test/python.sh), [C++ runner](https://github.com/mirmik/termin/blob/master/scripts/test/cpp.sh).
- Scene navigation: [acceptance project](https://github.com/mirmik/termin/blob/master/test-projects/world-controller-scene-cycle/README.md).
- Nodegraph: [README](https://github.com/mirmik/termin/blob/master/graphics/termin-nodegraph/README.md), [Python native_view](https://github.com/mirmik/termin/blob/master/graphics/termin-nodegraph/python/termin/nodegraph/native_view.py), [pipeline editor](https://github.com/mirmik/termin/blob/master/editor/termin-app/termin/editor_native/pipeline_editor.py).
- Charts: [retained_chart3d.h](https://github.com/mirmik/termin/blob/master/graphics/tcplot/include/tcplot/retained_chart3d.h), [MultiChart2D.cs](https://github.com/mirmik/termin/blob/master/termin-csharp/Termin.Native/MultiChart2D.cs).
- Web: [browser gate](../web-runtime-browser-gate.md).
- QOpt: [README](https://github.com/mirmik/termin/blob/master/physics/termin-qopt/README.md), [HQP status](https://github.com/mirmik/termin/blob/master/physics/termin-qopt/HQP_STATUS.md).
