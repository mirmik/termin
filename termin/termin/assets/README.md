# Assets Architecture

## Правило: Asset классы НЕ должны появляться в коде компонентов

Asset классы занимаются только **элевацией** — загрузкой данных с диска и передачей их потребителям.

### Архитектура

```
Диск (.png, .obj, .wav)
        ↓
    Asset (загрузка, кэширование, hot-reload)
        ↓
    Data (AudioClip, Mesh3, TcTexture)
        ↓
    Handle (smart reference)
        ↓
    Component (работает только с Data через Handle)
```

### Что делает Asset

- Загружает файл с диска (lazy loading)
- Кэширует данные
- Поддерживает hot-reload
- Хранит метаданные (uuid, source_path, version)
- Создаёт и владеет объектом Data

### Что делает Handle

- Предоставляет доступ к Data (не к Asset!)
- Сериализуется по uuid
- Автоматически резолвится через ResourceManager

### Что делает Component

- Хранит Handle, не Asset
- Получает Data через `handle.get()`
- НЕ знает откуда пришли данные (файл, память, сеть)

### Пример правильного кода

```python
# Компонент хранит Handle
class AudioSource(Component):
    clip: AudioClipHandle  # Handle, не Asset!

    def play(self):
        audio_clip = self.clip.get()  # Получаем AudioClip (Data)
        if audio_clip is not None:
            engine.play(audio_clip.chunk)
```

### Пример неправильного кода

```python
# НЕПРАВИЛЬНО: компонент работает с Asset
class AudioSource(Component):
    clip_asset: AudioClipAsset  # Asset в компоненте — нарушение!

    def play(self):
        self.clip_asset.ensure_loaded()  # Компонент знает о загрузке — плохо
```

### Почему это важно

1. **Разделение ответственности** — Asset про загрузку, Component про логику
2. **Тестируемость** — можно подменить данные без файловой системы
3. **Сериализация** — Handle сериализуется в uuid, Asset нет
4. **Hot-reload** — Asset может перезагрузиться, компонент не заметит
