from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class UniformProperty:
    """
    Описание uniform-свойства материала.

    Атрибуты:
        name: Имя uniform'а (например, "u_glossiness")
        uniform_type: Тип ("float", "int", "bool", "vec2", "vec3", "vec4", "color", "texture2d")
        default: Значение по умолчанию (None для текстур без дефолта)
        range_min: Минимум для range (опционально)
        range_max: Максимум для range (опционально)
        label: Человекочитаемое имя для инспектора (опционально)
    """
    name: str
    uniform_type: str
    default: Any = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    label: Optional[str] = None


def parse_uniform_directive(line: str) -> UniformProperty:
    """
    Парсит директиву @uniform.

    Форматы:
        @uniform float u_name 0.5
        @uniform float u_name 0.5 range(0.0, 1.0)
        @uniform color u_name 1.0 1.0 1.0 1.0
        @uniform vec3 u_name 0.0 1.0 0.0
        @uniform texture2d u_name
        @uniform texture2d u_name "default_texture"
    """
    # Убираем @uniform и лишние пробелы
    content = line[len("@uniform"):].strip()

    # Извлекаем range(...) если есть
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_match = re.search(r'range\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', content)
    if range_match:
        try:
            range_min = float(range_match.group(1).strip())
            range_max = float(range_match.group(2).strip())
        except ValueError:
            pass
        # Убираем range(...) из content
        content = content[:range_match.start()].strip()

    parts = content.split()
    if len(parts) < 2:
        raise ValueError(f"@uniform требует минимум тип и имя: {line!r}")

    uniform_type = parts[0].lower()
    name = parts[1]

    # Валидация типа
    valid_types = {"float", "int", "bool", "vec2", "vec3", "vec4", "color", "texture2d"}
    if uniform_type not in valid_types:
        raise ValueError(f"Неизвестный тип uniform: {uniform_type!r}")

    # Парсим default value
    default: Any = None
    remaining = parts[2:]

    if uniform_type == "float":
        if remaining:
            default = float(remaining[0])
        else:
            default = 0.0
    elif uniform_type == "int":
        if remaining:
            default = int(remaining[0])
        else:
            default = 0
    elif uniform_type == "bool":
        if remaining:
            default = parse_bool(remaining[0])
        else:
            default = False
    elif uniform_type in ("vec2",):
        if len(remaining) >= 2:
            default = (float(remaining[0]), float(remaining[1]))
        else:
            default = (0.0, 0.0)
    elif uniform_type in ("vec3",):
        if len(remaining) >= 3:
            default = (float(remaining[0]), float(remaining[1]), float(remaining[2]))
        else:
            default = (0.0, 0.0, 0.0)
    elif uniform_type in ("vec4", "color"):
        if len(remaining) >= 4:
            default = (float(remaining[0]), float(remaining[1]),
                      float(remaining[2]), float(remaining[3]))
        else:
            default = (1.0, 1.0, 1.0, 1.0) if uniform_type == "color" else (0.0, 0.0, 0.0, 0.0)
    elif uniform_type == "texture2d":
        if remaining:
            # Может быть имя текстуры в кавычках или без
            default = remaining[0].strip('"\'')
        else:
            default = None

    return UniformProperty(
        name=name,
        uniform_type=uniform_type,
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
        @uniform <type> <name> [default] [range(min, max)]
        @stage <stage_name>
        @endstage
        @endphase

    Типы для @uniform:
        float, int, bool, vec2, vec3, vec4, color, texture2d

    Примеры @uniform:
        @uniform float u_glossiness 0.5
        @uniform float u_metallic 0.0 range(0.0, 1.0)
        @uniform color u_color 1.0 1.0 1.0 1.0
        @uniform texture2d u_mainTex

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

        # Если мы внутри @stage, любые строки, кроме директив @endstage, копим как есть
        if current_stage_name is not None:
            if line.startswith("@endstage"):
                close_current_stage()
                continue
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

        if directive == "@uniform":
            if current_phase is None:
                raise ValueError("@uniform вне @phase")
            uniform_prop = parse_uniform_directive(line)
            uniforms_list: List[UniformProperty] = current_phase["uniforms"]
            uniforms_list.append(uniform_prop)
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

    def __init__(self, program: Optional[str], phases: List[ShaderPhase]):
        self.program = program
        self.phases = phases

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
