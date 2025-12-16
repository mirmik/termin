from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class MaterialProperty:
    """
    Описание свойства материала для инспектора.

    Атрибуты:
        name: Имя uniform'а в шейдере (например, "u_color")
        property_type: Тип свойства для инспектора:
            - "Float", "Int", "Bool" — скалярные
            - "Vec2", "Vec3", "Vec4" — векторные
            - "Color" — RGBA цвет (отображается как color picker)
            - "Texture" — текстура
        default: Значение по умолчанию
        range_min: Минимум для range (опционально)
        range_max: Максимум для range (опционально)
        label: Человекочитаемое имя для инспектора (опционально)
    """
    name: str
    property_type: str
    default: Any = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    label: Optional[str] = None


# Алиас для обратной совместимости
UniformProperty = MaterialProperty


def _parse_property_value(value_str: str, property_type: str) -> Any:
    """
    Парсит значение свойства из строки.

    Args:
        value_str: Строка со значением (например, "1.0" или "Color(1.0, 0.5, 0.0, 1.0)")
        property_type: Тип свойства

    Returns:
        Распаршенное значение
    """
    value_str = value_str.strip()

    if property_type == "Float":
        return float(value_str)
    elif property_type == "Int":
        return int(value_str)
    elif property_type == "Bool":
        return parse_bool(value_str)
    elif property_type in ("Vec2", "Vec3", "Vec4", "Color"):
        # Парсим конструктор: Color(1.0, 0.5, 0.0, 1.0) или Vec3(1, 2, 3)
        match = re.search(r'\w+\s*\(\s*([^)]+)\s*\)', value_str)
        if match:
            inner = match.group(1)
            values = tuple(float(v.strip()) for v in inner.split(','))
        else:
            # Пробельный формат: 1.0 0.5 0.0 1.0
            values = tuple(float(v) for v in value_str.split())

        # Проверяем/дополняем размерность
        expected_len = {"Vec2": 2, "Vec3": 3, "Vec4": 4, "Color": 4}[property_type]
        if len(values) < expected_len:
            if property_type == "Color":
                values = values + (1.0,) * (expected_len - len(values))
            else:
                values = values + (0.0,) * (expected_len - len(values))
        return values
    elif property_type == "Texture":
        return value_str.strip('"\'') if value_str else None
    else:
        raise ValueError(f"Неизвестный тип свойства: {property_type!r}")


def parse_property_directive(line: str) -> MaterialProperty:
    """
    Парсит директиву @property.

    Формат:
        @property Type name = DefaultValue [range(min, max)]

    Примеры:
        @property Float u_time = 0.0
        @property Float u_metallic = 0.5 range(0.0, 1.0)
        @property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
        @property Vec3 u_lightDir = Vec3(0.0, 1.0, 0.0)
        @property Texture u_mainTex
        @property Texture u_normalMap = "default_normal"

    Поддерживаемые типы:
        Float, Int, Bool, Vec2, Vec3, Vec4, Color, Texture
    """
    # Убираем @property и лишние пробелы
    content = line[len("@property"):].strip()

    # Извлекаем range(...) если есть
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_match = re.search(r'\brange\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', content)
    if range_match:
        try:
            range_min = float(range_match.group(1).strip())
            range_max = float(range_match.group(2).strip())
        except ValueError:
            pass
        # Убираем range(...) из content
        content = content[:range_match.start()].strip()

    # Парсим: Type name = value
    if '=' in content:
        left, right = content.split('=', 1)
        left_parts = left.strip().split()
        if len(left_parts) < 2:
            raise ValueError(f"@property требует тип и имя: {line!r}")

        property_type = left_parts[0]
        name = left_parts[1]
        value_str = right.strip()
    else:
        # Без значения по умолчанию
        parts = content.split()
        if len(parts) < 2:
            raise ValueError(f"@property требует тип и имя: {line!r}")

        property_type = parts[0]
        name = parts[1]
        value_str = ""

    # Валидация типа (с учётом регистра)
    valid_types = {"Float", "Int", "Bool", "Vec2", "Vec3", "Vec4", "Color", "Texture"}
    if property_type not in valid_types:
        raise ValueError(f"Неизвестный тип свойства: {property_type!r}. "
                        f"Допустимые: {', '.join(sorted(valid_types))}")

    # Парсим значение по умолчанию
    if value_str:
        default = _parse_property_value(value_str, property_type)
    else:
        # Дефолты по типам
        defaults = {
            "Float": 0.0,
            "Int": 0,
            "Bool": False,
            "Vec2": (0.0, 0.0),
            "Vec3": (0.0, 0.0, 0.0),
            "Vec4": (0.0, 0.0, 0.0, 0.0),
            "Color": (1.0, 1.0, 1.0, 1.0),
            "Texture": None,
        }
        default = defaults[property_type]

    return MaterialProperty(
        name=name,
        property_type=property_type,
        default=default,
        range_min=range_min,
        range_max=range_max,
    )


def parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"Невозможно интерпретировать как bool: {value!r}")


def parse_shader_text(text: str) -> Dict[str, Any]:
    """
    Парсит кастомный формат шейдера в промежуточное состояние.

    Поддерживаемые директивы:
        @program <name>
        @phase <mark>
        @priority <int>
        @glDepthMask <bool>
        @glDepthTest <bool>
        @glBlend <bool>
        @glCull <bool>
        @property <Type> <name> [= DefaultValue] [range(min, max)]
        @stage <stage_name>
        @endstage
        @endphase

    Типы для @property:
        Float, Int, Bool, Vec2, Vec3, Vec4, Color, Texture

    Примеры @property:
        @property Float u_glossiness = 0.5
        @property Float u_metallic = 0.0 range(0.0, 1.0)
        @property Color u_color = Color(1.0, 1.0, 1.0, 1.0)
        @property Texture u_mainTex

    Структура результата:
        {
            "program": str | None,
            "phases": [
                {
                    "phase_mark": str,
                    "priority": int,
                    "glDepthMask": bool | None,
                    "glDepthTest": bool | None,
                    "glBlend": bool | None,
                    "glCull": bool | None,
                    "uniforms": [UniformProperty, ...],
                    "stages": {
                        "<stage_name>": "<glsl_source>",
                        ...
                    },
                },
                ...
            ],
        }
    """
    lines = text.splitlines(keepends=True)

    program_name: Optional[str] = None
    phases: List[Dict[str, Any]] = []

    current_phase: Optional[Dict[str, Any]] = None
    current_stage_name: Optional[str] = None
    current_stage_lines: List[str] = []

    def start_new_phase(mark: str) -> Dict[str, Any]:
        phase: Dict[str, Any] = {
            "phase_mark": mark,
            "priority": 0,
            "glDepthMask": None,
            "glDepthTest": None,
            "glBlend": None,
            "glCull": None,
            "stages": {},  # type: ignore[dict-anno]
            "uniforms": [],  # List[UniformProperty]
        }
        return phase

    def close_current_stage() -> None:
        nonlocal current_stage_name, current_stage_lines, current_phase
        if current_stage_name is None:
            return
        if current_phase is None:
            raise ValueError("Найдён @endstage вне @phase")

        source = "".join(current_stage_lines)
        stages_dict: Dict[str, str] = current_phase["stages"]  # type: ignore[assignment]
        stages_dict[current_stage_name] = source

        current_stage_name = None
        current_stage_lines = []

    def close_current_phase() -> None:
        nonlocal current_phase
        if current_phase is None:
            return
        # закрываем незакрытую стадию, если есть
        close_current_stage()
        phases.append(current_phase)
        current_phase = None

    for raw_line in lines:
        line = raw_line.strip()

        # Если мы внутри @stage, любые строки, кроме директив, копим как есть
        if current_stage_name is not None:
            if line.startswith("@endstage"):
                close_current_stage()
                continue
            elif line.startswith("@stage "):
                # Новый @stage — закрываем предыдущий и обрабатываем этот
                close_current_stage()
                # Не делаем continue — пусть обработается ниже как @stage
            elif line.startswith("@phase "):
                # Новая фаза — закрываем текущий stage и текущую фазу
                close_current_stage()
                close_current_phase()
                # Не делаем continue — пусть обработается ниже
            elif line.startswith("@endphase"):
                # Закрываем текущий stage и фазу
                close_current_stage()
                # Не делаем continue — пусть обработается ниже
            else:
                current_stage_lines.append(raw_line)
                continue

        # Вне @stage обрабатываем только директивы, остальное игнорируем (можно будет расширить)
        if not line.startswith("@") or line == "@":
            # Пустые строки / комментарии вне stage нам не нужны
            continue

        parts = line.split()
        directive = parts[0]

        if directive == "@program":
            if len(parts) < 2:
                raise ValueError("@program без имени")
            program_name = " ".join(parts[1:])
            continue

        if directive == "@phase":
            if len(parts) < 2:
                raise ValueError("@phase без маркера")
            # Закрываем предыдущую фазу, если она была
            close_current_phase()
            phase_mark = parts[1]
            current_phase = start_new_phase(phase_mark)
            continue

        if directive == "@endphase":
            close_current_phase()
            continue

        if directive == "@priority":
            if current_phase is None:
                raise ValueError("@priority вне @phase")
            if len(parts) < 2:
                raise ValueError("@priority без значения")
            try:
                priority_value = int(parts[1])
            except ValueError as exc:
                raise ValueError(f"Некорректный @priority: {parts[1]!r}") from exc
            current_phase["priority"] = priority_value
            continue

        if directive == "@glDepthMask":
            if current_phase is None:
                raise ValueError("@glDepthMask вне @phase")
            if len(parts) < 2:
                raise ValueError("@glDepthMask без значения")
            depth_mask = parse_bool(parts[1])
            current_phase["glDepthMask"] = depth_mask
            continue

        if directive == "@glDepthTest":
            if current_phase is None:
                raise ValueError("@glDepthTest вне @phase")
            if len(parts) < 2:
                raise ValueError("@glDepthTest без значения")
            depth_test = parse_bool(parts[1])
            current_phase["glDepthTest"] = depth_test
            continue

        if directive == "@glBlend":
            if current_phase is None:
                raise ValueError("@glBlend вне @phase")
            if len(parts) < 2:
                raise ValueError("@glBlend без значения")
            blend_enabled = parse_bool(parts[1])
            current_phase["glBlend"] = blend_enabled
            continue

        if directive == "@glCull":
            if current_phase is None:
                raise ValueError("@glCull вне @phase")
            if len(parts) < 2:
                raise ValueError("@glCull без значения")
            cull_enabled = parse_bool(parts[1])
            current_phase["glCull"] = cull_enabled
            continue

        if directive == "@stage":
            if current_phase is None:
                raise ValueError("@stage вне @phase")
            if len(parts) < 2:
                raise ValueError("@stage без имени стадии")
            if current_stage_name is not None:
                raise ValueError("Вложенный @stage не поддерживается")
            current_stage_name = parts[1]
            current_stage_lines = []
            continue

        if directive == "@endstage":
            # Теоретически сюда не должны попасть, потому что внутри stage мы
            # перехватываем @endstage раньше. Но проверим на всякий случай.
            close_current_stage()
            continue

        if directive == "@property":
            if current_phase is None:
                raise ValueError("@property вне @phase")
            prop = parse_property_directive(line)
            uniforms_list: List[MaterialProperty] = current_phase["uniforms"]
            uniforms_list.append(prop)
            continue

        # Неизвестная директива — на этом этапе просто бросаем ошибку.
        # Можно сделать логирование/варнинг вместо ошибки.
        raise ValueError(f"Неизвестная директива: {directive!r}")

    # Закрываем всё, что осталось
    if current_stage_name is not None:
        # Если файл закончился, а @endstage нет — закроем автоматически
        close_current_stage()

    if current_phase is not None:
        close_current_phase()

    result: Dict[str, Any] = {
        "program": program_name,
        "phases": phases,
    }
    return result


class ShasderStage:
    """
    Описание отдельной стадии шейдера.

    Здесь нет скрытой динамики: имя и исходник задаются явно.
    """

    def __init__(self, name: str, source: str):
        if not name:
            raise ValueError("Имя стадии не может быть пустым")
        self.name = name
        self.source = source

    @staticmethod
    def from_tree(data: Dict[str, Any]) -> "ShasderStage":
        """
        Создание стадии из словаря {"name": ..., "source": ...}.
        """
        name = data.get("name")
        source = data.get("source", "")
        return ShasderStage(str(name), str(source))


class ShaderPhase:
    """
    Фаза шейдера: набор стадий, флаги состояния рендера и uniform-свойства.
    """

    def __init__(
        self,
        phase_mark: str,
        priority: int,
        gl_depth_mask: Optional[bool],
        gl_depth_test: Optional[bool],
        gl_blend: Optional[bool],
        gl_cull: Optional[bool],
        stages: Dict[str, ShasderStage],
        uniforms: Optional[List[UniformProperty]] = None,
    ):
        if not phase_mark:
            raise ValueError("Маркер фазы не может быть пустым")
        self.phase_mark = phase_mark
        self.priority = int(priority)
        self.gl_depth_mask = gl_depth_mask
        self.gl_depth_test = gl_depth_test
        self.gl_blend = gl_blend
        self.gl_cull = gl_cull
        self.stages = stages
        self.uniforms = uniforms if uniforms is not None else []

    @staticmethod
    def from_tree(data: Dict[str, Any]) -> "ShaderPhase":
        """
        Создание фазы из словаря, который возвращает parse_shader_text.
        """
        phase_mark = data.get("phase_mark")
        priority = data.get("priority", 0)
        gl_depth_mask = data.get("glDepthMask")
        gl_depth_test = data.get("glDepthTest")
        gl_blend = data.get("glBlend")
        gl_cull = data.get("glCull")
        stages_raw = data.get("stages", {})
        uniforms_raw = data.get("uniforms", [])

        stages: Dict[str, ShasderStage] = {}
        for stage_name, stage_source in stages_raw.items():
            stage_data = {"name": stage_name, "source": stage_source}
            stage_obj = ShasderStage.from_tree(stage_data)
            stages[stage_name] = stage_obj

        # uniforms уже распаршены как UniformProperty в parse_shader_text
        uniforms: List[UniformProperty] = list(uniforms_raw)

        return ShaderPhase(
            phase_mark=phase_mark,
            priority=priority,
            gl_depth_mask=gl_depth_mask,
            gl_depth_test=gl_depth_test,
            gl_blend=gl_blend,
            gl_cull=gl_cull,
            stages=stages,
            uniforms=uniforms,
        )


class ShaderMultyPhaseProgramm:
    """
    Полное описание мультифазной программы.
    """

    def __init__(
        self,
        program: Optional[str],
        phases: List[ShaderPhase],
        source_path: Optional[str] = None,
    ):
        self.program = program
        self.phases = phases
        self.source_path: Optional[str] = source_path

    @staticmethod
    def from_tree(tree: Dict[str, Any]) -> "ShaderMultyPhaseProgramm":
        """
        Собрать объект из результата parse_shader_text.
        """
        program_name = tree.get("program")
        phases_list_raw = tree.get("phases", [])
        phases: List[ShaderPhase] = []
        for phase_dict in phases_list_raw:
            phases.append(ShaderPhase.from_tree(phase_dict))
        return ShaderMultyPhaseProgramm(program=program_name, phases=phases)

    # ----------------------------------------------------------------
    # Сериализация
    # ----------------------------------------------------------------

    def direct_serialize(self) -> dict:
        """
        Сериализует шейдерную программу в словарь.

        Если source_path задан, возвращает ссылку на файл.
        Иначе сериализует данные inline.
        """
        if self.source_path is not None:
            return {
                "type": "path",
                "path": self.source_path,
            }

        phases_data = []
        for phase in self.phases:
            phase_data = {
                "phase_mark": phase.phase_mark,
                "priority": phase.priority,
                "stages": {
                    name: stage.source
                    for name, stage in phase.stages.items()
                },
            }
            if phase.gl_depth_mask is not None:
                phase_data["gl_depth_mask"] = phase.gl_depth_mask
            if phase.gl_depth_test is not None:
                phase_data["gl_depth_test"] = phase.gl_depth_test
            if phase.gl_blend is not None:
                phase_data["gl_blend"] = phase.gl_blend
            if phase.gl_cull is not None:
                phase_data["gl_cull"] = phase.gl_cull
            if phase.uniforms:
                phase_data["uniforms"] = [
                    {"name": u.name, "type": u.type, "default": u.default}
                    for u in phase.uniforms
                ]
            phases_data.append(phase_data)

        return {
            "type": "inline",
            "program": self.program,
            "phases": phases_data,
        }

    @classmethod
    def direct_deserialize(cls, data: dict) -> "ShaderMultyPhaseProgramm":
        """Десериализует шейдерную программу из словаря."""
        source_path = data.get("path") if data.get("type") == "path" else None

        phases = []
        for phase_data in data.get("phases", []):
            stages = {
                name: ShasderStage(name=name, source=source)
                for name, source in phase_data.get("stages", {}).items()
            }
            uniforms = [
                UniformProperty(
                    name=u["name"],
                    type=u["type"],
                    default=u.get("default"),
                )
                for u in phase_data.get("uniforms", [])
            ]
            phase = ShaderPhase(
                phase_mark=phase_data["phase_mark"],
                priority=phase_data.get("priority", 0),
                gl_depth_mask=phase_data.get("gl_depth_mask"),
                gl_depth_test=phase_data.get("gl_depth_test"),
                gl_blend=phase_data.get("gl_blend"),
                gl_cull=phase_data.get("gl_cull"),
                stages=stages,
                uniforms=uniforms,
            )
            phases.append(phase)

        return cls(
            program=data.get("program"),
            phases=phases,
            source_path=source_path,
        )
