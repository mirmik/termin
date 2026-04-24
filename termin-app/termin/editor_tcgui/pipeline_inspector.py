"""Pipeline inspector for tcgui."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.separator import Separator
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.message_box import MessageBox
from tcgui.widgets.input_dialog import show_input_dialog
from tcgui.widgets.units import px

from termin.editor_tcgui.inspect_field_panel import InspectFieldPanel


class PipelineInspectorTcgui(VStack):
    """Specialized tcgui inspector for RenderPipeline."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._pipeline = None
        self._pipeline_name = ""
        self._source_path: str | None = None
        self._selected_postprocess = None
        self._selected_spec_index = -1
        self._updating = False
        self._updating_spec = False

        self.on_changed: Optional[Callable[[], None]] = None

        self._build_ui()
        self._set_visible_state(False)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        title = Label()
        title.text = "Pipeline Inspector"
        self.add_child(title)

        self._subtitle = Label()
        self._subtitle.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._subtitle)

        self.add_child(Separator())

        # Passes row
        passes_title = Label()
        passes_title.text = "Passes"
        self.add_child(passes_title)

        passes_row = HStack()
        passes_row.spacing = 4
        passes_row.preferred_height = px(130)

        self._passes_list = ListWidget()
        self._passes_list.item_height = 22
        self._passes_list.item_spacing = 1
        self._passes_list.stretch = True
        self._passes_list.on_select = self._on_pass_selected
        passes_row.add_child(self._passes_list)

        pass_btns = VStack()
        pass_btns.spacing = 4

        self._pass_add = Button()
        self._pass_add.text = "+"
        self._pass_add.preferred_width = px(28)
        self._pass_add.on_click = self._on_add_pass
        pass_btns.add_child(self._pass_add)

        self._pass_remove = Button()
        self._pass_remove.text = "-"
        self._pass_remove.preferred_width = px(28)
        self._pass_remove.on_click = self._on_remove_pass
        pass_btns.add_child(self._pass_remove)

        self._pass_up = Button()
        self._pass_up.text = "▲"
        self._pass_up.preferred_width = px(28)
        self._pass_up.on_click = self._on_move_pass_up
        pass_btns.add_child(self._pass_up)

        self._pass_down = Button()
        self._pass_down.text = "▼"
        self._pass_down.preferred_width = px(28)
        self._pass_down.on_click = self._on_move_pass_down
        pass_btns.add_child(self._pass_down)

        passes_row.add_child(pass_btns)
        self.add_child(passes_row)

        pass_name_row = HStack()
        pass_name_row.spacing = 6
        pass_name_lbl = Label()
        pass_name_lbl.text = "Pass name:"
        pass_name_lbl.preferred_width = px(96)
        pass_name_row.add_child(pass_name_lbl)
        self._pass_name = TextInput()
        self._pass_name.on_submit = self._on_pass_name_submitted
        self._pass_name.stretch = True
        pass_name_row.add_child(self._pass_name)
        self.add_child(pass_name_row)

        pass_enabled_row = HStack()
        pass_enabled_row.spacing = 6
        pass_enabled_lbl = Label()
        pass_enabled_lbl.text = "Enabled:"
        pass_enabled_lbl.preferred_width = px(96)
        pass_enabled_row.add_child(pass_enabled_lbl)
        self._pass_enabled = Checkbox()
        self._pass_enabled.on_changed = self._on_pass_enabled_changed
        pass_enabled_row.add_child(self._pass_enabled)
        pass_enabled_spacer = Label()
        pass_enabled_spacer.stretch = True
        pass_enabled_row.add_child(pass_enabled_spacer)
        self.add_child(pass_enabled_row)

        self._pass_fields = InspectFieldPanel(self._rm)
        self._pass_fields.on_field_changed = self._on_pass_field_changed
        self.add_child(self._pass_fields)

        # Effects (for PostProcessPass only)
        self.add_child(Separator())
        self._effects_title = Label()
        self._effects_title.text = "Post Effects"
        self.add_child(self._effects_title)

        effects_row = HStack()
        effects_row.spacing = 4
        effects_row.preferred_height = px(100)

        self._effects_list = ListWidget()
        self._effects_list.item_height = 22
        self._effects_list.item_spacing = 1
        self._effects_list.stretch = True
        self._effects_list.on_select = self._on_effect_selected
        effects_row.add_child(self._effects_list)

        eff_btns = VStack()
        eff_btns.spacing = 4

        self._effect_add = Button()
        self._effect_add.text = "+"
        self._effect_add.preferred_width = px(24)
        self._effect_add.on_click = self._on_add_effect
        eff_btns.add_child(self._effect_add)

        self._effect_remove = Button()
        self._effect_remove.text = "-"
        self._effect_remove.preferred_width = px(24)
        self._effect_remove.on_click = self._on_remove_effect
        eff_btns.add_child(self._effect_remove)

        self._effect_up = Button()
        self._effect_up.text = "▲"
        self._effect_up.preferred_width = px(24)
        self._effect_up.on_click = self._on_move_effect_up
        eff_btns.add_child(self._effect_up)

        self._effect_down = Button()
        self._effect_down.text = "▼"
        self._effect_down.preferred_width = px(24)
        self._effect_down.on_click = self._on_move_effect_down
        eff_btns.add_child(self._effect_down)

        effects_row.add_child(eff_btns)
        self.add_child(effects_row)

        eff_name_row = HStack()
        eff_name_row.spacing = 6
        eff_name_lbl = Label()
        eff_name_lbl.text = "Effect name:"
        eff_name_lbl.preferred_width = px(96)
        eff_name_row.add_child(eff_name_lbl)
        self._effect_name = TextInput()
        self._effect_name.on_submit = self._on_effect_name_submitted
        self._effect_name.stretch = True
        eff_name_row.add_child(self._effect_name)
        self.add_child(eff_name_row)

        self._effect_fields = InspectFieldPanel(self._rm)
        self._effect_fields.on_field_changed = self._on_effect_field_changed
        self.add_child(self._effect_fields)

        # Resource specs
        self.add_child(Separator())
        specs_title = Label()
        specs_title.text = "Resource Specs (FBO)"
        self.add_child(specs_title)

        specs_row = HStack()
        specs_row.spacing = 4
        specs_row.preferred_height = px(84)

        self._specs_list = ListWidget()
        self._specs_list.item_height = 22
        self._specs_list.item_spacing = 1
        self._specs_list.stretch = True
        self._specs_list.on_select = self._on_spec_selected
        specs_row.add_child(self._specs_list)

        spec_btns = VStack()
        spec_btns.spacing = 4
        self._spec_add = Button()
        self._spec_add.text = "+"
        self._spec_add.preferred_width = px(24)
        self._spec_add.on_click = self._on_add_spec
        spec_btns.add_child(self._spec_add)

        self._spec_remove = Button()
        self._spec_remove.text = "-"
        self._spec_remove.preferred_width = px(24)
        self._spec_remove.on_click = self._on_remove_spec
        spec_btns.add_child(self._spec_remove)

        specs_row.add_child(spec_btns)
        self.add_child(specs_row)

        self._spec_editor = VStack()
        self._spec_editor.spacing = 4
        self.add_child(self._spec_editor)

        self._spec_resource = TextInput()
        self._spec_resource.on_submit = self._on_spec_field_changed
        self._spec_samples = ComboBox()
        for item in ("1", "2", "4", "8"):
            self._spec_samples.add_item(item)
        self._spec_samples.on_changed = self._on_spec_field_changed_combo
        self._spec_format = ComboBox()
        for item in ("rgba8", "rgba16f", "rgba32f", "r8", "r16f", "r32f"):
            self._spec_format.add_item(item)
        self._spec_format.on_changed = self._on_spec_field_changed_combo

        self._spec_clear_color = Checkbox()
        self._spec_clear_color.on_changed = self._on_spec_field_changed_check
        self._spec_clear_r = TextInput(); self._spec_clear_r.on_submit = self._on_spec_field_changed
        self._spec_clear_g = TextInput(); self._spec_clear_g.on_submit = self._on_spec_field_changed
        self._spec_clear_b = TextInput(); self._spec_clear_b.on_submit = self._on_spec_field_changed
        self._spec_clear_a = TextInput(); self._spec_clear_a.on_submit = self._on_spec_field_changed
        self._spec_clear_depth_check = Checkbox()
        self._spec_clear_depth_check.on_changed = self._on_spec_field_changed_check
        self._spec_clear_depth = TextInput(); self._spec_clear_depth.on_submit = self._on_spec_field_changed

        self._spec_editor.add_child(self._two_col_row("Resource:", self._spec_resource))
        self._spec_editor.add_child(self._two_col_row("Samples:", self._spec_samples))
        self._spec_editor.add_child(self._two_col_row("Format:", self._spec_format))
        self._spec_editor.add_child(self._two_col_row("Clear color:", self._spec_clear_color))

        color_vals_row = HStack()
        color_vals_row.spacing = 4
        for w in (self._spec_clear_r, self._spec_clear_g, self._spec_clear_b, self._spec_clear_a):
            w.preferred_width = px(56)
            color_vals_row.add_child(w)
        color_vals_spacer = Label()
        color_vals_spacer.stretch = True
        color_vals_row.add_child(color_vals_spacer)
        self._spec_editor.add_child(color_vals_row)

        self._spec_editor.add_child(self._two_col_row("Clear depth:", self._spec_clear_depth_check))
        self._spec_editor.add_child(self._two_col_row("", self._spec_clear_depth))

        self._empty = Label()
        self._empty.text = "No pipeline selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

    def _two_col_row(self, label_text: str, widget) -> HStack:
        row = HStack()
        row.spacing = 6
        label = Label()
        label.text = label_text
        label.preferred_width = px(96)
        row.add_child(label)
        row.add_child(widget)
        spacer = Label()
        spacer.stretch = True
        row.add_child(spacer)
        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pipeline(self, pipeline, subtitle: str = "", source_path: str | None = None) -> None:
        self._pipeline = pipeline
        self._subtitle.text = subtitle
        self._source_path = source_path
        self._rebuild_all()

    def load_pipeline_file(self, file_path: str) -> None:
        path = Path(file_path)
        name = path.stem
        asset = self._rm.get_pipeline_asset(name)
        pipeline = asset.data if asset is not None else None
        self.set_pipeline(pipeline, f"File: {file_path}", file_path)

    # ------------------------------------------------------------------
    # Rebuild
    # ------------------------------------------------------------------

    def _set_visible_state(self, has_pipeline: bool) -> None:
        self._passes_list.visible = has_pipeline
        self._pass_add.visible = has_pipeline
        self._pass_remove.visible = has_pipeline
        self._pass_up.visible = has_pipeline
        self._pass_down.visible = has_pipeline
        self._pass_name.visible = has_pipeline
        self._pass_enabled.visible = has_pipeline
        self._pass_fields.visible = has_pipeline

        effects_visible = has_pipeline and self._selected_postprocess is not None
        self._effects_title.visible = effects_visible
        self._effects_list.visible = effects_visible
        self._effect_add.visible = effects_visible
        self._effect_remove.visible = effects_visible
        self._effect_up.visible = effects_visible
        self._effect_down.visible = effects_visible
        self._effect_name.visible = effects_visible
        self._effect_fields.visible = effects_visible

        self._specs_list.visible = has_pipeline
        self._spec_add.visible = has_pipeline
        self._spec_remove.visible = has_pipeline
        self._spec_editor.visible = has_pipeline and self._selected_spec_index >= 0

        self._empty.visible = not has_pipeline

    def _rebuild_all(self) -> None:
        self._updating = True
        try:
            self._selected_postprocess = None
            self._selected_spec_index = -1

            self._passes_list.set_items([])
            self._effects_list.set_items([])
            self._specs_list.set_items([])
            self._pass_fields.set_target(None)
            self._effect_fields.set_target(None)
            self._pass_name.text = ""
            self._effect_name.text = ""
            self._pass_enabled.checked = False

            if self._pipeline is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            self._rebuild_passes()
            self._rebuild_specs()
            self._update_buttons()
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _rebuild_passes(self) -> None:
        if self._pipeline is None:
            self._passes_list.set_items([])
            return
        items = []
        for p in self._pipeline.passes:
            mark = "[x]" if p.enabled else "[ ]"
            items.append({"text": f"{mark} {p.pass_name}", "subtitle": p.__class__.__name__})
        self._passes_list.set_items(items)

    def _rebuild_effects(self) -> None:
        if self._selected_postprocess is None:
            self._effects_list.set_items([])
            return
        items = []
        for eff in self._selected_postprocess.effects:
            name = eff.name if hasattr(eff, "name") else eff.__class__.__name__
            items.append({"text": name, "subtitle": eff.__class__.__name__})
        self._effects_list.set_items(items)

    def _rebuild_specs(self) -> None:
        if self._pipeline is None:
            self._specs_list.set_items([])
            return
        items = []
        for spec in self._pipeline.pipeline_specs:
            subtitle = f"samples={spec.samples}, format={spec.format or 'rgba8'}"
            items.append({"text": spec.resource, "subtitle": subtitle})
        self._specs_list.set_items(items)

    # ------------------------------------------------------------------
    # Passes
    # ------------------------------------------------------------------

    def _current_pass_index(self) -> int:
        return self._passes_list.selected_index

    def _current_pass(self):
        if self._pipeline is None:
            return None
        idx = self._current_pass_index()
        if idx < 0 or idx >= len(self._pipeline.passes):
            return None
        return self._pipeline.passes[idx]

    def _on_pass_selected(self, index: int, _item: dict) -> None:
        if self._updating:
            return
        p = self._current_pass()
        self._updating = True
        try:
            if p is None:
                self._pass_name.text = ""
                self._pass_enabled.checked = False
                self._pass_fields.set_target(None)
                self._selected_postprocess = None
                self._rebuild_effects()
                self._effect_fields.set_target(None)
                self._effect_name.text = ""
            else:
                self._pass_name.text = p.pass_name or ""
                self._pass_enabled.checked = bool(p.enabled)
                self._pass_fields.set_target(p)

                from termin.visualization.render.postprocess import PostProcessPass
                if isinstance(p, PostProcessPass):
                    self._selected_postprocess = p
                    self._rebuild_effects()
                else:
                    self._selected_postprocess = None
                    self._rebuild_effects()
                    self._effect_fields.set_target(None)
                    self._effect_name.text = ""
        finally:
            self._updating = False
            self._set_visible_state(self._pipeline is not None)
            self._update_buttons()
            if self._ui is not None:
                self._ui.request_layout()

    def _on_pass_enabled_changed(self, checked: bool) -> None:
        if self._updating:
            return
        p = self._current_pass()
        if p is None:
            return
        p.enabled = bool(checked)
        self._rebuild_passes()
        self._passes_list.selected_index = self._current_pass_index()
        self._emit_changed()

    def _on_pass_name_submitted(self, text: str) -> None:
        if self._updating:
            return
        p = self._current_pass()
        if p is None:
            return
        new_name = text.strip()
        if not new_name or new_name == p.pass_name:
            return
        p.pass_name = new_name
        self._rebuild_passes()
        self._emit_changed()

    def _on_pass_field_changed(self, _key, _old, _new) -> None:
        self._emit_changed()

    def _on_add_pass(self) -> None:
        if self._pipeline is None or self._ui is None:
            return
        names = self._rm.list_frame_pass_names()
        if not names:
            MessageBox.warning(self._ui, "No Passes", "No FramePass types registered.")
            return

        menu = Menu()
        menu.items = [MenuItem(name, on_click=lambda n=name: self._create_pass_of_type(n)) for name in names]
        x = self._pass_add.x + self._pass_add.width
        y = self._pass_add.y
        menu.show(self._ui, x, y)

    def _create_pass_of_type(self, pass_type: str) -> None:
        if self._pipeline is None or self._ui is None:
            return

        pass_cls = self._rm.get_frame_pass(pass_type)
        if pass_cls is None:
            log.error(f"[PipelineInspectorTcgui] frame pass class not found: {pass_type}")
            return

        def _on_name(name: str | None) -> None:
            if name is None:
                return
            pass_name = name.strip() or pass_type
            try:
                new_pass = pass_cls(pass_name=pass_name)
            except Exception as e:
                log.error(f"[PipelineInspectorTcgui] failed to create pass {pass_type}: {e}")
                MessageBox.error(self._ui, "Create Pass Failed", str(e))
                return

            idx = self._current_pass_index()
            if idx < 0:
                self._pipeline.add_pass(new_pass)
                idx = len(self._pipeline.passes) - 1
            else:
                self._pipeline.insert_pass(idx + 1, new_pass)
                idx += 1

            self._rebuild_passes()
            self._passes_list.selected_index = idx
            self._on_pass_selected(idx, {})
            self._emit_changed()

        show_input_dialog(
            self._ui,
            title="Add Pass",
            message="Pass name:",
            default=pass_type,
            on_result=_on_name,
        )

    def _on_remove_pass(self) -> None:
        if self._pipeline is None or self._ui is None:
            return
        p = self._current_pass()
        if p is None:
            return

        def _on_result(btn: str) -> None:
            if btn != "Yes":
                return
            idx = self._current_pass_index()
            self._pipeline.remove_pass(p)
            self._rebuild_passes()
            if self._pipeline.passes:
                idx = max(0, min(idx, len(self._pipeline.passes) - 1))
                self._passes_list.selected_index = idx
                self._on_pass_selected(idx, {})
            else:
                self._on_pass_selected(-1, {})
            self._emit_changed()

        MessageBox.question(
            self._ui,
            "Remove Pass",
            f"Remove pass '{p.pass_name}'?",
            on_result=_on_result,
        )

    def _on_move_pass_up(self) -> None:
        if self._pipeline is None:
            return
        idx = self._current_pass_index()
        if idx <= 0:
            return
        self._pipeline.move_pass(idx, idx - 1)
        self._rebuild_passes()
        self._passes_list.selected_index = idx - 1
        self._on_pass_selected(idx - 1, {})
        self._emit_changed()

    def _on_move_pass_down(self) -> None:
        if self._pipeline is None:
            return
        idx = self._current_pass_index()
        if idx < 0 or idx >= len(self._pipeline.passes) - 1:
            return
        self._pipeline.move_pass(idx, idx + 1)
        self._rebuild_passes()
        self._passes_list.selected_index = idx + 1
        self._on_pass_selected(idx + 1, {})
        self._emit_changed()

    # ------------------------------------------------------------------
    # Effects
    # ------------------------------------------------------------------

    def _current_effect_index(self) -> int:
        return self._effects_list.selected_index

    def _current_effect(self):
        if self._selected_postprocess is None:
            return None
        idx = self._current_effect_index()
        if idx < 0 or idx >= len(self._selected_postprocess.effects):
            return None
        return self._selected_postprocess.effects[idx]

    def _on_effect_selected(self, _index: int, _item: dict) -> None:
        if self._updating:
            return
        eff = self._current_effect()
        if eff is None:
            self._effect_fields.set_target(None)
            self._effect_name.text = ""
        else:
            self._effect_fields.set_target(eff)
            self._effect_name.text = eff.name if hasattr(eff, "name") else ""
        self._update_buttons()

    def _on_add_effect(self) -> None:
        if self._selected_postprocess is None or self._ui is None:
            return
        names = self._rm.list_post_effect_names()
        if not names:
            MessageBox.warning(self._ui, "No Effects", "No PostEffect types registered.")
            return

        menu = Menu()
        menu.items = [MenuItem(name, on_click=lambda n=name: self._create_effect_of_type(n)) for name in names]
        x = self._effect_add.x + self._effect_add.width
        y = self._effect_add.y
        menu.show(self._ui, x, y)

    def _create_effect_of_type(self, effect_type: str) -> None:
        if self._selected_postprocess is None:
            return
        effect_cls = self._rm.get_post_effect(effect_type)
        if effect_cls is None:
            log.error(f"[PipelineInspectorTcgui] post effect class not found: {effect_type}")
            return
        try:
            effect = effect_cls()
            self._selected_postprocess.effects.append(effect)
        except Exception as e:
            log.error(f"[PipelineInspectorTcgui] failed to create effect {effect_type}: {e}")
            if self._ui is not None:
                MessageBox.error(self._ui, "Create Effect Failed", str(e))
            return

        self._rebuild_effects()
        idx = len(self._selected_postprocess.effects) - 1
        self._effects_list.selected_index = idx
        self._on_effect_selected(idx, {})
        self._emit_changed()

    def _on_remove_effect(self) -> None:
        if self._selected_postprocess is None or self._ui is None:
            return
        idx = self._current_effect_index()
        eff = self._current_effect()
        if eff is None:
            return
        name = eff.name if hasattr(eff, "name") else eff.__class__.__name__

        def _on_result(btn: str) -> None:
            if btn != "Yes":
                return
            del self._selected_postprocess.effects[idx]
            self._rebuild_effects()
            if self._selected_postprocess.effects:
                idx2 = max(0, min(idx, len(self._selected_postprocess.effects) - 1))
                self._effects_list.selected_index = idx2
                self._on_effect_selected(idx2, {})
            else:
                self._on_effect_selected(-1, {})
            self._emit_changed()

        MessageBox.question(
            self._ui,
            "Remove Effect",
            f"Remove effect '{name}'?",
            on_result=_on_result,
        )

    def _on_move_effect_up(self) -> None:
        if self._selected_postprocess is None:
            return
        idx = self._current_effect_index()
        if idx <= 0:
            return
        effects = self._selected_postprocess.effects
        effects[idx], effects[idx - 1] = effects[idx - 1], effects[idx]
        self._rebuild_effects()
        self._effects_list.selected_index = idx - 1
        self._on_effect_selected(idx - 1, {})
        self._emit_changed()

    def _on_move_effect_down(self) -> None:
        if self._selected_postprocess is None:
            return
        idx = self._current_effect_index()
        effects = self._selected_postprocess.effects
        if idx < 0 or idx >= len(effects) - 1:
            return
        effects[idx], effects[idx + 1] = effects[idx + 1], effects[idx]
        self._rebuild_effects()
        self._effects_list.selected_index = idx + 1
        self._on_effect_selected(idx + 1, {})
        self._emit_changed()

    def _on_effect_name_submitted(self, text: str) -> None:
        eff = self._current_effect()
        if eff is None or not hasattr(eff, "name"):
            return
        new_name = text.strip()
        if not new_name or new_name == eff.name:
            return
        eff.name = new_name
        self._rebuild_effects()
        self._emit_changed()

    def _on_effect_field_changed(self, _key, _old, _new) -> None:
        self._emit_changed()

    # ------------------------------------------------------------------
    # Resource specs
    # ------------------------------------------------------------------

    def _current_spec(self):
        if self._pipeline is None:
            return None
        idx = self._selected_spec_index
        if idx < 0 or idx >= len(self._pipeline.pipeline_specs):
            return None
        return self._pipeline.pipeline_specs[idx]

    def _on_spec_selected(self, index: int, _item: dict) -> None:
        self._selected_spec_index = index
        self._sync_spec_editor_from_model()
        self._set_visible_state(self._pipeline is not None)
        self._update_buttons()
        if self._ui is not None:
            self._ui.request_layout()

    def _on_add_spec(self) -> None:
        if self._pipeline is None or self._ui is None:
            return

        def _on_name(text: str | None) -> None:
            if text is None:
                return
            name = text.strip()
            if not name:
                return
            for spec in self._pipeline.pipeline_specs:
                if spec.resource == name:
                    MessageBox.warning(self._ui, "Duplicate Resource", f"Resource '{name}' already exists.")
                    return
            from termin.visualization.render.framegraph.resource_spec import ResourceSpec
            self._pipeline.pipeline_specs.append(ResourceSpec(resource=name, resource_type="fbo"))
            self._rebuild_specs()
            idx = len(self._pipeline.pipeline_specs) - 1
            self._specs_list.selected_index = idx
            self._on_spec_selected(idx, {})
            self._emit_changed()

        show_input_dialog(
            self._ui,
            title="Add Resource Spec",
            message="Resource name:",
            default="new_resource",
            on_result=_on_name,
        )

    def _on_remove_spec(self) -> None:
        if self._pipeline is None or self._ui is None:
            return
        idx = self._selected_spec_index
        spec = self._current_spec()
        if spec is None:
            return

        def _on_result(btn: str) -> None:
            if btn != "Yes":
                return
            del self._pipeline.pipeline_specs[idx]
            self._rebuild_specs()
            if self._pipeline.pipeline_specs:
                idx2 = max(0, min(idx, len(self._pipeline.pipeline_specs) - 1))
                self._specs_list.selected_index = idx2
                self._on_spec_selected(idx2, {})
            else:
                self._selected_spec_index = -1
                self._sync_spec_editor_from_model()
                self._set_visible_state(True)
            self._emit_changed()

        MessageBox.question(
            self._ui,
            "Remove Resource Spec",
            f"Remove resource spec '{spec.resource}'?",
            on_result=_on_result,
        )

    def _sync_spec_editor_from_model(self) -> None:
        spec = self._current_spec()
        self._updating_spec = True
        try:
            if spec is None:
                self._spec_resource.text = ""
                self._spec_samples.selected_index = 0
                self._spec_format.selected_index = 0
                self._spec_clear_color.checked = False
                self._spec_clear_r.text = "0.0"
                self._spec_clear_g.text = "0.0"
                self._spec_clear_b.text = "0.0"
                self._spec_clear_a.text = "1.0"
                self._spec_clear_depth_check.checked = False
                self._spec_clear_depth.text = "1.0"
                return

            self._spec_resource.text = spec.resource or ""

            samples = int(spec.samples)
            sample_idx = 0
            if samples == 2:
                sample_idx = 1
            elif samples == 4:
                sample_idx = 2
            elif samples == 8:
                sample_idx = 3
            self._spec_samples.selected_index = sample_idx

            fmt = spec.format or "rgba8"
            fmt_idx = 0
            for i in range(self._spec_format.item_count):
                if self._spec_format.item_text(i) == fmt:
                    fmt_idx = i
                    break
            self._spec_format.selected_index = fmt_idx

            if spec.clear_color is None:
                self._spec_clear_color.checked = False
                self._spec_clear_r.text = "0.0"
                self._spec_clear_g.text = "0.0"
                self._spec_clear_b.text = "0.0"
                self._spec_clear_a.text = "1.0"
            else:
                self._spec_clear_color.checked = True
                self._spec_clear_r.text = str(spec.clear_color[0])
                self._spec_clear_g.text = str(spec.clear_color[1])
                self._spec_clear_b.text = str(spec.clear_color[2])
                self._spec_clear_a.text = str(spec.clear_color[3])

            if spec.clear_depth is None:
                self._spec_clear_depth_check.checked = False
                self._spec_clear_depth.text = "1.0"
            else:
                self._spec_clear_depth_check.checked = True
                self._spec_clear_depth.text = str(spec.clear_depth)
        finally:
            self._updating_spec = False

    def _on_spec_field_changed_combo(self, _index: int, _text: str) -> None:
        self._on_spec_field_changed("")

    def _on_spec_field_changed_check(self, _checked: bool) -> None:
        self._on_spec_field_changed("")

    def _on_spec_field_changed(self, _text: str) -> None:
        if self._updating_spec:
            return
        spec = self._current_spec()
        if spec is None:
            return

        # Name
        new_name = self._spec_resource.text.strip()
        if new_name and new_name != spec.resource:
            duplicate = False
            if self._pipeline is not None:
                for i, s in enumerate(self._pipeline.pipeline_specs):
                    if i != self._selected_spec_index and s.resource == new_name:
                        duplicate = True
                        break
            if duplicate:
                self._spec_resource.text = spec.resource
            else:
                spec.resource = new_name

        # Samples and format
        samples_map = [1, 2, 4, 8]
        sidx = self._spec_samples.selected_index
        if 0 <= sidx < len(samples_map):
            spec.samples = samples_map[sidx]
        spec.format = self._spec_format.selected_text

        # Clear color
        if self._spec_clear_color.checked:
            try:
                spec.clear_color = (
                    float(self._spec_clear_r.text),
                    float(self._spec_clear_g.text),
                    float(self._spec_clear_b.text),
                    float(self._spec_clear_a.text),
                )
            except ValueError:
                pass
        else:
            try:
                spec.clear_color = None
            except TypeError:
                pass

        # Clear depth
        if self._spec_clear_depth_check.checked:
            try:
                spec.clear_depth = float(self._spec_clear_depth.text)
            except ValueError:
                pass
        else:
            try:
                spec.clear_depth = None
            except TypeError:
                pass

        self._rebuild_specs()
        if self._selected_spec_index >= 0:
            self._specs_list.selected_index = self._selected_spec_index
        self._emit_changed()

    # ------------------------------------------------------------------
    # State / signals
    # ------------------------------------------------------------------

    def _update_buttons(self) -> None:
        has_pipeline = self._pipeline is not None
        pass_idx = self._current_pass_index()
        pass_count = len(self._pipeline.passes) if has_pipeline else 0

        self._pass_add.enabled = has_pipeline
        self._pass_remove.enabled = has_pipeline and pass_idx >= 0
        self._pass_up.enabled = has_pipeline and pass_idx > 0
        self._pass_down.enabled = has_pipeline and 0 <= pass_idx < pass_count - 1

        eff_idx = self._current_effect_index()
        eff_count = len(self._selected_postprocess.effects) if self._selected_postprocess is not None else 0
        has_effects = self._selected_postprocess is not None

        self._effect_add.enabled = has_effects
        self._effect_remove.enabled = has_effects and eff_idx >= 0
        self._effect_up.enabled = has_effects and eff_idx > 0
        self._effect_down.enabled = has_effects and 0 <= eff_idx < eff_count - 1

        spec_idx = self._selected_spec_index
        spec_count = len(self._pipeline.pipeline_specs) if has_pipeline else 0
        self._spec_add.enabled = has_pipeline
        self._spec_remove.enabled = has_pipeline and 0 <= spec_idx < spec_count

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
