"""
Reusable widget for editing material uniform properties.

This widget can be embedded in MaterialInspector or in component inspectors
(like MeshRenderer) to edit material properties.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

if TYPE_CHECKING:
    from termin.visualization.core.material import Material, MaterialPhase
    from termin.visualization.render.shader_parser import (
        ShaderMultyPhaseProgramm,
        MaterialProperty,
    )


class MaterialPropertiesEditor(QWidget):
    """
    Reusable editor for material uniform properties.

    Displays editors for all uniform properties defined in the shader,
    allowing users to modify material parameters.

    Signals:
        property_changed: Emitted when any property value changes.
                         Args: (property_name: str, new_value: Any)
        editing_finished: Emitted when editing is complete (for autosave).
    """

    property_changed = pyqtSignal(str, object)  # property_name, new_value
    editing_finished = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._material: Material | None = None
        self._shader_program: ShaderMultyPhaseProgramm | None = None
        self._property_widgets: Dict[str, QWidget] = {}
        self._phase_combos: List[Tuple[int, QComboBox]] = []  # (phase_index, combo)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def set_material(
        self,
        material: Material | None,
        shader_program: ShaderMultyPhaseProgramm | None = None,
    ) -> None:
        """
        Set the material to edit.

        Args:
            material: The material to edit.
            shader_program: Optional shader program for property definitions.
                           If not provided, will try to load from ResourceManager.
        """
        self._material = material

        if shader_program is not None:
            self._shader_program = shader_program
        elif material is not None:
            from termin.visualization.core.resources import ResourceManager
            rm = ResourceManager.instance()
            self._shader_program = rm.get_shader(material.shader_name)
        else:
            self._shader_program = None

        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        """Rebuild the UI for the current material."""
        # Clear existing widgets
        self._property_widgets.clear()
        self._phase_combos = []
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._material is None or self._shader_program is None:
            return

        # Phase selectors for each phase with multiple available marks
        for i, phase in enumerate(self._material.phases):
            available = phase.available_marks
            if len(available) > 1:
                self._create_phase_selector_for_phase(i, phase)
            elif len(available) == 1:
                self._create_phase_label(available[0])

        # Collect all properties from all phases
        all_properties: Dict[str, "MaterialProperty"] = {}
        for phase in self._shader_program.phases:
            for prop in phase.uniforms:
                if prop.name not in all_properties:
                    all_properties[prop.name] = prop

        # Create editors for each property
        for prop in all_properties.values():
            self._create_property_editor(prop)

    def _create_phase_label(self, phase_mark: str) -> None:
        """Create a simple label showing the phase when there's no choice."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label = QLabel("Render Mode:")
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        value_label = QLabel(phase_mark)
        value_label.setStyleSheet("color: #888;")
        row_layout.addWidget(value_label, 1)

        self._layout.addWidget(row_widget)

    def _create_phase_selector_for_phase(self, phase_index: int, phase: "MaterialPhase") -> None:
        """Create phase selector ComboBox for a specific phase with multiple available marks."""
        from termin.visualization.core.material import MaterialPhase

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        # Label shows phase index if multiple phases, otherwise just "Render Mode"
        label_text = f"Phase {phase_index + 1}:" if len(self._material.phases) > 1 else "Render Mode:"
        label = QLabel(label_text)
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        combo = QComboBox()
        for mark in phase.available_marks:
            combo.addItem(mark, mark)

        # Set current value
        current = phase.phase_mark
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)

        combo.currentIndexChanged.connect(
            lambda idx, pi=phase_index: self._on_phase_mark_changed(pi, idx)
        )
        row_layout.addWidget(combo, 1)

        self._phase_combos.append((phase_index, combo))
        self._layout.addWidget(row_widget)

    def _on_phase_mark_changed(self, phase_index: int, combo_index: int) -> None:
        """Handle phase mark selection change for a specific phase."""
        if self._material is None or phase_index >= len(self._material.phases):
            return

        # Find the combo for this phase
        combo = None
        for pi, c in self._phase_combos:
            if pi == phase_index:
                combo = c
                break

        if combo is None:
            return

        new_mark = combo.itemData(combo_index)
        self._material.phases[phase_index].set_phase_mark(new_mark)
        self.property_changed.emit(f"phase_{phase_index}_mark", new_mark)
        self._on_editing_finished()

    def _create_property_editor(self, prop: "MaterialProperty") -> None:
        """Create an editor widget for a material property."""
        from termin.editor.material_inspector import (
            ColorButton,
            Vec2Editor,
            Vec3Editor,
            Vec4Editor,
            TextureSelector,
        )

        # Get current value from material
        current_value = None
        if self._material is not None:
            current_value = self._material.uniforms.get(prop.name)
        if current_value is None:
            current_value = prop.default

        # Label text
        label_text = prop.label or prop.name

        # Create row widget
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label = QLabel(label_text + ":")
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        editor: QWidget | None = None

        if prop.property_type == "Float":
            editor = self._create_float_editor(prop, current_value)
        elif prop.property_type == "Int":
            editor = self._create_int_editor(prop, current_value)
        elif prop.property_type == "Bool":
            editor = self._create_bool_editor(prop, current_value)
        elif prop.property_type == "Vec2":
            editor = self._create_vec2_editor(prop, current_value)
        elif prop.property_type == "Vec3":
            editor = self._create_vec3_editor(prop, current_value)
        elif prop.property_type == "Vec4":
            editor = self._create_vec4_editor(prop, current_value)
        elif prop.property_type == "Color":
            editor = self._create_color_editor(prop, current_value)
        elif prop.property_type == "Texture":
            editor = self._create_texture_editor(prop, current_value)

        if editor is not None:
            row_layout.addWidget(editor, 1)
            self._property_widgets[prop.name] = editor

        self._layout.addWidget(row_widget)

    def _create_float_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setSingleStep(0.1)

        if prop.range_min is not None and prop.range_max is not None:
            spin.setRange(prop.range_min, prop.range_max)
        else:
            spin.setRange(-9999.0, 9999.0)

        spin.setValue(float(value) if value is not None else 0.0)
        spin.valueChanged.connect(
            lambda v, name=prop.name: self._on_property_changed(name, v)
        )
        spin.editingFinished.connect(self._on_editing_finished)
        return spin

    def _create_int_editor(self, prop: "MaterialProperty", value: Any) -> QSpinBox:
        spin = QSpinBox()

        if prop.range_min is not None and prop.range_max is not None:
            spin.setRange(int(prop.range_min), int(prop.range_max))
        else:
            spin.setRange(-9999, 9999)

        spin.setValue(int(value) if value is not None else 0)
        spin.valueChanged.connect(
            lambda v, name=prop.name: self._on_property_changed(name, v)
        )
        spin.editingFinished.connect(self._on_editing_finished)
        return spin

    def _create_bool_editor(self, prop: "MaterialProperty", value: Any) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(value) if value is not None else False)
        checkbox.stateChanged.connect(
            lambda state, name=prop.name: self._on_property_changed(
                name, state == Qt.CheckState.Checked.value
            )
        )
        checkbox.stateChanged.connect(lambda _: self._on_editing_finished())
        return checkbox

    def _create_vec2_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> "Vec2Editor":
        from termin.editor.material_inspector import Vec2Editor

        val = value if value is not None else (0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec2Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_property_changed(
                name, np.array(v, dtype=np.float32)
            )
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_vec3_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> "Vec3Editor":
        from termin.editor.material_inspector import Vec3Editor

        val = value if value is not None else (0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec3Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_property_changed(
                name, np.array(v, dtype=np.float32)
            )
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_vec4_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> "Vec4Editor":
        from termin.editor.material_inspector import Vec4Editor

        val = value if value is not None else (0.0, 0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec4Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_property_changed(
                name, np.array(v, dtype=np.float32)
            )
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_color_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> "ColorButton":
        from termin.editor.material_inspector import ColorButton

        val = value if value is not None else (1.0, 1.0, 1.0, 1.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = ColorButton(val)
        editor.color_changed.connect(
            lambda v, name=prop.name: self._on_property_changed(name, v)  # v is Vec4
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_texture_editor(
        self, prop: "MaterialProperty", value: Any
    ) -> "TextureSelector":
        from termin.editor.material_inspector import TextureSelector
        from termin.visualization.core.resources import ResourceManager

        editor = TextureSelector()
        editor.refresh_texture_list()

        # Determine current texture name
        texture_name = ""
        if self._material is not None:
            texture = self._material.textures.get(prop.name)
            if texture is not None:
                rm = ResourceManager.instance()
                texture_name = rm.find_texture_name(texture) or ""
                # Skip white texture - show as None
                if texture_name == "__white_1x1__":
                    texture_name = ""

        editor.set_texture_name(texture_name)
        editor.texture_changed.connect(
            lambda name, uniform_name=prop.name: self._on_texture_changed(
                uniform_name, name
            )
        )
        editor.editing_finished.connect(self._on_editing_finished)

        return editor

    def _on_property_changed(self, name: str, value: Any) -> None:
        """Handle property value change."""
        if self._material is None:
            return

        # Convert numpy arrays to Vec3/Vec4 for C++ set_param
        from termin.geombase import Vec3, Vec4
        converted_value = value
        if isinstance(value, np.ndarray):
            if value.size == 3:
                converted_value = Vec3(float(value[0]), float(value[1]), float(value[2]))
            elif value.size == 4:
                converted_value = Vec4(float(value[0]), float(value[1]), float(value[2]), float(value[3]))

        # Update value in all phases of the material
        # Use set_param to properly update C++ uniforms map
        for phase in self._material.phases:
            phase.set_param(name, converted_value)

        self.property_changed.emit(name, value)

    def _on_texture_changed(self, uniform_name: str, texture_name: str) -> None:
        """Handle texture change."""
        if self._material is None:
            return

        from termin.visualization.core.resources import ResourceManager
        from termin.visualization.core.texture_handle import get_white_texture_handle, get_normal_texture_handle

        rm = ResourceManager.instance()

        if texture_name:
            texture_handle = rm.get_texture_handle(texture_name)
        else:
            # Use default texture from shader property definition
            default_tex_name = "white"
            if self._shader_program is not None:
                for phase in self._shader_program.phases:
                    for prop in phase.uniforms:
                        if prop.name == uniform_name and prop.property_type == "Texture":
                            if isinstance(prop.default, str):
                                default_tex_name = prop.default
                            break

            if default_tex_name == "normal":
                texture_handle = get_normal_texture_handle()
            else:
                texture_handle = get_white_texture_handle()

        if texture_handle is not None:
            for phase in self._material.phases:
                phase.set_texture(uniform_name, texture_handle)

        self.property_changed.emit(uniform_name, texture_name)

    def _on_editing_finished(self) -> None:
        """Handle editing finished."""
        self.editing_finished.emit()

    def refresh(self) -> None:
        """Refresh all property widgets from the material."""
        self._rebuild_ui()

    @property
    def material(self) -> Material | None:
        """Current material being edited."""
        return self._material
