# Система документации

Документация Termin описывает не только как вызвать API, но и кому этот API
принадлежит, где проходит его lifecycle и какое нарушение обязано упасть.
Основной принцип прост: деталям следует жить рядом с владельцем, а тексты о
границах между владельцами остаются в корневом портале.

## Уровни

| Уровень | Где лежит | Что хранит |
|---|---|---|
| Вход и маршруты | `docs/index.md` | Пользовательские и инженерные пути чтения |
| District guide | `docs/districts/<district>/` | Самостоятельный обзор района, его SDK, ownership и boundaries |
| Cross-district архитектура | `docs/architecture/`, `docs/modules.md` | Направление зависимостей, общие решения и capability map |
| Документация package | `<district>/<package>/docs/` | API, lifecycle, ownership, gotchas и focused examples |
| Migration history | `docs/plans/`, `docs/analysis/` | Временные планы, аудиты и следы переходов |
| README | `<district>/<package>/README.md` | Короткий вход и ссылка на полный source of truth |

District guide можно читать отдельно от остального продукта, но он остаётся
разделом одного GitHub Pages portal. District — не самостоятельный build root,
поэтому отдельный MkDocs и собственная CI ему не положены.

## Правила ссылок

- Для материалов внутри публичного portal используйте обычные относительные
  Markdown links: `[Core](districts/core/index.md)`.
- Для package docs, которые пока классифицированы как internal roots,
  используйте канонический GitHub path, например
  `[termin-gui-native](https://github.com/mirmik/termin/blob/master/graphics/termin-gui-native/README.md)`.
- Wiki links `[[...]]` допустимы только в личных черновиках, не являющихся
  source of truth.
- После перемещения package между districts проверяйте глубину относительных
  ссылок: `../../docs` из старого flat layout почти наверняка уже указывает в
  несуществующий каталог.
- Module passport должен называть owner district и ссылаться на ближайший
  district guide либо [карту районов](districts/index.md).

## Публикация

Единственная публичная команда локальной и CI-сборки:

```console
task docs:build
```

Она создаёт pinned disposable environment в `build/python-envs/docs`,
проверяет documentation inventory и собирает все публичные сайты в `_site/`
с MkDocs strict mode. Пользовательский MkDocs и docs tools внутри runtime SDK
не требуются.

Для принудительного пересоздания окружения:

```console
task docs:setup -- --force
```

Publication topology задаёт `build-system/docs-publication.json`. Корневой
portal содержит cross-district документацию; самостоятельные package sites
добавляются в manifest только тогда, когда их nav, links и repository metadata
действительно готовы к strict build.

## Что писать в district guide

Каждый зрелый guide отвечает на шесть вопросов:

1. За что отвечает район и чего он не владеет?
2. Какие packages составляют canonical roster?
3. Какой root task строит его продукт и куда он устанавливается?
4. Как выглядит installed CMake/Python consumption?
5. Какая проверка доказывает boundary без source fallback?
6. Где заканчивается район и начинается adapter следующего слоя?

Яркий вводный текст приветствуется. Команда, target, import и failure mode
после него должны оставаться буквальными.

## Что писать рядом с package

Package document описывает локальный public API, ownership, threading,
lifetime, errors и focused examples. Он не пересказывает устройство всего
района и не объявляет свой `CMakeLists.txt` самостоятельным проектом.

Если текст разросся до cross-package contracts, вынесите эту часть в district
guide. Если решение связывает несколько districts — в `docs/architecture/`.

## Живая документация и история

Завершённый migration plan не должен оставаться единственным описанием
текущего мира. Итог переносится в живой guide или package passport; plan
остаётся историей и явно помечается superseded, если его топология больше не
канонична.

Перед завершением архитектурной правки проверьте:

- обновлён ли district guide или package passport;
- не остался ли новый behavior только в плане;
- совпадают ли команды с корневым `Taskfile.yml`;
- совпадают ли output paths с `build-system/sdk-profiles.json`;
- есть ли маршрут из `mkdocs.yml`, README или ближайшего index;
- проходит ли `task docs:build` либо зафиксирован ли внешний blocker этой
  команды.
