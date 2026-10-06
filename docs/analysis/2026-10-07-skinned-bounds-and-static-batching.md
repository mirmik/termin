# Skinned bounds и стоимость static batching — #2898, #2899

## Реализация

Штатный SkinnedMeshRenderer использует исходный AABB выбранного submesh и
текущую model matrix для CPU culling. Bone matrices остаются в draw payload;
анимация не меняется. Отдельный flag обозначает именно это приближение.
Без skeleton payload геометрия действительно неподвижна и использует обычный
conservative flag. Custom skinned producers должны явно выбрать новую политику.
Bounds используют существующий version cache и вычисляются при публикации
snapshot; камеры и shadow cascades затем проверяют свои frusta.

Консервативный контракт для текущей анимированной позы **отложен решением
пользователя от 2026-10-07 до появления проблем от наивной политики**. Исчезновение
геометрии или теней из-за исходного AABB потребует воспроизведения и пересмотра
этого решения. Проверка ниже не гарантирует containment произвольных поз.

Static batching индексирует semantic keys с проверкой полного равенства при
совпадении хеша. Порядок групп остаётся порядком первого появления. Scratch
storage сохраняется между apply, signatures вычисляются заново, неизменённые
cached groups переносятся без глубокого копирования signatures. Перенос
выполняется после успешной подготовки всех meshes, сохраняя cache при ошибке
поздней пересборки. Scene/layer/category/filter variants остаются независимыми;
старые snapshots сохраняют владение своими merged meshes.

## Метод проверки

База — `8717ed149`. CargoTerminal запущен в отдельном агентском редакторе,
Vulkan offscreen, окно 1600×1000, игровой viewport 1052×614. В одном процессе
переключались сохранённая реализация прежнего batching и прежнее исключение
skinned bounds через временный LD_PRELOAD probe. Прежний batching имеет
собственный cache/Impl. Probe и копии старого кода находятся только в `/tmp`.

Три состояния измерены с одинаковым detailed profiler, по 120 прогретых кадров:
step/time=0, выбран Arthur, 39 animation players остановлены на clip time 0,
projections скрыты, editor display выключен. Камера `[-16, -53, 35]`, near/far
0.1/350. JSON capture и screenshots выполнялись отдельно от измерений; при
профилировании probe не сериализовал snapshot и не копировал диагностические
items. Снимались уже опубликованные snapshots, без повторного сбора producers.
Сцена и проект не сохранялись.

При загрузке повторились известные ошибки legacy TransparentShader/TimeSpirit
assets (#2232); проекции исключены из smoke. До измерений наблюдался также
RingUBO transient fallback (#2300). Эти существующие проблемы не исправлялись
данными изменениями и не считаются успешной проверкой соответствующих систем.

Это один фиксированный smoke текущего проекта. CPU timings подвержены шуму;
они не измеряют GPU speedup. Исторические 1999 draws в исходных карточках сняты
в другом live состоянии и не являются baseline этой пары.

## Результат

| Показатель на кадр | Старые batching/bounds | Новый batching, старые bounds | Оба изменения |
| --- | ---: | ---: | ---: |
| Static batching, мс (3 apply) | 1.284 | 0.610 | 0.584 |
| Grouping, мс | 0.810 | 0.437 | 0.426 |
| Cache/output, мс | 0.339 | 0.166 | 0.153 |
| Bounds + phase index, мс | 0.067 | 0.044 | 0.049 |
| CPU Render, мс | 12.143 | 11.895 | 9.082 |
| Active frame, мс | 13.614 | 13.445 | 10.574 |
| Encode mesh draw calls | 2120 | 2120 | 1535 |

В трёх apply суммарно 1910 input geometry, 1680 eligible geometry, 636 work
groups и 460 output batches. На прогретом cache rebuilds=0, reused=460 во всех
случаях. Work key comparisons уменьшились с 268699 до 1044, cache key comparisons
с 52901 до 460. Member signatures по-прежнему сравниваются 1504 раза; глубокие
копирования signatures уменьшились с 1504 до 0. Состав и порядок всех трёх
target snapshots, bytes vertices/indices всех merged meshes совпали.

Источник прежних `168 without_bounds` подтверждён: SkinnedMeshRenderer,
168 разных object/geometry pairs, по одному item для phase 1 и 32 (336 rows).
Например, `Yard patrol/Model/corpguardMesh` с 66 bone matrices. В главном
snapshot 1015 items: valid bounds выросли с 660 до 996; unsupported осталось
19 (15 WorldTextComponent и 4 NavMeshKeeper). Все identities находятся в JSON.

| Проход chronosquad | Draws до skinned bounds | После | without_bounds до → после |
| --- | ---: | ---: | ---: |
| Shadow cascade 0 | 190 | 43 | 168 → 0 |
| Shadow cascade 1 | 272 | 174 | 168 → 0 |
| Shadow cascade 2 | 498 | 498 | 168 → 0 |
| ActorAttributePass | 170 | 82 | 168 → 0 |
| Depth | 278 | 190 | 168 → 0 |
| Normal | 278 | 190 | 168 → 0 |

Shadow CPU section: 2.767 → 2.195 мс; ActorAttributePass: 0.651 → 0.430 мс;
Normal: 1.051 → 0.653 мс. Общая Depth section для трёх targets: 1.462 →
1.144 мс. Bounds + phase index: 0.044 → 0.049 мс при включении skinned bounds.
Эти секции не дают оснований обещать весь прежний Shadow cost как выигрыш.

RGB viewport совпал **пиксель в пиксель во всех трёх состояниях** (645928 pixels).
В этом кадре потери геометрии и теней не обнаружено. Сравнение включает игровую
картинку и UI, исключает остальную оболочку редактора.

## Проверки

- Штатный offline `task build` прошёл, SDK и Python launcher/import graph готовы.
- Native regression suite проверяет submesh/model/pose/version/missing bounds,
  отдельные camera/cascade frusta, сохранность skinning payload, forced hash
  collisions, порядок 96 batches, revisions, membership и cache variants,
  позднюю ошибку rebuild и lifetime прежнего snapshot. Дополнительная
  интеграционная регрессия проходит через TcSceneRenderItemSource.publish:
  visible/entity enabled/component enabled, добавление/удаление/replacement
  entities и components, layer/category masks и владение предыдущих snapshots
  после cache clear и scene free.
- `task test`: native 268/268 passed, Python 3687 passed и один известный
  failure #2885 (`test_native_textured_pixal3d_geometry_reference`, generated
  TANGENT degenerate/non-finite at vertex0). GLB код не менялся; повторное
  свидетельство добавлено в существующую карточку.
- После последней правки integration test: `task test -- --no-python` —
  266/266 passed (Python-dependent native targets в этом режиме отключены).
- `git diff --check` прошёл. Логи: `/tmp/termin-2898-2899/build.log`,
  `test-final.log`, `test-native-verified.log`.

Полные числовые данные, identities, fingerprints и culling counters:
[JSON](2026-10-07-skinned-bounds-and-static-batching.json).
Снимки viewport:
[до](skinned-bounds-and-static-batching-2026-10-07/old_batch_old_bounds.png),
[после batching](skinned-bounds-and-static-batching-2026-10-07/new_batch_old_bounds.png),
[после обоих изменений](skinned-bounds-and-static-batching-2026-10-07/new_batch_new_bounds.png).
