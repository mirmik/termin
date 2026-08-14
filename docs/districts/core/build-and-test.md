# Сборка и проверка

Core владеет пакетами, но не собственной строительной компанией. Сборка,
tests, CI, toolchains, third-party и документационный портал принадлежат корню
репозитория. `core/CMakeLists.txt` только компонует нижний слой в общий граф.

## Публичные команды

| Команда | Результат |
|---|---|
| `task build:core` | Core profile в `sdk-core/` |
| `task build:graphics` | Кумулятивный Core + Graphics в `sdk-graphics/` |
| `task build` | Полный editor product в `sdk/` |
| `task test` | Центральный native, Python и process-smoke прогон |
| `task docs:build` | Все public docs sites в `_site/` |

Полная форма Core profile тоже допустима:

```console
task build -- --profile core
```

Для обычной работы предпочтительнее `task build:core`: имя задачи явно
показывает намерение, а `Taskfile.yml` остаётся единственной публичной
командной поверхностью. Пути в `scripts/` — детали реализации.

## Что строится

Профиль использует общий build frontend и тот же exact runtime lock, что
остальные продукты. Он:

1. готовит канонический CPython 3.14t toolchain;
2. конфигурирует Core closure в корневом CMake graph;
3. устанавливает native libraries, headers и CMake configs;
4. собирает и устанавливает Core Python distributions;
5. публикует wheelhouse и manifests;
6. проверяет профиль, ABI и import boundary.

Build directory получает профильный suffix, а установленный prefix по
умолчанию равен `sdk-core/`. Полный `sdk/` при этом не перезаписывается.

## Что тестируется

`task test` — репозиторный, а не Core-only entry point. Он нужен перед
интеграцией изменений в нижнем слое: поломка Core часто обнаруживает себя
выше, где договорённостью уже пользуются Graphics, Engine и Editor.

Отдельные Core suites и installed-consumer fixtures существуют внутри
центрального test plan, но прямой запуск их scripts не является публичным
workflow. Это намеренное ограничение: одна команда должна оставаться правдой
на Linux, Windows и CI.

## Desktop и platform builds

Standalone profile `core` — host desktop product. Android, Web и OpenXR
строятся корневыми platform tasks и выбирают нужную closure нескольких
районов. Они не являются «Core SDK для другой платформы» и не должны
документироваться как независимая сборка каталога `core/`.

Полное устройство оркестратора описано в общей
[системе сборки](../../build-system.md).
