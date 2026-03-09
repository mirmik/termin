from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class EditorViewportToolbarHandles:
    def __init__(
        self,
        viewport_toolbar: QWidget,
        play_button: QPushButton,
        pause_button: QPushButton,
        prefab_toolbar: QWidget,
        prefab_toolbar_label: QLabel,
    ) -> None:
        self.viewport_toolbar = viewport_toolbar
        self.play_button = play_button
        self.pause_button = pause_button
        self.prefab_toolbar = prefab_toolbar
        self.prefab_toolbar_label = prefab_toolbar_label


class EditorUIBuilder:
    @staticmethod
    def fix_splitters(top_splitter, vertical_splitter) -> None:
        top_splitter.setOpaqueResize(False)
        vertical_splitter.setOpaqueResize(False)

        top_splitter.setCollapsible(0, False)
        top_splitter.setCollapsible(1, False)
        top_splitter.setCollapsible(2, False)

        vertical_splitter.setCollapsible(0, False)
        vertical_splitter.setCollapsible(1, False)

        top_splitter.setSizes([300, 1000, 300])
        vertical_splitter.setSizes([600, 200])

    @staticmethod
    def build_viewport_toolbar(
        center_tab_widget,
        top_splitter,
        on_toggle_game_mode,
        on_toggle_pause,
        on_save_prefab,
        on_exit_prefab,
    ) -> EditorViewportToolbarHandles:
        """
        Создаёт панель инструментов над centerTabWidget с кнопкой Play в центре.
        """
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet("background-color: #3c3c3c;")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Левый спейсер для центрирования кнопки
        layout.addStretch(1)

        # Кнопка Play/Stop
        play_btn = QPushButton("Play")
        play_btn.setFixedSize(60, 24)
        play_btn.setCheckable(True)
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:checked {
                background-color: #4a90d9;
                border-color: #5aa0e9;
            }
            QPushButton:checked:hover {
                background-color: #5aa0e9;
            }
        """)
        play_btn.clicked.connect(on_toggle_game_mode)
        layout.addWidget(play_btn)

        # Кнопка Pause (видна только в game mode)
        pause_btn = QPushButton("Pause")
        pause_btn.setFixedSize(60, 24)
        pause_btn.setCheckable(True)
        pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:checked {
                background-color: #d9a04a;
                border-color: #e9b05a;
            }
            QPushButton:checked:hover {
                background-color: #e9b05a;
            }
        """)
        pause_btn.clicked.connect(on_toggle_pause)
        pause_btn.setVisible(False)  # Hidden until game mode starts
        layout.addWidget(pause_btn)

        # Правый спейсер для центрирования кнопки
        layout.addStretch(1)

        # --- Prefab toolbar (скрытый по умолчанию) ---
        prefab_toolbar = QWidget()
        prefab_toolbar.setFixedHeight(28)
        prefab_toolbar.setStyleSheet("background-color: #4a7c59;")  # Зелёный оттенок
        prefab_toolbar.setVisible(False)

        prefab_layout = QHBoxLayout(prefab_toolbar)
        prefab_layout.setContentsMargins(8, 2, 8, 2)
        prefab_layout.setSpacing(8)

        # Иконка и название префаба
        prefab_label = QLabel("Editing Prefab: ")
        prefab_label.setStyleSheet("color: white; font-weight: bold;")
        prefab_layout.addWidget(prefab_label)

        prefab_layout.addStretch(1)

        # Кнопка Save
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(70, 22)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a9a6a;
                color: white;
                border: 1px solid #6aaa7a;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6aaa7a;
            }
        """)
        save_btn.clicked.connect(on_save_prefab)
        prefab_layout.addWidget(save_btn)

        # Кнопка Exit
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedSize(70, 22)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6a6a6a;
                color: white;
                border: 1px solid #7a7a7a;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7a7a7a;
            }
        """)
        exit_btn.clicked.connect(on_exit_prefab)
        prefab_layout.addWidget(exit_btn)

        # Создаём контейнер для toolbar + prefab_toolbar + centerTabWidget
        center_container = QWidget()
        container_layout = QVBoxLayout(center_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Добавляем toolbars в контейнер
        container_layout.addWidget(toolbar)
        container_layout.addWidget(prefab_toolbar)

        # Перемещаем centerTabWidget в контейнер
        # Сначала получаем индекс centerTabWidget в topSplitter
        splitter_index = top_splitter.indexOf(center_tab_widget)

        # Убираем centerTabWidget из splitter (setParent(None))
        center_tab_widget.setParent(None)

        # Добавляем centerTabWidget в контейнер
        container_layout.addWidget(center_tab_widget)

        # Вставляем контейнер в splitter на место centerTabWidget
        top_splitter.insertWidget(splitter_index, center_container)

        # Переустанавливаем размеры сплиттера после перемещения виджетов
        top_splitter.setSizes([300, 1000, 300])

        return EditorViewportToolbarHandles(
            viewport_toolbar=toolbar,
            play_button=play_btn,
            pause_button=pause_btn,
            prefab_toolbar=prefab_toolbar,
            prefab_toolbar_label=prefab_label,
        )
