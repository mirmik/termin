from __future__ import annotations

from typing import Any, Dict, List, Optional


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
        @stage <stage_name>
        @endstage
        @endphase

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
