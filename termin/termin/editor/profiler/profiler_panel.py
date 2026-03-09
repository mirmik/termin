"""
Profiler panel for the editor.

Dock-виджет с графиком frame time и таблицей секций.
Включается через Debug → Profiler (F7).
"""

from __future__ import annotations

from typing import Dict

from PyQt6 import QtWidgets, QtCore, QtGui

from termin.core.profiler import Profiler, SectionStats
from termin.editor.profiler.frame_time_graph import FrameTimeGraph


class ProfilerPanel(QtWidgets.QDockWidget):
    """
    Dock-виджет профайлера.

    Показывает:
    - График frame time
    - FPS и общее время кадра
    - Иерархическую таблицу секций с временами
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Profiler", parent)
        self.setObjectName("ProfilerPanel")

        self._profiler = Profiler.instance()
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._update_display)

        # Кэш для оптимизации обновления таблицы
        self._last_sections: Dict[str, SectionStats] = {}
        self._update_table_enabled = True
        self._ema_sections: Dict[str, float] = {}
        self._ema_children: Dict[str, float] = {}
        self._ema_calls: Dict[str, int] = {}
        self._ema_total: float | None = None
        self._ema_alpha: float = 0.1  # f_new = f_prev*(1-α) + f_curr*α

        self._build_ui()

    def _build_ui(self) -> None:
        """Создаёт UI панели."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)

        self._enable_check = QtWidgets.QCheckBox("Enable")
        self._enable_check.setToolTip("Enable/disable profiling (affects performance when enabled)")
        self._enable_check.toggled.connect(self._on_enable_toggled)
        toolbar.addWidget(self._enable_check)

        self._detailed_check = QtWidgets.QCheckBox("Detailed")
        self._detailed_check.setToolTip("Enable detailed rendering profiling (shows Collect/Sort/UBO/DrawCalls sections)")
        self._detailed_check.toggled.connect(self._on_detailed_toggled)
        toolbar.addWidget(self._detailed_check)

        toolbar.addSpacing(16)

        # Clear button
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.setToolTip("Clear profiling history")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()

        # FPS label
        self._fps_label = QtWidgets.QLabel("-- FPS")
        self._fps_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._fps_label.setToolTip("Frames per second (averaged over 60 frames)")
        toolbar.addWidget(self._fps_label)

        layout.addLayout(toolbar)

        # Graph
        self._graph = FrameTimeGraph()
        self._graph.setMinimumHeight(80)
        self._graph.setMaximumHeight(100)
        layout.addWidget(self._graph)

        # Table
        self._table = QtWidgets.QTreeWidget()
        self._table.setHeaderLabels(["Section", "Time (ms)", "%", "Cov", "Count"])
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 50)
        self._table.setColumnWidth(3, 50)
        self._table.setColumnWidth(4, 50)
        self._table.setAlternatingRowColors(True)
        self._table.setRootIsDecorated(True)
        self._table.setIndentation(16)

        # Стиль для progress bar в ячейках
        self._table.setStyleSheet("""
            QTreeWidget {
                background-color: #2d2d2d;
                alternate-background-color: #323232;
            }
            QTreeWidget::item {
                padding: 2px;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                padding: 4px;
                border: none;
            }
        """)

        layout.addWidget(self._table, 1)

        self.setWidget(widget)

        # Минимальный размер
        self.setMinimumWidth(300)
        self.setMinimumHeight(200)

    def _on_enable_toggled(self, checked: bool) -> None:
        """Обработчик включения/выключения профайлера."""
        self._profiler.enabled = checked

        if checked:
            self._update_timer.start(100)  # 10 Hz update
        else:
            self._update_timer.stop()
            self._table.clear()
            self._graph.clear()
            self._fps_label.setText("-- FPS")
            self._last_sections.clear()
            self._ema_sections.clear()
            self._ema_children.clear()
            self._ema_calls.clear()
            self._ema_total = None

    def _on_detailed_toggled(self, checked: bool) -> None:
        """Обработчик включения/выключения детального профилирования рендеринга."""
        self._profiler.detailed_rendering = checked

    def _on_clear_clicked(self) -> None:
        """Обработчик кнопки Clear."""
        self._profiler.clear_history()
        self._graph.clear()
        self._table.clear()
        self._last_sections.clear()
        self._ema_sections.clear()
        self._ema_children.clear()
        self._ema_calls.clear()
        self._ema_total = None

    def _update_display(self) -> None:
        """Обновляет отображение данных профайлера."""
        if not self._profiler.enabled:
            return

        frame = self._get_last_frame()
        if frame is None:
            return

        detailed = self._collect_sections_from_frame(frame)
        if not detailed:
            return

        # Считаем общее время (только root секции)
        total = sum(stats.cpu_ms for k, stats in detailed.items() if "/" not in k)
        total_ema = self._update_total_ema(total)
        detailed_ema = self._update_sections_ema(detailed)

        # FPS
        if total_ema > 0:
            fps = 1000.0 / total_ema
            self._fps_label.setText(f"{fps:.0f} FPS ({total_ema:.1f}ms)")
        else:
            self._fps_label.setText("-- FPS")

        # Graph
        self._graph.add_frame(total_ema)

        # Table - обновляем только если данные изменились значительно
        if self._update_table_enabled and self._should_update_table(detailed_ema):
            self._rebuild_table(detailed_ema, total_ema)
            self._last_sections = detailed_ema.copy()

    def _get_last_frame(self):
        """Возвращает последний кадр профайлера без конвертации всей истории."""
        tc = self._profiler._tc
        count = tc.history_count
        if count <= 0:
            return None
        return tc.history_at(count - 1)

    def _collect_sections_from_frame(self, frame) -> Dict[str, SectionStats]:
        """Собирает секции из одного кадра в формате path -> SectionStats."""
        sections = frame.sections
        if not sections:
            return {}

        names = [s.name for s in sections]
        parents = [s.parent_index for s in sections]
        path_cache: Dict[int, str] = {}

        def make_path(idx: int) -> str:
            cached = path_cache.get(idx)
            if cached is not None:
                return cached
            parent_idx = parents[idx]
            if parent_idx < 0:
                path = names[idx]
            else:
                path = f"{make_path(parent_idx)}/{names[idx]}"
            path_cache[idx] = path
            return path

        result: Dict[str, SectionStats] = {}
        for i, s in enumerate(sections):
            path = make_path(i)
            result[path] = SectionStats(cpu_ms=s.cpu_ms, children_ms=s.children_ms, call_count=s.call_count)
        return result

    def _update_total_ema(self, total: float) -> float:
        if self._ema_total is None:
            self._ema_total = total
        else:
            self._ema_total = self._ema_total * (1.0 - self._ema_alpha) + total * self._ema_alpha
        return self._ema_total

    def _update_sections_ema(self, detailed: Dict[str, SectionStats]) -> Dict[str, SectionStats]:
        alpha = self._ema_alpha

        for key, stats in detailed.items():
            prev = self._ema_sections.get(key)
            prev_children = self._ema_children.get(key)
            if prev is None:
                self._ema_sections[key] = stats.cpu_ms
                self._ema_children[key] = stats.children_ms
            else:
                self._ema_sections[key] = prev * (1.0 - alpha) + stats.cpu_ms * alpha
                self._ema_children[key] = (prev_children or 0.0) * (1.0 - alpha) + stats.children_ms * alpha
            self._ema_calls[key] = stats.call_count

        # Плавно затухаем секции, которые пропали
        for key in list(self._ema_sections.keys()):
            if key in detailed:
                continue
            self._ema_sections[key] *= (1.0 - alpha)
            self._ema_children[key] = self._ema_children.get(key, 0.0) * (1.0 - alpha)
            if self._ema_sections[key] < 0.01:
                self._ema_sections.pop(key, None)
                self._ema_children.pop(key, None)
                self._ema_calls.pop(key, None)

        return {
            key: SectionStats(
                cpu_ms=self._ema_sections[key],
                children_ms=self._ema_children.get(key, 0.0),
                call_count=self._ema_calls.get(key, 0)
            )
            for key in self._ema_sections
        }

    def _should_update_table(self, detailed: Dict[str, SectionStats]) -> bool:
        """Проверяет, нужно ли обновлять таблицу."""
        if len(detailed) != len(self._last_sections):
            return True

        # Проверяем изменение значений более чем на 5%
        for key, stats in detailed.items():
            old_stats = self._last_sections.get(key)
            if old_stats is None:
                if stats.cpu_ms > 0.1:  # Новая секция с заметным временем
                    return True
            elif old_stats.cpu_ms > 0 and abs(stats.cpu_ms - old_stats.cpu_ms) / old_stats.cpu_ms > 0.05:
                return True

        return False

    def _rebuild_table(self, detailed: Dict[str, SectionStats], total: float) -> None:
        """Перестраивает таблицу секций."""
        # Сохраняем состояние раскрытия
        expanded_items = self._get_expanded_items()

        self._table.clear()

        # Группируем по иерархии
        root_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}

        # Сортируем: сначала по глубине (меньше = раньше), потом по времени (больше = раньше)
        sorted_sections = sorted(
            detailed.items(),
            key=lambda x: (x[0].count("/"), -x[1].cpu_ms)
        )

        for path, stats in sorted_sections:
            parts = path.split("/")
            pct = (stats.cpu_ms / total * 100) if total > 0 else 0

            # Coverage: какая часть времени секции покрыта подсекциями
            coverage = (stats.children_ms / stats.cpu_ms * 100) if stats.cpu_ms > 0 else 0

            # Создаём item
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, parts[-1])
            item.setText(1, f"{stats.cpu_ms:.2f}")
            item.setText(2, f"{pct:.1f}%")
            # Показываем coverage только если есть подсекции
            item.setText(3, f"{coverage:.0f}%" if stats.children_ms > 0 else "")
            # Показываем count только если > 1
            item.setText(4, str(stats.call_count) if stats.call_count > 1 else "")
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, path)

            # Выравнивание чисел вправо
            item.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(3, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(4, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

            # Цвет в зависимости от процента
            if pct > 50:
                item.setForeground(1, QtGui.QColor(255, 100, 100))
            elif pct > 25:
                item.setForeground(1, QtGui.QColor(255, 200, 100))

            # Цвет coverage: красный если низкий (много непрофилированного времени)
            if stats.children_ms > 0:
                if coverage < 50:
                    item.setForeground(3, QtGui.QColor(255, 100, 100))
                elif coverage < 80:
                    item.setForeground(3, QtGui.QColor(255, 200, 100))

            if len(parts) == 1:
                # Root level
                self._table.addTopLevelItem(item)
                root_items[parts[0]] = item
            else:
                # Nested - ищем родителя
                parent_path = "/".join(parts[:-1])
                parent = root_items.get(parent_path)
                if parent:
                    parent.addChild(item)
                    root_items[path] = item
                else:
                    # Родитель не найден - добавляем в root
                    self._table.addTopLevelItem(item)
                    root_items[path] = item

        # Восстанавливаем состояние раскрытия
        self._restore_expanded_items(expanded_items)

    def _get_expanded_items(self) -> set:
        """Возвращает множество путей раскрытых элементов."""
        expanded = set()

        def collect(item: QtWidgets.QTreeWidgetItem) -> None:
            if item.isExpanded():
                path = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if path:
                    expanded.add(path)
            for i in range(item.childCount()):
                collect(item.child(i))

        for i in range(self._table.topLevelItemCount()):
            collect(self._table.topLevelItem(i))

        return expanded

    def _restore_expanded_items(self, expanded: set) -> None:
        """Восстанавливает состояние раскрытия элементов."""
        def restore(item: QtWidgets.QTreeWidgetItem) -> None:
            path = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if path in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                restore(item.child(i))

        # По умолчанию раскрываем все root элементы
        for i in range(self._table.topLevelItemCount()):
            item = self._table.topLevelItem(i)
            if not expanded:  # Если нет сохранённого состояния
                item.setExpanded(True)
            else:
                restore(item)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """При показе панели синхронизируем состояние checkbox."""
        super().showEvent(event)
        self._enable_check.setChecked(self._profiler.enabled)
        self._detailed_check.setChecked(self._profiler.detailed_rendering)
        if self._profiler.enabled:
            self._update_timer.start(100)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """При скрытии панели останавливаем таймер."""
        super().hideEvent(event)
        self._update_timer.stop()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """При закрытии панели останавливаем таймер."""
        self._update_timer.stop()
        super().closeEvent(event)
