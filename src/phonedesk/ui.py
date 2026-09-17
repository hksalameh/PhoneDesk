from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .core import AndroidBridge, CommandResult, ScrcpyManager, find_tool


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            value = self.fn(*self.args)
            self.signals.result.emit(value)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneDesk")
        self.resize(900, 650)

        self.settings = QSettings("PhoneDesk", "PhoneDesk")
        self.bridge = AndroidBridge()
        self.scrcpy = ScrcpyManager()
        self.pool = QThreadPool.globalInstance()

        self.address = QLineEdit(self.settings.value("serial", "192.168.1.2:5555"))
        self.status = QLabel("● غير متصل")
        self.status.setStyleSheet("font-weight: 700;")

        self.connect_btn = QPushButton("اتصال")
        self.refresh_btn = QPushButton("فحص الحالة")
        self.mirror_btn = QPushButton("عرض الهاتف")
        self.desktop_btn = QPushButton("سطح مكتب")
        self.stop_btn = QPushButton("إيقاف الجلسات")

        self.screen_off = QCheckBox("إطفاء شاشة الهاتف أثناء العرض")
        self.screen_off.setChecked(self.settings.value("screen_off", False, type=bool))

        self.package_combo = QComboBox()
        self.package_combo.setEditable(True)
        self.package_combo.setInsertPolicy(QComboBox.NoInsert)
        self.package_combo.setPlaceholderText("مثال: com.android.chrome")
        self.load_apps_btn = QPushButton("جلب التطبيقات")
        self.launch_app_btn = QPushButton("تشغيل في نافذة")

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self._build_ui()
        self._bind()
        self._check_tools()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("PhoneDesk")
        title.setStyleSheet("font-size: 28px; font-weight: 800;")
        subtitle = QLabel("تحويل اتصال ADB + scrcpy إلى تجربة سطح مكتب للهاتف")
        subtitle.setStyleSheet("color: #777;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        connection = QGroupBox("الاتصال")
        grid = QGridLayout(connection)
        grid.addWidget(QLabel("عنوان الهاتف"), 0, 0)
        grid.addWidget(self.address, 0, 1, 1, 3)
        grid.addWidget(self.connect_btn, 1, 0)
        grid.addWidget(self.refresh_btn, 1, 1)
        grid.addWidget(self.status, 1, 2, 1, 2)
        layout.addWidget(connection)

        actions = QGroupBox("التشغيل")
        actions_layout = QHBoxLayout(actions)
        actions_layout.addWidget(self.mirror_btn)
        actions_layout.addWidget(self.desktop_btn)
        actions_layout.addWidget(self.stop_btn)
        layout.addWidget(actions)
        layout.addWidget(self.screen_off)

        apps = QGroupBox("تشغيل تطبيق Android في نافذة مستقلة")
        apps_layout = QGridLayout(apps)
        apps_layout.addWidget(self.package_combo, 0, 0, 1, 2)
        apps_layout.addWidget(self.load_apps_btn, 1, 0)
        apps_layout.addWidget(self.launch_app_btn, 1, 1)
        layout.addWidget(apps)

        layout.addWidget(QLabel("السجل"))
        layout.addWidget(self.log, 1)

        self.setCentralWidget(root)

    def _bind(self):
        self.connect_btn.clicked.connect(self.connect_device)
        self.refresh_btn.clicked.connect(self.refresh_state)
        self.mirror_btn.clicked.connect(self.mirror)
        self.desktop_btn.clicked.connect(self.desktop)
        self.stop_btn.clicked.connect(self.stop_sessions)
        self.load_apps_btn.clicked.connect(self.load_apps)
        self.launch_app_btn.clicked.connect(self.launch_app)
        self.address.editingFinished.connect(self._save_settings)
        self.screen_off.toggled.connect(self._save_settings)

    def _save_settings(self):
        self.settings.setValue("serial", self.address.text().strip())
        self.settings.setValue("screen_off", self.screen_off.isChecked())

    def _serial(self) -> str:
        return self.address.text().strip()

    def append_log(self, text: str):
        self.log.append(text)

    def _set_connected(self, connected: bool, detail: str = ""):
        if connected:
            self.status.setText("● متصل" + (f" — {detail}" if detail else ""))
            self.status.setStyleSheet("font-weight: 700; color: #228B22;")
        else:
            self.status.setText("● غير متصل" + (f" — {detail}" if detail else ""))
            self.status.setStyleSheet("font-weight: 700; color: #B22222;")

    def _run_async(self, fn, callback, *args):
        worker = Worker(fn, *args)
        worker.signals.result.connect(callback)
        worker.signals.error.connect(lambda e: self.append_log(f"خطأ: {e}"))
        self.pool.start(worker)

    def _check_tools(self):
        adb = find_tool("adb")
        scrcpy = find_tool("scrcpy")
        self.append_log(f"ADB: {adb or 'غير موجود'}")
        self.append_log(f"scrcpy: {scrcpy or 'غير موجود'}")
        available = bool(adb and scrcpy)
        for button in (self.connect_btn, self.refresh_btn, self.mirror_btn, self.desktop_btn,
                       self.load_apps_btn, self.launch_app_btn):
            button.setEnabled(available)
        if available:
            self.refresh_state()
        else:
            self._set_connected(False, "ثبّت ADB وscrcpy أولًا")

    def connect_device(self):
        serial = self._serial()
        if not serial:
            self.append_log("أدخل عنوان الهاتف أولًا.")
            return
        self._save_settings()
        self.append_log(f"محاولة الاتصال بـ {serial} ...")
        self._run_async(self.bridge.connect, self._after_connect, serial)

    def _after_connect(self, result: CommandResult):
        self.append_log(result.output or "انتهى أمر الاتصال.")
        self._set_connected(result.ok)
        if result.ok:
            self._run_async(self.bridge.model, self._after_model, self._serial())

    def _after_model(self, result: CommandResult):
        if result.ok and result.output:
            self._set_connected(True, result.output.strip())

    def refresh_state(self):
        serial = self._serial()
        if not serial:
            return
        self._run_async(self.bridge.state, self._after_state, serial)

    def _after_state(self, result: CommandResult):
        connected = result.ok and result.output.strip() == "device"
        self._set_connected(connected)

    def mirror(self):
        result = self.scrcpy.mirror_phone(self._serial(), self.screen_off.isChecked())
        self.append_log(result.output)

    def desktop(self):
        result = self.scrcpy.desktop(self._serial())
        self.append_log(result.output)
        if result.ok:
            self.append_log("إذا ظهر العرض فارغًا، شغّل تطبيقًا من القسم التالي.")

    def load_apps(self):
        self.append_log("جلب تطبيقات المستخدم ...")
        self._run_async(self.bridge.list_user_packages, self._after_apps, self._serial())

    def _after_apps(self, result: CommandResult):
        if not result.ok:
            self.append_log(result.output or "تعذر جلب التطبيقات.")
            return
        packages = [x for x in result.output.splitlines() if x.strip()]
        self.package_combo.clear()
        self.package_combo.addItems(packages)
        self.append_log(f"تم العثور على {len(packages)} حزمة مستخدم.")

    def launch_app(self):
        package = self.package_combo.currentText().strip()
        result = self.scrcpy.launch_app(self._serial(), package)
        self.append_log(result.output)

    def stop_sessions(self):
        count = self.scrcpy.stop_all()
        self.append_log(f"تم إيقاف {count} جلسة.")

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)
