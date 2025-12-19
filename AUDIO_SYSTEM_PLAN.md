# Audio System Implementation Plan

## Overview

Интеграция звуковой подсистемы в termin editor на базе SDL_mixer. Архитектура повторяет паттерны существующей системы: ECS-компоненты, AssetRegistry, InspectField, FileProcessor.

---

## Module Structure

```
termin/
├── audio/
│   ├── __init__.py              ✅
│   ├── audio_engine.py          ✅ Singleton, обёртка над SDL_mixer
│   ├── audio_clip.py            ✅ AudioClipAsset + AudioClipHandle
│   ├── audio_bus.py             # AudioBus, AudioMixer (optional)
│   └── components/
│       ├── __init__.py          ✅
│       ├── audio_source.py      ✅ AudioSource component
│       └── audio_listener.py    ✅ AudioListener component
│
├── visualization/core/
│   ├── resources.py             ✅ + _audio_clip_registry
│   └── component.py             ✅ + audio_clip serialization
│
└── editor/
    ├── file_processors/
    │   └── audio_processor.py   ✅ AudioPreLoader
    └── widgets/
        └── audio_clip_widget.py ✅ AudioClipFieldWidget
```

---

## Implementation Steps

### Step 1: AudioEngine (Core) ✅ DONE

**File:** `termin/audio/audio_engine.py`

Singleton для работы с SDL_mixer:
- `initialize()` — инициализация SDL_mixer
- `shutdown()` — освобождение ресурсов
- `play_chunk(chunk, channel, loops, fade_in_ms)` — воспроизведение
- `stop_channel(channel, fade_out_ms)` — остановка
- `set_channel_volume(channel, volume)` — громкость канала
- `set_channel_position(channel, angle, distance)` — 3D позиционирование

```python
class AudioEngine:
    _instance: "AudioEngine | None" = None

    def __init__(self):
        self._initialized: bool = False
        self._channels: int = 32
        self._frequency: int = 44100

    @classmethod
    def instance(cls) -> "AudioEngine":
        if cls._instance is None:
            cls._instance = AudioEngine()
        return cls._instance
```

---

### Step 2: AudioClipAsset + AudioClipHandle ✅ DONE

**File:** `termin/audio/audio_clip.py`

Ресурс звукового файла:

```python
@dataclass
class AudioClipAsset:
    name: str = ""
    source_path: str = ""
    uuid: str = field(default_factory=lambda: str(uuid4()))
    _chunk: ctypes.c_void_p | None = None
    _duration_seconds: float = 0.0

    def load(self) -> None: ...
    def unload(self) -> None: ...

class AudioClipHandle:
    """Lazy-loading handle."""
    def __init__(self, asset: AudioClipAsset | None = None): ...

    @classmethod
    def from_asset(cls, asset: AudioClipAsset) -> "AudioClipHandle": ...

    def get_asset(self) -> AudioClipAsset | None: ...
```

---

### Step 3: ResourceManager Integration ✅ DONE

**File:** `termin/visualization/core/resources.py`

Добавить в ResourceManager:

```python
# New registry
self._audio_clip_registry: AssetRegistry[AudioClipAsset, AudioClipHandle]

# New methods
def get_audio_clip(self, name: str) -> AudioClipHandle: ...
def get_audio_clip_by_uuid(self, uuid: str) -> AudioClipHandle: ...
def find_audio_clip_uuid(self, handle: AudioClipHandle) -> str | None: ...
def register_audio_clip(self, name: str, asset: AudioClipAsset) -> None: ...
```

---

### Step 4: AudioFileProcessor ✅ DONE

**File:** `termin/editor/file_processors/audio_processor.py`

Загрузчик аудио файлов:

```python
class AudioFileProcessor(FilePreLoader):
    extensions = {".wav", ".ogg", ".mp3", ".flac"}
    priority = 10  # Same as textures (independent resource)

    def preload(self, path: str) -> PreLoadResult | None:
        # Create AudioClipAsset
        # Register in ResourceManager
        # Return PreLoadResult
```

---

### Step 5: AudioSource Component ✅ DONE

**File:** `termin/audio/components/audio_source.py`

Компонент воспроизведения звука:

```python
class AudioSource(Component):
    inspect_fields = {
        "clip": InspectField(path="clip", label="Audio Clip", kind="audio_clip"),
        "volume": InspectField(path="volume", label="Volume", kind="float", min=0.0, max=1.0),
        "pitch": InspectField(path="pitch", label="Pitch", kind="float", min=0.1, max=3.0),
        "loop": InspectField(path="loop", label="Loop", kind="bool"),
        "play_on_awake": InspectField(path="play_on_awake", label="Play On Awake", kind="bool"),
        "spatial_blend": InspectField(path="spatial_blend", label="Spatial Blend", kind="float"),
        "min_distance": InspectField(path="min_distance", label="Min Distance", kind="float"),
        "max_distance": InspectField(path="max_distance", label="Max Distance", kind="float"),
    }

    def __init__(self, clip=None, volume=1.0, pitch=1.0, loop=False, ...): ...

    def play(self) -> None: ...
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...

    def update(self) -> None:
        # Update 3D positioning based on AudioListener
```

**Properties:**
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| clip | AudioClipHandle | None | Audio clip to play |
| volume | float | 1.0 | Volume (0.0 - 1.0) |
| pitch | float | 1.0 | Playback speed (0.1 - 3.0) |
| loop | bool | False | Loop playback |
| play_on_awake | bool | False | Auto-play on entity add |
| spatial_blend | float | 0.0 | 0 = 2D, 1 = 3D |
| min_distance | float | 1.0 | Distance at full volume |
| max_distance | float | 50.0 | Distance at zero volume |

---

### Step 6: AudioListener Component ✅ DONE

**File:** `termin/audio/components/audio_listener.py`

Слушатель (обычно на камере):

```python
class AudioListener(Component):
    inspect_fields = {
        "volume": InspectField(path="volume", label="Master Volume", kind="float"),
    }

    def __init__(self, volume: float = 1.0): ...
```

---

### Step 7: Inspector Widget ✅ DONE

**File:** `termin/editor/widgets/audio_clip_widget.py`

UI виджет для выбора AudioClip:

```python
class AudioClipPicker(QWidget):
    value_changed = Signal(object)

    # Components:
    # - QLineEdit (readonly, shows clip name)
    # - QPushButton "..." (browse)
    # - QPushButton "▶" (preview playback)
```

Также добавить обработку `kind="audio_clip"` в `InspectFieldPanel`.

---

### Step 8 (Optional): AudioBus / AudioMixer

**File:** `termin/audio/audio_bus.py`

Шины микширования:

```python
@dataclass
class AudioBus:
    name: str
    volume: float = 1.0
    muted: bool = False
    channels: list[int] = field(default_factory=list)

class AudioMixer:
    def __init__(self):
        self.buses = {
            "Master": AudioBus("Master"),
            "Music": AudioBus("Music"),
            "SFX": AudioBus("SFX"),
            "Voice": AudioBus("Voice"),
        }
```

---

## Integration Points

### 1. App Initialization

В точке входа приложения:

```python
# Initialize audio engine
AudioEngine.instance().initialize()

# On shutdown
AudioEngine.instance().shutdown()
```

### 2. Scene Update Loop

В игровом цикле вызывать `update()` для AudioSource компонентов:

```python
for entity in scene.entities:
    audio_source = entity.get_component(AudioSource)
    if audio_source and audio_source.enabled:
        audio_source.update()
```

### 3. Component Registration

Зарегистрировать компоненты в ResourceManager:

```python
rm.components["AudioSource"] = AudioSource
rm.components["AudioListener"] = AudioListener
```

### 4. FileProcessor Registration

Добавить в список процессоров:

```python
file_processors.append(AudioFileProcessor())
```

---

## Serialization Format

### AudioSource in .scene file:

```json
{
  "type": "AudioSource",
  "enabled": true,
  "clip": {"uuid": "550e8400-e29b-41d4-a716-446655440000"},
  "volume": 0.8,
  "pitch": 1.0,
  "loop": true,
  "play_on_awake": false,
  "spatial_blend": 1.0,
  "min_distance": 1.0,
  "max_distance": 50.0
}
```

### AudioClipAsset metadata (.audio_clip file, optional):

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "source_path": "assets/sounds/explosion.wav",
  "name": "explosion"
}
```

---

## Dependencies

- `pysdl2` — уже используется для рендеринга
- `sdl2-mixer` — дополнительная библиотека SDL

Установка:
```bash
# Ubuntu/Debian
sudo apt-get install libsdl2-mixer-2.0-0 libsdl2-mixer-dev

# Python bindings (если не включены в pysdl2)
pip install pysdl2-dll  # Includes SDL2_mixer on some platforms
```

---

## Testing Checklist

- [x] AudioEngine инициализируется без ошибок
- [ ] AudioClipAsset загружает .wav файлы
- [ ] AudioClipAsset загружает .ogg файлы
- [ ] AudioClipAsset загружает .mp3 файлы
- [ ] AudioSource воспроизводит звук
- [ ] AudioSource останавливает звук
- [ ] AudioSource loop работает
- [ ] AudioSource volume работает
- [ ] AudioListener влияет на master volume
- [ ] 3D позиционирование работает (spatial_blend = 1)
- [x] AudioFileProcessor загружает файлы при старте (реализовано)
- [ ] Hot-reload аудио файлов работает
- [x] Inspector widget показывает и выбирает клипы (реализовано)
- [x] Preview playback в редакторе работает (реализовано)
- [x] Сериализация/десериализация AudioSource работает (реализовано)

---

## Future Enhancements

1. **Audio Mixer Window** — UI для управления шинами микширования
2. **Waveform Preview** — визуализация волны в инспекторе
3. **Audio Effects** — reverb, echo, low-pass filter (SDL_mixer effects)
4. **Streaming Audio** — для длинных музыкальных треков (Mix_Music)
5. **Audio Occlusion** — приглушение звука за препятствиями (raycast)
6. **Doppler Effect** — эффект Доплера для движущихся источников
