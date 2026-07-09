# Taskboard CLI

`scripts/taskboard` - удобный слой поверх низкоуровневого `scripts/kanboard-api`.
Он использует тот же `~/.config/termin/kanboard-codex.env`, тот же Termin
Kanboard project id `1` по умолчанию и не требует писать JSON-RPC руками для
обычных операций.

`scripts/kanboard-api` остаётся escape hatch для редких Kanboard methods.

## Частые команды

```bash
scripts/taskboard list
scripts/taskboard list --tags
scripts/taskboard list --column "Ready" --tags
scripts/taskboard list --column "On Test" --tags
scripts/taskboard show 119
scripts/taskboard export --comments --tags --output /tmp/termin-board.json
```

Write-операции имеют dry-run там, где это важно:

```bash
scripts/taskboard close 28 29 41 --dry-run
scripts/taskboard close 28 29 41 --comment "Implemented and verified."
scripts/taskboard comment 119 "Still reproducible after player shutdown fixes."
scripts/taskboard move 13 "Ready" --dry-run
scripts/taskboard move 13 "On Test" --dry-run
scripts/taskboard create "[bug] Short title" --description "Context..."
scripts/taskboard create "[bug] Short title" --description "Context..." --tags bug size:S
```

Справочники:

```bash
scripts/taskboard columns
scripts/taskboard swimlanes
```

## Правила использования

- Для чтения доски и обычных изменений предпочитай `scripts/taskboard`.
- Для массовых закрытий сначала используй `--dry-run`.
- После write-команды `taskboard` перечитывает карточку там, где это важно
  (`close`, `move`, `create --tags`) и падает, если Kanboard не принял
  ожидаемое состояние.
- Для нестандартных JSON-RPC methods используй `scripts/kanboard-api`.
