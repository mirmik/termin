# Taskboard CLI

Глобальный скилл `kanboard-taskboard` содержит удобный CLI поверх Kanboard API.
Он умеет выбирать проект по имени или ID и не требует писать JSON-RPC руками
для обычных операций. Если имя текущего репозитория однозначно совпадает с
проектом Kanboard, `--project` можно не указывать. Ниже `taskboard` означает
`~/.codex/skills/kanboard-taskboard/scripts/taskboard`.

Bundled `scripts/kanboard-api` остаётся escape hatch для редких Kanboard methods.

## Частые команды

```bash
taskboard list
taskboard list --tags
taskboard list --column "Ready" --tags
taskboard list --column "On Test" --tags
taskboard show 119
taskboard export --comments --tags --output /tmp/termin-board.json
```

Write-операции имеют dry-run там, где это важно:

```bash
taskboard close 28 29 41 --dry-run
taskboard close 28 29 41 --comment "Implemented and verified."
taskboard comment 119 "Still reproducible after player shutdown fixes."
taskboard move 13 "Ready" --dry-run
taskboard move 13 "On Test" --dry-run
taskboard create "[bug] Short title" --description "Context..."
taskboard create "[bug] Short title" --description "Context..." --tags bug size:S
```

Справочники:

```bash
taskboard columns
taskboard swimlanes
```

## Правила использования

- Для чтения доски и обычных изменений предпочитай CLI из глобального скилла `kanboard-taskboard`.
- Для массовых закрытий сначала используй `--dry-run`.
- После write-команды `taskboard` перечитывает карточку там, где это важно
  (`close`, `move`, `create --tags`) и падает, если Kanboard не принял
  ожидаемое состояние.
- Для нестандартных JSON-RPC methods используй bundled `scripts/kanboard-api` из того же скилла.
