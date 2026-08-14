# Первый спуск

Никакого священного ритуала нет. Нужны Git, CMake, C/C++ toolchain, системный
Python для запуска сборщика и [Task](https://taskfile.dev/). Целевой Python
система не выбирает по погоде: SDK сам готовит закреплённый free-threaded
CPython 3.14t.

## Собрать Core SDK

Команды выполняются из корня общего репозитория:

```console
git clone https://github.com/mirmik/termin.git
cd termin
task build:core
```

На Windows команда та же: Task выберет PowerShell launcher. Результат не
смешивается с полным editor SDK и появляется в `sdk-core/`:

```text
sdk-core/
├── bin/termin_python        # termin_python.exe на Windows
├── include/                 # C, C++, Python и nanobind headers
├── lib/                     # библиотеки, runtime и CMake packages
├── wheels/                  # проверенный набор Python wheels
└── sdk-product.json         # идентичность профиля core
```

Первый проход может занять время и потребовать сеть: точный Python toolchain и
runtime inputs материализуются один раз, затем переиспользуются.

## Открыть люк в Python

Используйте Python из SDK. Это не декоративная рекомендация: native-модули
собраны для конкретного free-threaded ABI.

```console
./sdk-core/bin/termin_python -I -c \
  "import tcbase, termin.dispatch, termin.inspect, termin.mcp; print('Core жив')"
```

На Windows:

```powershell
.\sdk-core\bin\termin_python.exe -I -c `
  "import tcbase, termin.dispatch, termin.inspect, termin.mcp; print('Core жив')"
```

Небольшой пример с dispatcher:

```python
from termin.dispatch import Dispatcher

dispatcher = Dispatcher()
dispatcher.defer(lambda: print("вызвано не сейчас, а когда мы решим"))

# Никакого скрытого потока: работу выполняет вызвавший run_pending().
stats = dispatcher.run_pending()
print(stats.executed)
```

Запускайте файл через `sdk-core/bin/termin_python`. Системный Python может
иметь другую версию, другой SOABI и совершенно иные планы на этот процесс.

## Подключить C++

Core публикует обычные CMake config packages:

```cmake
cmake_minimum_required(VERSION 3.20)
project(core_trip LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)

find_package(termin_base CONFIG REQUIRED)
find_package(termin_dispatch CONFIG REQUIRED)

add_executable(core_trip main.cpp)
target_link_libraries(core_trip PRIVATE
    tcbase::termin_base
    termin_dispatch::termin_dispatch
)
```

```cpp
#include <tcbase/tc_version.h>
#include <termin/dispatch/dispatcher.hpp>

#include <iostream>

int main() {
    termin::Dispatcher dispatcher;
    dispatcher.defer([] { std::cout << "работа выполнена\n"; });
    dispatcher.drain();
    std::cout << "Core " << tc_version() << '\n';
}
```

Сборка consumer-а:

```console
cmake -S . -B build \
  -DCMAKE_PREFIX_PATH=/absolute/path/to/termin/sdk-core
cmake --build build
```

Не добавляйте соседний checkout через `add_subdirectory()` и не ищите headers
в исходниках. Если установленный package не найден, это ошибка поставки SDK,
а не приглашение открыть потайную дверь.

## Проверить контракт

`task build:core` завершает профильную сборку проверкой SDK manifests и import
boundary. Полный репозиторный прогон запускается общей командой:

```console
task test
```

CI дополнительно копирует Core SDK во временный каталог, отравляет ambient
Python paths, собирает внешние C/C++ consumers и проверяет отрицательный
сценарий с намеренно спрятанным CMake package. Подробности этого допроса — в
[контракте SDK](sdk.md).

!!! warning "Не перепутайте профили"

    `task smoke` относится к полному `sdk/`, а не к `sdk-core/`. Отдельной
    публичной команды `smoke:core` сейчас нет; не подменяйте её вызовом
    внутренних scripts.
