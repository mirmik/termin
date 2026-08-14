# Машинное отделение

<div class="termin-kicker">District guide / Graphics</div>

<div class="termin-lead" markdown>
Graphics — район, где безобидное число становится пикселем, пиксель получает
шейдер, шейдер получает backend, а затем вся процессия идёт к GPU и надеется,
что ни один контракт не был написан карандашом на мокрой салфетке.
</div>

Это не один renderer. Graphics владеет переносимыми изображениями и мешами,
GPU substrate, материалами, scene-neutral render orchestration, окнами,
retained visual scenes, native UI, nodegraph, plotting, skeleton, animation и
portable GLB. Восемнадцать пакетов образуют один район, потому что вместе они
способны выдать законченную графическую систему без Engine и Editor.

```console
task build:graphics
```

Команда строит кумулятивный Core + Graphics SDK в `sdk-graphics/`. Сам каталог
`graphics/` не является отдельным проектом: профиль выбирает корневой
оркестратор, third-party и CI остаются общими для всего Termin.

<div class="termin-contract" markdown>
**Короткий контракт:** Graphics знает, как хранить визуальные данные,
подготовить GPU domain и исполнить scene-neutral render work. Он не знает, что
такое engine Entity, active scene, AssetManager, editor project или
application bootstrap.
</div>

## Не перепутать вывески

| Имя | Что это |
|---|---|
| Graphics district | Весь район и его 18 пакетов |
| `graphics/` | Namespace владения в checkout |
| `graphics` profile | Core + Graphics SDK product |
| `graphics/termin-graphics` | Низкоуровневый GPU package с tgfx/tgfx2 |
| `graphics/termin-render-core` | Scene-neutral framegraph и render execution |
| `engine/termin-render` | Верхний adapter для сцен и компонентов |

Слово «graphics» встречается часто, но это не повод употреблять его как
универсальный гаечный ключ.

## Маршрут чтения

<div class="termin-card-grid" markdown>

<div class="termin-card termin-card--graphics" markdown>

### [Первый кадр](getting-started.md)

Headless showcase, PNG и JSON report, затем необязательное SDL-окно и
D3D11-only маршрут для Windows.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Карта механизмов](toolbox.md)

Все 18 пакетов, разложенные по данным, GPU/render и presentation tools, с
публичными imports и CMake targets.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Рендер без сцены](rendering.md)

`GraphicsHost`, tgfx2, immutable render snapshots, render core и та граница,
за которой начинается Engine.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Шейдеры и backend-ы](shaders-and-backends.md)

Artifacts, material contracts, capability-driven код и причины не строить
архитектуру на строке `backend == "vulkan"`.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Контракт SDK](sdk.md)

Installed CMake и Python consumption, product identity и проверка без доступа
к исходникам Termin.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Санитарный кордон](boundaries.md)

Куда не пускать scenes, assets и components, даже когда они обещают пробыть
всего одну ночь.

</div>

</div>

Общая схема владения находится на [карте районов](../index.md).
