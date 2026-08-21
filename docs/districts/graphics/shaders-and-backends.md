# Шейдеры и backend-ы

Backend — это способ исполнить контракт, а не религия, не identity продукта и
не повод размножить рендерер на три почти одинаковых вида. Graphics profile
выбирает возможности флагами сборки, а runtime-код принимает решения по typed
capabilities.

## Сборочные режимы

Полный desktop Graphics product:

```console
task build:graphics -- --sdl
```

Урезанная headless SDK-конфигурация для внутренних проверок:

```console
task build:graphics -- --no-sdl
```

D3D11-only Windows profile:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
```

Backend flags остаются ортогональны SDK-профилю. Публичный Python product при
этом фиксирует SDL/window capability как часть своей closure; `--no-sdl`
допустим только для внутренних SDK/platform recipes.

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

Headless execution создаёт offscreen graphics composition без native window,
даже когда window stack установлен. Он по-прежнему исполняет GPU/render
contracts, создаёт framebuffer output и проверяет результат по пикселям.
Внутренний `--no-sdl` build удаляет window capability целиком, но для этого не
нужен отдельный публичный Python product.

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
