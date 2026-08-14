# Первый кадр

Лучший вход в Graphics — не пустое окно цвета «вроде бы очистилось». Профильный
showcase собирает native UI, линии, retained 2D/3D scenes, nodegraph, GLB,
animation и plots в один проверяемый продукт, а затем оставляет после себя PNG
и отчёт. Улики весят больше бодрого сообщения в stdout.

## Собрать headless профиль

Из корня репозитория:

```console
task build:graphics -- --no-sdl
```

Результат находится в `sdk-graphics/`. Запустите showcase через bundled
Python, не добавляя checkout в `PYTHONPATH`:

```console
./sdk-graphics/bin/termin_python -I examples/graphics-showcase/main.py \
  --headless \
  --output /tmp/termin-graphics-showcase.png \
  --report /tmp/termin-graphics-showcase.json
```

Headless path — обязательный baseline. Ему не нужны `termin-window`, SDL,
Engine, Editor или PySDL2; кадр собирает
`termin.gui_native.OffscreenGuiComposition`. Ошибка любого раздела логируется
с его именем и завершает процесс ненулевым кодом.

## Что находится на плёнке

| Раздел | Что он доказывает |
|---|---|
| Native UI | Retained controls, text, models и layout |
| Graphics lines | Caps, joins, widths и 3D polylines |
| Plot gallery | Lines, scatter, markers, 3D surface и colormap |
| Visual Scene | Иерархия, transforms, opacity, hit regions и 3D items |
| Animated GLB | Mesh, skeleton и sampled animation pose |
| Nodegraph composition | Graph model, projection и plot widgets внутри nodes |

JSON report фиксирует exact imports, статус всех секций, framebuffer metrics и
путь к артефакту. PNG рисуется самой композицией, а не достаётся заранее из
кармана фокусника.

## Добавить окно

Окно — необязательный host поверх той же графической closure:

```console
task build:graphics -- --sdl
./sdk-graphics/bin/termin_python -I \
  examples/graphics-showcase/main.py --windowed
```

`--frames N` и `--seconds N` ограничивают жизнь окна для автоматизированных
проверок. `termin-window` обслуживает platform events и presentation;
engine-owned `termin-display` в Graphics profile не входит.

## Windows и D3D11

Для D3D11-only продукта отключите SDL, Vulkan и OpenGL:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
.\sdk-graphics\bin\termin_python.exe -I `
  .\examples\graphics-showcase\main.py `
  --headless `
  --output "$env:TEMP\termin-graphics-showcase.png" `
  --report "$env:TEMP\termin-graphics-showcase.json"
```

На Windows профиль автоматически выбирает C# composition `plot-d3d11`, если
собираются C# bindings. Это не превращает весь Graphics в WPF: managed bridge
остаётся отдельным consumer surface.

## Проверить изменения

Центральный test entry point остаётся общим:

```console
task test
```

Отдельной публичной команды `smoke:graphics` сейчас нет. Не закрепляйте в
своей автоматизации paths из `scripts/`: корневой `Taskfile.yml` — единственная
поддерживаемая command surface.

!!! note "Границы профиля"

    Standalone `graphics` profile — desktop host product. Android и Web
    выбирают Graphics subsets через свои корневые platform builds; каталог
    `graphics/` не собирает себя для этих targets независимо.
