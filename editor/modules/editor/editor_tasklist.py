"""Task palette for the program editor."""

from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .editor_tasks import EditorTasks
from .special_tasks import SpecialTasks


class EditorTaskList(QWidget):
    """Show all standard and special tasks as addable buttons."""

    def __init__(self, add_task_callback, parent=None):
        super().__init__(parent)
        self.add_task_callback = add_task_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Tasks</b>"))

        for task_name in EditorTasks.get_all_task_names():
            btn = QPushButton(task_name)
            btn.clicked.connect(lambda _, name=task_name: self.add_task_callback(name))
            layout.addWidget(btn)

        layout.addWidget(QLabel("<b>Special Tasks</b>"))

        for task_name in SpecialTasks.get_all_task_names():
            btn = QPushButton(task_name)
            btn.clicked.connect(lambda _, name=task_name: self.add_task_callback(name))
            layout.addWidget(btn)

        layout.addStretch()