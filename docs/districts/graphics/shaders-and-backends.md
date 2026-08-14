# Шейдеры и backend-ы

Backend — это способ исполнить контракт, а не религия, не identity продукта и
не повод размножить рендерер на три почти одинаковых вида. Graphics profile
выбирает возможности флагами сборки, а runtime-код принимает решения по typed
capabilities.

## Сборочные режимы

Обычный headless desktop профиль:

```console
task build:graphics -- --no-sdl
```

SDL-enabled window host:

```console
task build:graphics -- --sdl
```

D3D11-only Windows profile:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
```

Backend flags ортогональны профилю: `graphics` отвечает за package closure,
а Vulkan/OpenGL/D3D11/SDL — за capabilities конкретной сборки. Не выводите
одно из другого по имени каталога.

## От source к artifact

`termin-materials` описывает shader programs, phases, material properties и
surface contracts. `termin_shaderc`, устанавливаемый Graphics SDK, компилирует
исходники в target artifacts и layout metadata. `termin-shader-runtime`
разрешает инструменты и source-project configuration на Python-стороне.

Runtime потребляет явный artifact contract. Он не должен на ходу угадывать
bindings из имён, подменять отсутствующую stage другим файлом или незаметно
возвращаться к старому GLSL preprocessing path. Ошибка shader ABI обязана
появиться в логе и остановить невалидную операцию.

## Capabilities вместо строк

Плохой branching:

```cpp
if (context.backend() == "opengl") {
    // Надежда, эвристика и старый баг живут здесь.
}
```

Рабочий branching спрашивает устройство о конкретной возможности:

```cpp
const auto& caps = device.capabilities();
// Решение принимается по нужному feature contract.
```

Строка `backend` остаётся полезной диагностикой. Но имя API не сообщает
texture origin, MRT limits, sampler budget или readback support с достаточной
точностью.

## Headless не значит «без графики»

Headless profile создаёт offscreen graphics composition без native window.
Он по-прежнему исполняет GPU/render contracts, создаёт framebuffer output и
проверяет результат по пикселям. `--no-sdl` удаляет window dependency, а не
превращает showcase в набор mock-объектов.

## Platform builds

Standalone Graphics SDK ориентирован на desktop host. Web, Android и OpenXR
используют свои корневые build tasks и выбирают поддерживаемую Graphics
closure вместе с platform code. Это позволяет, например, отключить desktop
OpenGL и window tests для Web или включить Vulkan для Android, не заводя
`graphics/CMakeLists.txt` как второй проект.

## Статус API

Graphics активно развивается. Installed package names, профильная closure и
основные ownership/lifetime contracts уже пригодны для документации. Полный
сырой inventory tgfx/material bindings пока не является обещанием
стабильного ABI: coexistence legacy и tgfx2 поверхностей ещё мигрирует.

Пишите guide вокруг устойчивых контрактов — host ownership, targets,
capabilities, artifacts и failure modes — а не вокруг каждого экспортированного
имени, которое случайно пережило вчерашний refactor.
