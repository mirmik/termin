# Утечка host Python окружения в SDK build

Дата: 2026-06-08

## Контекст

Во время Windows-сборки:

```powershell
.\build-sdk.ps1 --no-vulkan --no-sdl --no-wheels
```

Stage 3 (`Populate bundled Python site-packages`) вывел предупреждение pip о
пакете `simple-lama-inpainting`. Этот пакет относится к ранее вынесенному
`diffusion-editor` и не является зависимостью Termin.

Поиск по репозиторию Termin не нашел прямой зависимости на
`simple-lama-inpainting`; пакет был установлен в активном host Python:

```text
C:\Users\sorok\AppData\Local\Programs\Python\Python312\Lib\site-packages
```

Это показало, что SDK build не полностью изолирован от пользовательского Python
окружения.

## Наблюдаемый симптом

Pip сообщил конфликт зависимостей host Python:

```text
simple-lama-inpainting 0.1.2 requires numpy<2.0.0,>=1.24.3
simple-lama-inpainting 0.1.2 requires pillow<10.0.0,>=9.5.0
```

При этом `termin-app/requirements.txt` содержит только обычные SDK-зависимости
вроде `numpy`, `Pillow`, `scipy`, `PyOpenGL`, `pysdl2`, `watchdog` и не содержит
`simple-lama-inpainting`.

## Где происходит выход наружу

### 1. Главный скрипт выбирает обычный Python из PATH

`build-sdk.ps1` выбирает интерпретатор в таком порядке:

1. `PYTHON_BIN`
2. `PYTHON_EXECUTABLE`
3. `python`
4. `python3`

Если переменные не заданы, сборка использует обычный установленный Python
пользователя. В наблюдаемом случае это был:

```text
C:\Users\sorok\AppData\Local\Programs\Python\Python312\python.exe
```

### 2. Orchestrator использует host Python как build Python

`termin-build-tools/termin_build/sdk.py::_python_executable()` возвращает
`PYTHON_EXECUTABLE`, `PYTHON_BIN` или `sys.executable`. Для Stage 3 отдельный
venv не создается.

### 3. Runtime layout строится из host Python paths

`_python_version_and_paths()` читает:

- `sys.prefix`;
- `sysconfig.get_paths()["stdlib"]`;
- `site.getsitepackages()`;
- `site.getusersitepackages()`.

Затем `ensure_bundled_python_runtime()` копирует stdlib host Python в SDK и
проходит по host `site-packages`, копируя часть пакетов из
`EXTERNAL_PYTHON_PACKAGES` (`numpy`, `PIL`, `scipy`, `OpenGL`, `sdl2`, `yaml`,
`watchdog` и др.) в bundled `site-packages`.

Это прямой канал, через который содержимое global/user Python может влиять на
SDK.

### 4. Windows Stage 3 запускает pip без изолированного окружения

На Windows `install_python_packages()` сначала выполняет:

```text
host-python -m pip install --upgrade --target sdk/python/Lib/site-packages -r termin-app/requirements.txt
```

`--target` задает директорию установки, но не делает resolver изолированным.
Pip все равно видит installed distributions активного host Python и может
выдавать предупреждения или принимать решения с учетом global `site-packages`.

После этого вызывается установка Termin-пакетов через общий
`install_pip_packages(..., target_dir=..., editable=False, force=True)`.

### 5. PYTHONPATH наследуется

PowerShell wrapper-скрипты добавляют `termin-build-tools` в начало
`PYTHONPATH`, но сохраняют старое значение:

```powershell
$env:PYTHONPATH = "$env:PYTHONPATH$([IO.Path]::PathSeparator)$oldPythonPath"
```

Это полезно для совместимости, но для SDK build ослабляет изоляцию: внешние
пути пользователя остаются видимыми Python-процессам сборки.

## Почему это плохо

- Сборка SDK зависит от состояния пользовательского Python, а не только от
  репозитория, lock/requirements и toolchain.
- Один и тот же коммит может давать разные bundled SDK в зависимости от
  global/user `site-packages`.
- Pip warnings от посторонних проектов загрязняют build log и маскируют
  реальные проблемы Termin.
- Host packages могут попасть в SDK не через явный requirements-файл, а через
  ручное копирование из `site.getsitepackages()`.
- На CI и dev-машинах поведение будет различаться, если активный Python
  содержит разные пакеты.

## Рекомендации

### Краткосрочно

1. Для Stage 3 создавать отдельный build/bundle venv в `build/sdk-python-venv`
   или аналогичной директории.
2. Запускать pip для bundled SDK только через Python из этого venv.
3. Перед pip-вызовами очищать переменные, влияющие на импорт и resolver:
   `PYTHONPATH`, `PYTHONHOME`, `PYTHONUSERBASE`; выставлять
   `PYTHONNOUSERSITE=1`.
4. Убрать использование host `site.getsitepackages()` как источника внешних
   пакетов для SDK. Внешние пакеты должны попадать в SDK только через
   requirements/constraints/wheelhouse.
5. Для `pip install --target` использовать `--no-deps` там, где зависимости уже
   установлены контролируемым первым шагом, или устанавливать все зависимости
   через один constraints-controlled шаг.

### Среднесрочно

1. Ввести constraints/lock-файл для bundled Python runtime, отдельный от
   loose `termin-app/requirements.txt`.
2. Разделить роли:
   - host Python: только bootstrap orchestrator;
   - build venv: CMake/nanobind/pip build tooling;
   - bundled Python runtime: итоговая stdlib + site-packages SDK.
3. Добавить диагностический вывод Stage 3:
   - путь к Python executable;
   - `sys.prefix`;
   - включен ли user site;
   - target `site-packages`;
   - путь constraints-файла.
4. Добавить проверку, что bundled `site-packages` не содержит пакетов вне
   разрешенного manifest/requirements набора.

### Долгосрочно

1. Перейти к сборке bundled Python packages из wheelhouse:
   - сначала собрать/download wheelhouse в контролируемую директорию;
   - затем устанавливать SDK runtime из wheelhouse с `--no-index --find-links`.
2. Сделать Windows и Linux Stage 3 симметричными: один изолированный механизм
   установки зависимостей, отличающийся только layout (`sdk/python/Lib` против
   `sdk/lib/pythonX.Y`).
3. Зафиксировать политику: SDK build не читает global/user `site-packages`, за
   исключением stdlib/runtime файлов самого выбранного Python.

## Текущее решение не выполнено

Эта заметка фиксирует расследование и направление исправления. На 2026-06-08
изоляция Stage 3 не внедрена.
