# Контракт Core SDK

Главный внешний продукт Core — не build directory и не набор `.so` рядом с
исходниками. Это установленный `sdk-core/`, который знает собственную
идентичность и не знает, где его собрали.

Внутри монорепозитория районы соединяет единый root CMake graph. За его
пределами действует только установленная граница: CMake packages, headers,
libraries, bundled Python и manifests. Два режима не надо смешивать в третий
режим «давайте на всякий случай посмотрим в соседнюю папку».

## CMake contract

Передайте корень SDK через `CMAKE_PREFIX_PATH` и находите установленные
packages:

```cmake
find_package(termin_base CONFIG REQUIRED)
find_package(termin_dispatch CONFIG REQUIRED)
find_package(termin_inspect CONFIG REQUIRED)
find_package(termin_python_host CONFIG REQUIRED)
```

Основные targets:

| Package | Target |
|---|---|
| `termin_base` | `tcbase::termin_base` |
| `termin_dispatch` | `termin_dispatch::termin_dispatch` |
| `termin_inspect` | `termin_inspect::termin_inspect` |
| `termin_python_host` | `termin_python_host::termin_python_host` |

Конкретные packages лучше aggregate target: dependency graph должен говорить,
чем программа действительно пользуется, а не сообщать следствию «каким-то
Core».

## Python contract

Код запускается через `sdk-core/bin/termin_python`. Launcher знает layout SDK
и изолирует процесс от случайного `PYTHONPATH`, user site и системных packages.

```console
/opt/termin/sdk-core/bin/termin_python -I tool.py
```

Профиль содержит, среди прочего, следующие публичные imports:

- `tcbase`;
- `termin.dispatch`;
- `termin.inspect`;
- `termin.mcp`.

Нельзя взять native extension из одного SDK, интерпретатор из второго и
`libnanobind-ft` из третьего. Такая конструкция способна прожить достаточно
долго, чтобы испортить вечер, поэтому manifests и import gates не дают ей
сойти за продукт.

## Identity вместо надежды

Установленный SDK записывает:

- выбранный профиль и Python ABI;
- content-derived `native_build_id`;
- перечень и hashes native artifacts;
- runtime и wheel provenance;
- связь Python runtime с `sdk-product.json`.

Это не рекламная листовка. Consumer может проверить, что libraries, Python и
wheels принадлежат одной сборке, прежде чем несовпадение выразит мнение через
segmentation fault.

## Relocation как исполняемое доказательство

CI-проверка Core делает больше, чем `import tcbase` в родном checkout:

1. копирует SDK во временное место;
2. очищает пути, через которые могли просочиться исходники;
3. намеренно прячет `termin_dispatch` CMake package и требует, чтобы
   конфигурация упала;
4. возвращает package и собирает C++ executable, embedded-Python host и
   nanobind extension;
5. запускает их против перемещённого SDK;
6. проверяет изолированные Python imports.

Отрицательная стадия здесь важнее торжественного `OK`: если consumer способен
найти удалённый package где-то в системе или checkout, переносимость уже
сфальсифицирована.

Исполняемый fixture находится в
[`tests/installed-core-consumers`](https://github.com/mirmik/termin/tree/master/tests/installed-core-consumers).
Это repository gate, а не второй публичный build interface.

## Что должен делать внешний consumer

- принимать явный путь к установленному SDK;
- использовать CMake packages и публичные headers;
- запускать bundled Python для native distributions;
- не добавлять sibling-checkout fallback;
- не копировать исходники Core в своё дерево;
- проверять хотя бы один installed consumer в CI.

Строгость окупается быстро: граф зависимостей остаётся правдой на другой
машине, в другой ветке и после того, как исходный checkout исчез из поля
зрения.
