# Аудит управляющего контура монорепозитория Termin

Дата: 2026-07-09.

## Резюме

Основной найденный риск находится не в архитектуре ядра движка, а в
инфраструктуре, которая должна доказывать целостность быстро растущего
монорепозитория.

Кодовая база уже использует достаточно зрелые механизмы декомпозиции:

- отдельные domain-пакеты и native-библиотеки;
- явную карту ownership и допустимых зависимостей;
- единый manifest Python-пакетов;
- центральные build/test entry points;
- модульную документацию рядом с владельцами кода.

Однако test discovery, часть CI и публикация документации всё ещё опираются
на вручную поддерживаемые списки. Проект декомпозируется быстрее, чем
обновляется его управляющий контур. Из-за этого наличие теста или документа
в репозитории ещё не означает, что он участвует в центральной проверке или
публикации.

Главный практический результат аудита: `./run-tests.sh --full` не является
полным repo-wide прогоном Python-тестов, несмотря на естественное ожидание от
названия и справки скрипта.

## Область и методика

Проверены:

- корневая CMake-конфигурация и штатные build/test scripts;
- `build-system/packages.json` и Python package tooling;
- расположение repository-owned Python-тестов;
- GitHub Actions workflows;
- структура `docs/`, module-local `docs/` и MkDocs workflow;
- активная Kanboard-доска, чтобы не дублировать известные задачи.

Из подсчётов исключались `.git`, `build`, `sdk`, `.venv` и
`termin-thirdparty`. Число test-функций получено статическим разбором AST и
поэтому не равно числу pytest cases: параметризация может увеличить реальное
число запусков. Подсчёт нужен для оценки масштаба слепой зоны, а не как
замена `pytest --collect-only`.

Аудит выполнялся по `HEAD` (`9718df5f`) и неизменённым файлам. Параллельно в
рабочем дереве шла сторонняя работа над `termin-gui-native`; её изменения не
использовались как основание для выводов.

## 1. Центральный Python test runner пропускает целые подсистемы

### Наблюдение

`run-tests.sh` последовательно вызывает `run-tests-cpp.sh` и
`run-tests-python.sh`. В отсутствие явно переданных pytest targets
`run-tests-python.sh` запускает вручную перечисленный набор каталогов.

Флаг `--full` не расширяет список каталогов. Он только снимает фильтр
`-m "not full"` и включает editor-process smoke tests на верхнем уровне.

На момент аудита:

- package manifest содержит 53 Python-пакета;
- default Python runner перечисляет около 20 test roots;
- вне перечисленных roots находятся 57 файлов `test_*.py`;
- в этих файлах статически найдено не менее 316 test-функций.

Крупнейшие выпавшие наборы:

| Test root | Файлов | Test-функций |
| --- | ---: | ---: |
| `termin-project-build/tests` | 11 | 118 |
| `termin-navmesh/tests` | 8 | 48 |
| `termin-components/termin-components-render/tests` | 3 | 33 |
| `termin-components/termin-components-kinematic/tests` | 1 | 28 |
| `termin-render/tests` | 5 | 15 |
| `termin-animation/tests` | 4 | 11 |
| `termin-physics/tests` | 3 | 9 |
| `termin-project-modules/tests` | 1 | 7 |
| `termin-project/tests` | 2 | 7 |
| `termin-render-passes/tests` | 3 | 7 |

Кроме них центральный runner не включает Python-тесты ряда component
packages, `termin-engine`, `termin-gui-native`, `termin-skeleton`,
`termin-stdlib`, `termin-tween`, `tcplot`, `termin-collision`,
`termin-physics-fem` и `termin-shader-runtime`.

### Почему это системная проблема

Ручной список создаёт fail-open поведение: новый пакет или новый test root
молча остаётся за пределами центрального прогона. Добавление тестов выглядит
успешным локально при focused run, но не усиливает repo-wide gate.

Особенно опасно, что в слепой зоне находятся активно меняющиеся части:
runtime package exporter, navmesh, render contracts и native UI. Зелёный
`./run-tests.sh` не доказывает отсутствие регрессий в этих подсистемах.

### CI не закрывает разрыв

GitHub Actions использует другие ручные списки:

- `test-pip-packages` запускает только tests для `termin-base`,
  `termin-graphics`, `termin-gui` и `termin-nodegraph`;
- `test-termin` запускает только `termin-app/tests`;
- C/C++ job конфигурирует CMake с `TERMIN_BUILD_PYTHON=OFF`, поэтому не может
  случайно подобрать пропущенные pytest suites через CTest.

Таким образом локальный runner и CI не являются двумя независимыми полными
воротами: у них разные, частично пересекающиеся неполные inventories.

### Целевая архитектура

Test inventory должен быть декларативным и общим для локальных scripts и CI.
Подходящие варианты:

1. Расширить `build-system/packages.json` test metadata для каждого пакета.
2. Ввести отдельный test manifest, ссылающийся на package manifest.

Для каждого test root нужны как минимум:

- путь;
- режим `working` / `full`;
- необходимые features и native extensions;
- platform/backend ограничения;
- признак manual/device/window gate;
- явная причина исключения из автоматического прогона.

Отдельная inventory-проверка должна падать, если repository-owned
`test_*.py` не принадлежит ни одному объявленному набору. Это меняет модель с
fail-open на fail-closed: новый тест нельзя случайно оставить за воротами.

Локальный runner может по-прежнему запускать suites раздельно для хорошей
диагностики и продолжения после ошибки, но список должен генерироваться из
manifest, а не дублироваться в shell и YAML.

### Трекинг

Создана Kanboard-карточка **#262**:
`[qa/ci] Make Python test discovery manifest-driven`.

## 2. Source-size CI gate не проходит на текущем HEAD

Workflow `lint-source-size` выполняет:

```bash
python3 scripts/find-long-files.py --threshold 2000 --fail .
```

Та же команда на проверенном `HEAD` возвращает код 1 и находит четыре
repository-owned файла:

| Файл | Строк |
| --- | ---: |
| `termin-project-build/tests/test_runtime_package_exporter.py` | 2196 |
| `termin-gui-native/src/widgets.cpp` | 2180 |
| `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp` | 2162 |
| `termin-graphics/tools/termin_shaderc.cpp` | 2013 |

Это означает расхождение между объявленной политикой CI и состоянием
master: gate либо уже красный, либо не является обязательным сигналом для
интеграции изменений.

Само превышение порога не обязательно доказывает плохую архитектуру каждого
файла. Например, большой test module может оставаться связным набором
контрактов. Но gate с `--fail` должен быть честным: либо файлы делятся, либо
исключения задаются явно с обоснованием и сроком пересмотра. Постоянно красный
необязательный gate быстро превращается в информационный шум.

## 3. Опубликованная документация не является полной проекцией репозитория

В репозитории найдено около 195 Markdown-файлов в module-local `docs/` и
десятки документированных модулей. При этом Pages workflow:

- собирает корневой MkDocs site из `docs/`;
- отдельно собирает только `termin-app`, `termin-collision`, `termin-gui`,
  `termin-inspect`, `termin-scene` и `termin-modules`;
- реагирует изменениями paths только на эти же module-local docs;
- не публикует остальные module-local docs как самостоятельные sites.

Корневой `mkdocs.yml` содержит в `nav` только `docs/index.md`. Сам hub
ссылается на документы вида `../termin-base/docs/index.md`, то есть за
пределами корневого `docs_dir`. Такие source-tree ссылки полезны в GitHub и
Obsidian, но сами по себе не превращают внешние Markdown-файлы в страницы
собранного корневого MkDocs site.

Итог: source documentation заметно полнее опубликованного портала. Пользователь
может увидеть хороший module map в checkout, но не получить тот же граф
навигации на Pages.

Целевое решение похоже на test inventory:

- объявить публикуемые docs roots в едином module/package manifest;
- генерировать MkDocs navigation или multi-project build из manifest;
- проверять внутренние ссылки после сборки;
- падать, если документированный модуль не опубликован и не помечен как
  intentionally internal;
- использовать один URL contract для source-tree и published navigation.

## 4. Общий паттерн

Все три наблюдения имеют одну причину: архитектурное знание уже существует,
но не всегда исполняется машиной.

| Область | Source of truth уже есть | Разрыв |
| --- | --- | --- |
| Python packages | `build-system/packages.json` | tests перечислены отдельно в shell/YAML |
| Test policy | `run-tests.sh`, pytest markers | отсутствует полный inventory и ownership gate |
| Source policy | `find-long-files.py`, CI job | текущий HEAD нарушает объявленный gate |
| Documentation | module map и module-local docs | Pages собирает ручное подмножество |

Это не аргумент за новый универсальный мегаманифест со всеми деталями
проекта. Но package/module identity должна иметь один машиночитаемый корень,
от которого производятся inventories для сборки, тестов, CI и документации.
Особые случаи допустимы как явные feature/platform policies, а не как
отсутствие записи.

## Рекомендуемый порядок действий

1. Исправить test discovery и добавить orphan-test gate — это риск ложного
   зелёного результата и потому самый высокий приоритет.
2. Включить новый inventory в CI, не копируя список suites в workflow YAML.
3. Привести source-size job в честное состояние: разделить четыре файла или
   оформить ограниченные явные исключения.
4. После стабилизации test manifest применить тот же принцип к docs roots и
   публикации Pages.
5. Добавить небольшую repo-doctor проверку согласованности package, test и
   docs inventories.

## Команды для воспроизведения

Проверка package manifest:

```bash
PYTHONPATH=termin-build-tools \
python3 -m termin_build.package_manifest --repo-root . --check
```

Текущий source-size gate:

```bash
python3 scripts/find-long-files.py --threshold 2000 --fail .
```

Ручная проверка центрального Python runner:

```bash
sed -n '84,200p' run-tests-python.sh
```

Проверка CI test roots и docs build roots:

```bash
rg -n 'pytest|run-tests|for project in' .github/workflows
```

Для постоянной автоматизации подсчёт orphan tests следует реализовать
репозиторным инструментом поверх декларативного inventory, а не сохранять
одноразовую audit-команду как ещё один независимый список путей.
