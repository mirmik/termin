# Rfmeas Editor Bridge Plan

## Overview

План первой версии интеграции `rfmeas`-моделей с редактором `termin`.
Цель: дать возможность открывать, редактировать и сохранять модель,
которая нужна `rfmeas`, не пытаясь делать единый формат для editor/runtime.

Стартовый вариант сознательно делается как Python-скрипт внутри проекта
`termin`, без отдельной системы внешних плагинов.

## Context

- В `rfmeas` уже есть свой runtime-oriented JSON с собственной семантикой.
- Формат editor scene и формат `rfmeas` похожи структурно, но не обязаны
  совпадать по смыслу.
- Попытка сделать "полную совместимость форматов" считается рискованной и
  тупиковой.
- В качестве основного механизма roundtrip принимается adapter/import-export
  подход.
- Для сохранения смысловых привязок используется metadata-компонент.

## Goals

- Импортировать `rfmeas` model в editor scene `termin`.
- Сохранять доменную семантику `rfmeas`, которая не выражается обычной
  сценой редактора.
- Давать пользователю редактировать сцену в штатном editor workflow.
- Экспортировать scene обратно в `rfmeas`-совместимый JSON.
- Не вводить на первом этапе отдельную plugin-infrastructure.

## Non-Goals

- Не делать единый общий JSON для editor и runtime.
- Не делать live-синхронизацию с работающим `rfmeas`.
- Не покрывать сразу все компоненты `termin`.
- Не строить отдельную внешнюю систему подключаемых плагинов.

## Proposed Form

Первая версия делается как Python-скрипт в проекте `termin`, например:

- `termin/termin/editor/plugins/rfmeas_bridge.py`

или другой близкий путь внутри editor-side Python-кода.

Скрипт:

- регистрирует editor-команды;
- умеет импортировать `rfmeas` model в текущую сцену;
- умеет экспортировать текущую сцену обратно;
- использует metadata-компонент для roundtrip-семантики.

## Core Design

### 1. Metadata Component

Нужен отдельный metadata-компонент, условно:

- `RfmeasBindingComponent`

Поля первой версии:

- `rfmeas_axis_name`
- `rfmeas_export_role`
- `rfmeas_runtime_component_type`
- `rfmeas_source_id`
- `rfmeas_flags`

Смысл:

- хранить только то, что editor scene сама по себе не выражает;
- не дублировать весь исходный JSON;
- дать экспортёру однозначную информацию для сборки runtime-модели.

### 2. Import Direction

Импорт выполняет:

1. чтение `rfmeas` JSON;
2. создание/очистку текущей scene;
3. построение entity hierarchy;
4. перенос transform;
5. навешивание обычных editor-friendly компонентов;
6. навешивание `RfmeasBindingComponent` там, где нужны export hints;
7. восстановление `axis_mapping` через metadata на нужных entity.

На старте предполагается, что `MeshRenderer` не требует специальной
конверсии: редактор работает с ним нативно, а `rfmeas` уже умеет
прозрачно адаптировать нужный subset при загрузке runtime-модели.

### 3. Export Direction

Экспорт выполняет:

1. обход scene entities;
2. чтение transform и поддерживаемых компонентов;
3. чтение `RfmeasBindingComponent`;
4. сборку `axis_mapping`;
5. фильтрацию editor-only данных;
6. сериализацию в `rfmeas` JSON.

Экспортер обязан быть deterministic:

- одинаковая scene -> одинаковый JSON по смыслу;
- metadata используется как источник истины для runtime-specific связей.

## V1 Supported Data

Первая версия должна поддержать только минимально нужный subset:

- entity hierarchy;
- local transform;
- `MeshRenderer`;
- `mesh_offset_*`;
- `ActuatorComponent` / actuator-like semantics;
- `axis_mapping`;
- metadata roundtrip.

Все прочие компоненты:

- либо игнорируются при экспорте,
- либо оставляются вне scope первой версии.

## Editor UX

Минимальный UX:

- команда `Import rfmeas model...`
- команда `Export rfmeas model...`
- команда `Re-export rfmeas model`

В inspector:

- отдельная секция `Rfmeas`
- редактирование metadata-компонента

Дополнительно, но не обязательно в v1:

- валидация missing `axis_mapping`
- подсветка entity, связанных с runtime axes

## File Layout Proposal

Python-side:

- `termin/termin/editor/plugins/rfmeas_bridge.py`
- `termin/termin/editor/plugins/rfmeas_importer.py`
- `termin/termin/editor/plugins/rfmeas_exporter.py`
- `termin/termin/editor/plugins/rfmeas_metadata.py`

Если окажется, что metadata-компонент проще сделать на C++:

- Python script остаётся orchestrator;
- metadata-компонент переносится в отдельный модуль позже.

## Implementation Phases

### Phase 1: Skeleton Script

- [ ] Создать Python script в editor-side коде
- [ ] Зарегистрировать команды import/export
- [ ] Добавить минимальный entry point в editor startup
- [ ] Проверить, что script подхватывается без отдельной plugin-system

### Phase 2: Metadata Component

- [ ] Реализовать `RfmeasBindingComponent` в Python-first варианте
- [ ] Сделать его видимым в inspector
- [ ] Зафиксировать поля v1
- [ ] Проверить сериализацию metadata внутри editor scene

### Phase 3: Import

- [ ] Прочитать `rfmeas` JSON
- [ ] Построить entity hierarchy
- [ ] Восстановить transform
- [ ] Навесить `MeshRenderer` и нужные runtime-compatible компоненты
- [ ] Разложить `axis_mapping` в metadata
- [ ] Открыть модель в editor и проверить ручное редактирование

### Phase 4: Export

- [ ] Обойти scene
- [ ] Собрать `axis_mapping` из metadata
- [ ] Выкинуть editor-only data
- [ ] Записать `rfmeas` JSON
- [ ] Проверить roundtrip `import -> edit -> export`

### Phase 5: Validation

- [ ] Добавить проверки missing metadata
- [ ] Добавить проверки duplicate axis bindings
- [ ] Добавить предупреждения для unsupported components
- [ ] Зафиксировать ограничения v1 в документации

## Validation Scenarios

Обязательные сценарии для v1:

- импорт существующей `rfmeas` модели и открытие в editor;
- изменение transform у entity и успешный экспорт;
- изменение `mesh_offset_*` и успешный экспорт;
- перенос `axis_mapping` без потери;
- повторный импорт экспортированного файла без структурного развала;
- явное предупреждение на unsupported компонентах.

## Risks

- Python editor API может оказаться недостаточным для красивого metadata UX.
- Некоторые runtime-компоненты могут быть плохо редактируемы в editor без
  специальных adapters.
- Если metadata-компонент будет хранить слишком много, он быстро превратится
  в "свалку исходного JSON".
- Если metadata будет слишком мало, roundtrip станет lossy.

## Decision Notes

- Начинаем со script-in-project, а не с external plugin system.
- Metadata-компонент обязателен.
- `MeshRenderer` в v1 не конвертируется принудительно.
- Источник истины для roundtrip-семантики — metadata + scene state, а не
  побайтная копия исходного JSON.

## Exit Criteria For V1

Версия v1 считается готовой, если:

- editor открывает существующую `rfmeas` модель;
- пользователь может изменить сцену;
- экспорт даёт рабочий `rfmeas` JSON;
- `axis_mapping` и `mesh_offset_*` не теряются;
- решение работает без отдельной plugin infrastructure.
