# termin-tween

`termin-tween` содержит независимое ядро твининга: easing-функции,
базовые tween-классы и `TweenManager`.

`MoveTween` и `ScaleTween` хранят состояние как `Vec3`, а `RotateTween` — как
нормализованный `Quat` и интерполирует его через checked `Quat.slerp`. На
публичной границе также принимаются числовые sequence ровно из 3 компонентов
для векторов и 4 для quaternion; NumPy пакету не требуется.

Пакет не зависит от editor/UI-слоя и не импортирует scene-компоненты при
`import termin.tween`.

Компонент `TweenManagerComponent` вынесен в `termin-components-tween`.
Канонический прямой импорт — `termin.tween_components`, а ленивый публичный
импорт `from termin.tween import TweenManagerComponent` сохраняется.
