# Termin App Product Boundary

Дата: 2026-07-19

Статус: Accepted

Реализация: #680 завершает app-payload/distribution часть решения. Editor
payload устанавливается по `build-system/application-python-payloads.json`, а
`termin-app` удалён из wheel/package/runtime metadata. Удаление отдельного
host-derived bundle pipeline остаётся в #681.

## Контекст

`termin-app` исторически одновременно выглядит как C++ приложение и как
обычный Python distribution:

- SDK устанавливает `termin_editor` и `termin_launcher` как native executables;
- editor-specific Python code и `termin.editor._editor_native` образуют
  внутреннюю, загружаемую embedded Python часть приложения;
- `termin-app/setup.py` объявляет distribution `termin-app`, а
  `build-system/packages.json` включает его в общий wheel pipeline;
- top-level `termin-app/CMakeLists.txt` умеет собирать ещё один standalone
  runtime из host `sys.prefix`, stdlib и собственных списков packages;
- Linux `termin-app/build.sh` затем частично заменяет этот runtime содержимым
  SDK, а Windows `termin-app/build.ps1` следует другому пути.

Одновременно Termin имеет настоящие библиотечные distributions: `tcbase`,
`tgfx`, `termin-display`, `termin-gui-native` и другие осмысленные subsets.
Внешний Diffusion Editor устанавливает их из SDK wheelhouse без редактора и
служит живым consumer этого контракта.

SDK уже имеет более строгий источник provenance: exact runtime lock,
`python-runtime-manifest.json`, relocatable `termin-artifacts.json` и
fail-closed verification. Самостоятельный `termin-app` packager создаёт второй
runtime resolver рядом с этим контрактом.

## Решение

`termin-app` является application composition root и C++ executable product, а
не independently installable Python library distribution.

Editor-specific Python modules и `termin.editor._editor_native` являются
app-internal payload редактора. Они устанавливаются как часть editor runtime в
SDK и доступны embedded Python редактора, но это не создаёт обещания
самостоятельного `pip install termin-app`, публичного library API или
транзитивной зависимости для нижележащих packages.

Канонический editor/launcher runtime artifact — проверенное SDK install tree.
Его Python и native provenance задаются SDK manifests и exact runtime lock.
Wheelhouse является воспроизводимым входом и каналом доставки library
distributions, но не вторым источником сборки editor runtime.

Самостоятельный host-derived `termin-app` bundle pipeline удаляется. При
необходимости package-local downstream build может сохраняться как compile/link
smoke против установленного SDK, но не формирует собственный runtime и не
называется product bundle. Relocation acceptance проверяет перемещённую копию
SDK через bundled launcher/editor с очищенным host environment.

Если в будущем понадобится отдельный облегчённый editor-only дистрибутив, он
должен получить явный product manifest и собираться из проверенного SDK. Он не
возрождает разрешение stdlib, packages или native artifacts из host
environment.

### Library distribution contract

Это решение не сворачивает modular wheel architecture. Нижележащие библиотеки,
включая как минимум `tcbase`, `tgfx`, `termin-display` и
`termin-gui-native`, остаются самостоятельными distributions:

- package-local metadata описывает правдивые runtime dependencies;
- clean PEP 517 build использует задекларированный build contract;
- SDK wheelhouse поддерживает установку осмысленных subsets без editor;
- никакой core/runtime package не зависит от `termin-app` или editor-private
  modules;
- Diffusion Editor остаётся обязательным внешним consumer-smoke для graphics,
  display и GUI subset.

## Обоснование

Python wheel описывает повторно используемый installable distribution.
`termin-app` же является владельцем процесса, executable lifecycle, editor UI
и composition policy. Его Python часть загружается собственным embedded host и
не имеет независимого смысла без executable, assets и согласованного SDK.

Отделение app payload от library wheels устраняет ложное публичное обещание и
упрощает dependency graph: reusable functionality должна быть вынесена в
нижний owning package, а не становиться доступной внешним consumers через
установку всего редактора.

Использование SDK как единственного runtime artifact устраняет расхождение
Linux/Windows и не позволяет host `sys.prefix`, ambient `site-packages` или
ручным package lists подменять exact-lock provenance.

## Рассмотренные альтернативы

### Сохранить termin-app как обычный wheel

Отвергнуто. Такой wheel смешивает executable application, editor-private
bindings и library distribution semantics. Он также поощряет зависимость
внешнего кода от editor internals.

### Починить самостоятельный termin-app packager

Отвергнуто. Даже manifest-driven вариант оставил бы второй владелец editor
runtime рядом с SDK без отдельного продуктового требования.

### Сделать termin-app packager тонким копировщиком SDK

Не требуется для текущего продукта. Downstream compile/link и relocation
smokes полезны, но не должны создавать ещё один официально выглядящий bundle.
Отдельный editor-only distribution допустим только как будущий явно названный
product profile.

### Перестать выпускать wheels для всех Termin modules

Отвергнуто. Модульные library distributions являются действующим публичным
контрактом и используются Diffusion Editor. Решение относится только к
application root `termin-app`.

## Последствия и риски

- `termin-app/setup.py`, запись `termin-app` в package manifest и
  `termin-app` metadata в SDK runtime/wheelhouse должны быть удалены;
- установка editor Python payload должна получить явный app-owned путь, не
  зависящий от wheel metadata или broad namespace discovery;
- reusable Python functionality, обнаруженная внутри app payload, должна быть
  вынесена в подходящий library/tooling package до удаления wheel;
- top-level `BUNDLE_PYTHON`, `termin-app/build.sh` и `build.ps1` не должны
  продолжать формировать runtime из host Python;
- существующий installed-bundle smoke использует host Python и должен быть
  заменён настоящим hostile-environment SDK relocation smoke;
- SDK verification должна различать library distributions и app-internal
  payload, не требуя фиктивной `.dist-info` записи для приложения;
- Linux и Windows должны проверять один и тот же продуктовый контракт.

## Последующая работа

1. #680 — выделить app-internal editor Python payload из wheel pipeline,
   удалить distribution `termin-app` и доказать отсутствие editor dependencies
   у устанавливаемых library subsets.
2. #681 — удалить host-derived standalone bundle pipeline и заменить его
   downstream compile/link и relocated-SDK runtime smokes.
3. Сохранить в #481 clean PEP 517 и subset-install contract для библиотечных
   distributions, включая внешний Diffusion Editor consumer.
4. Обновить build/test manifests и документацию после реализации, не объявляя
   текущий `termin-app` wheel удалённым заранее.

## Ссылки

- Kanboard: #633, #680, #681, #481, #483, #240, #358, #27;
- [`docs/build-system.md`](../build-system.md);
- [`docs/modules.md`](../modules.md);
- `termin-app/setup.py`;
- `termin-app/CMakeLists.txt`;
- `termin-app/build.sh`;
- `termin-app/build.ps1`;
- `build-system/packages.json`;
- `scripts/smoke-termin-app-installed-bundle`.
