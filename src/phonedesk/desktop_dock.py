from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class DesktopDock(QWidget):
    def __init__(self, scrcpy_manager, logger=None):
        super().__init__()
        self.scrcpy = scrcpy_manager
        self.logger = logger or (lambda _text: None)
        self.setWindowTitle("PhoneDesk Controls")
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._add_button(layout, "↩ رجوع", "back")
        self._add_button(layout, "⌂ الرئيسية", "home")
        self._add_button(layout, "▣ الأخيرة", "recent")
        self._add_button(layout, "🔔", "notifications")
        self._add_button(layout, "− صوت", "volume_down")
        self._add_button(layout, "+ صوت", "volume_up")
        self._add_button(layout, "⛶", "fullscreen")

        self.setStyleSheet(
            "QWidget { background: rgba(22,22,22,230); border-radius: 12px; }"
            "QPushButton { color: white; background: #2b2b2b; border: 0; "
            "padding: 9px 12px; border-radius: 8px; font-size: 13px; }"
            "QPushButton:hover { background: #3b3b3b; }"
            "QPushButton:pressed { background: #111; }"
        )
        self.adjustSize()

    def _add_button(self, layout, text: str, action: str):
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False, a=action: self._send(a))
        layout.addWidget(button)

    def _send(self, action: str):
        result = self.scrcpy.send_desktop_shortcut(action)
        self.logger(result.output)

    def show_dock(self):
        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.x() + (rect.width() - self.width()) // 2
            y = rect.y() + rect.height() - self.height() - 12
            self.move(max(rect.x(), x), max(rect.y(), y))
        self.show()
        self.raise_()
