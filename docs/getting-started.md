# Первые шаги

Этот маршрут позволяет сначала увидеть работающий Termin, а затем создать
собственный минимальный проект. Для знакомства с продуктом не нужно разбираться
в устройстве монорепозитория или писать код движка.

## 1. Соберите SDK

Termin пока распространяется в source-first виде. Для сборки нужны Git, CMake,
C/C++ toolchain и системный Python, достаточный для запуска build
orchestration. Сам SDK использует закреплённый CPython и не зависит от
пользовательского virtual environment.

Из корня репозитория на Linux выполните:

```bash
task build
```

На Windows:

```powershell
task build
```

Первая сборка загружает закреплённый Python toolchain и runtime-зависимости,
поэтому ей нужен доступ к сети. Последующие сборки используют локальные кеши.

После успешной сборки основные программы находятся в `sdk/bin`:

- `termin` — общая командная точка входа;
- `termin_launcher` — создание и выбор проекта;
- `termin_editor` — редактор сцен;
- `termin_player` — host собранного приложения;
- `termin_python` — изолированный Python из SDK.

## 2. Посмотрите готовый проект

Самый короткий путь к осмысленному результату — открыть desktop physics
showcase:

```bash
./sdk/bin/termin_editor \
  test-projects/desktop-physics-showcase/DesktopPhysicsShowcase.terminproj
```

В сцене уже настроены арена, падающие тела, материалы, освещение и тени.

1. Дождитесь загрузки сцены без сообщений об ошибках в Console.
2. Нажмите **Play** на верхней панели или **F5**.
3. Убедитесь, что тела падают и сталкиваются с ареной.
4. Нажмите **Stop** или **F5** ещё раз.

Play Mode работает с отдельным runtime-состоянием. После остановки редактор
возвращается к авторской сцене, поэтому результаты симуляции не записываются в
неё случайно.

## 3. Создайте проект

Запустить графический launcher можно командой:

```bash
task run
```

В launcher выберите **New Project**, укажите имя и родительскую директорию.
Launcher создаст отдельную папку проекта и откроет её в редакторе.

Тот же результат можно получить из командной строки. Сначала добавьте SDK в
текущий shell:

```bash
export PATH="$PWD/sdk/bin:$PATH"
```

Затем создайте проект в новой директории:

```bash
mkdir MyTerminProject
cd MyTerminProject
termin init
termin editor .
```

`termin init` не перезаписывает существующие `.terminproj`, `scene.scene` или
`project_settings`. Если один из этих путей уже занят, команда завершится с
понятной ошибкой.

Созданный проект выглядит примерно так:

```text
MyTerminProject/
├── MyTerminProject.terminproj
├── scene.scene
└── project_settings/
    ├── .editor_state.json
    ├── navigation.json
    └── project.json
```

Файл `.terminproj` обозначает проект, `scene.scene` хранит авторскую сцену, а
`project_settings` — настройки приложения, навигации и состояние редактора.

## 4. Осмотритесь в редакторе

Стартовая сцена уже содержит куб, плоскость, камеру и направленный источник
света. Основные области редактора:

- **Scene Hierarchy** показывает сущности сцены и их иерархию;
- **Viewport** показывает сцену и позволяет выбирать объекты;
- **Inspector** редактирует transform, компоненты и их свойства;
- **Project Browser** показывает сцены, материалы, текстуры, модели и другие
  файлы проекта;
- **Console** показывает сообщения движка, предупреждения и ошибки.

Для первого изменения:

1. Выберите `Cube` в Scene Hierarchy.
2. Измените position или scale в Inspector.
3. Сохраните сцену через **File → Save Scene** или **Ctrl+S**.
4. Включите Play Mode клавишей **F5**.
5. Остановите Play Mode и убедитесь, что редактор вернулся к сохранённому
   авторскому состоянию.

## 5. Запускайте проект из командной строки

Открытую сцену можно запустить без упаковки отдельного приложения:

```bash
termin play --project .
```

Перед запуском source-проекта команда синхронизирует ресурсы SDK в
`<project>/stdlib`. Для проекта, который намеренно не использует стандартную
библиотеку или управляет ею самостоятельно, этот этап можно отключить:

```bash
termin play --project . --no-stdlib-sync
```

Для воспроизводимых сборок используются project build profiles. Они описывают
целевую платформу, entry scene, backend рендеринга и выходную директорию. Профили
можно просматривать и запускать как из меню **Game → Build Profiles...**, так и
через CLI:

```bash
termin profiles --project .
termin build PROFILE --project .
termin run PROFILE --project .
```

Минимальный проект пока не создаёт build profile автоматически. Рабочие
примеры конфигурации находятся в `test-projects`, в частности в
`desktop-physics-showcase` и `android-render-showcase`.

Подробный контракт профилей и поддерживаемые цели описаны в
[документации Termin CLI](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/termin-cli.md).

## Если что-то не работает

- Запускайте редактор из терминала: ранние ошибки и выбранный графический
  backend будут видны в выводе процесса.
- Проверяйте Console редактора: ошибки загрузки компонентов, ресурсов и
  шейдеров не должны игнорироваться.
- Для воспроизводимого запуска передавайте путь к проекту явно:

  ```bash
  ./sdk/bin/termin_editor /absolute/path/to/Project.terminproj
  ```

- После изменения C++/Python bindings полностью пересоберите SDK через
  `task build`.
- Для диагностики build workflow обратитесь к
  [документации системы сборки](build-system.md).

## Куда дальше

- [Основные возможности и маршруты документации](index.md)
- [Тестовые проекты](https://github.com/mirmik/termin/tree/master/test-projects)
- [Termin CLI и build profiles](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/termin-cli.md)
- [Архитектура редактора](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/editor-architecture.md)
- [Карта модулей](modules.md)
