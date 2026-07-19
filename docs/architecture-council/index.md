# Architecture Council

Здесь хранятся краткие протоколы архитектурного совета: принятые направления,
контекст обсуждения и ещё не утверждённые детали реализации.

Действующие архитектурные контракты после окончательной проработки переносятся
в [`docs/architecture`](../architecture/index.md).

## Протоколы

- [Retire Authored GLSL Preprocessing](2026-07-19-retire-authored-glsl-preprocessing.md)
  — Slang как единственный authored shader contract и удаление глобального
  GLSL preprocessing pipeline.
- [Engine Loop Client and Editor Session](2026-07-19-engine-loop-client-and-editor-session.md)
  — внешнее атомарное подключение редактора к `EngineCore` и явное владение
  editor session.
