from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import shutil
import subprocess
import time
from typing import Iterable


@dataclass(slots=True)
class CommandResult:
    ok: bool
    output: str
    returncode: int = 0


def _startupinfo():
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def find_tool(name: str) -> str | None:
    return shutil.which(name)


def run_command(args: Iterable[str], timeout: int = 15) -> CommandResult:
    try:
        cp = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=_startupinfo(),
            creationflags=_creationflags(),
        )
    except FileNotFoundError:
        return CommandResult(False, f"الأداة غير موجودة: {list(args)[0]}", 127)
    except subprocess.TimeoutExpired:
        return CommandResult(False, "انتهت مهلة تنفيذ الأمر.", 124)

    output = "\n".join(x for x in (cp.stdout.strip(), cp.stderr.strip()) if x).strip()
    return CommandResult(cp.returncode == 0, output, cp.returncode)


class AndroidBridge:
    def __init__(self, adb_path: str | None = None):
        self.adb = adb_path or find_tool("adb") or "adb"

    def version(self) -> CommandResult:
        return run_command([self.adb, "version"])

    def connect(self, serial: str) -> CommandResult:
        result = run_command([self.adb, "connect", serial], timeout=20)
        if not result.ok:
            return result
        state = self.state(serial)
        if state.ok and state.output.strip() == "device":
            return CommandResult(True, f"متصل: {serial}")
        return CommandResult(False, state.output or f"تعذر تأكيد الاتصال مع {serial}")

    def state(self, serial: str) -> CommandResult:
        return run_command([self.adb, "-s", serial, "get-state"], timeout=8)

    def model(self, serial: str) -> CommandResult:
        return run_command([self.adb, "-s", serial, "shell", "getprop", "ro.product.model"], timeout=8)

    def android_version(self, serial: str) -> CommandResult:
        return run_command([self.adb, "-s", serial, "shell", "getprop", "ro.build.version.release"], timeout=8)

    def list_user_packages(self, serial: str) -> CommandResult:
        result = run_command(
            [self.adb, "-s", serial, "shell", "pm", "list", "packages", "-3"],
            timeout=30,
        )
        if not result.ok:
            return result
        packages = []
        for line in result.output.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.removeprefix("package:"))
        packages.sort(key=str.lower)
        return CommandResult(True, "\n".join(packages))


class ScrcpyManager:
    DESKTOP_TITLE = "PhoneDesk - Desktop"

    def __init__(self, scrcpy_path: str | None = None):
        self.scrcpy = scrcpy_path or find_tool("scrcpy") or "scrcpy"
        self.processes: list[subprocess.Popen] = []
        self.desktop_process: subprocess.Popen | None = None

    def version(self) -> CommandResult:
        return run_command([self.scrcpy, "--version"], timeout=8)

    def _spawn(self, args: list[str], role: str | None = None) -> CommandResult:
        cmd = [self.scrcpy, *args]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=_startupinfo(),
                creationflags=_creationflags(),
            )
        except FileNotFoundError:
            return CommandResult(False, "scrcpy غير موجود في PATH.", 127)
        except OSError as exc:
            return CommandResult(False, str(exc), 1)

        self.processes = [p for p in self.processes if p.poll() is None]
        self.processes.append(proc)
        if role == "desktop":
            self.desktop_process = proc
        return CommandResult(True, "تم تشغيل scrcpy.")

    def mirror_phone(self, serial: str, turn_screen_off: bool = False) -> CommandResult:
        args = [
            "-s", serial,
            "--audio-source=output",
            "--require-audio",
            "--window-title=PhoneDesk - Phone",
        ]
        if turn_screen_off:
            args.append("--turn-screen-off")
        return self._spawn(args)

    def desktop(self, serial: str) -> CommandResult:
        args = [
            "-s", serial,
            "--new-display=1920x1080",
            "--flex-display",
            "--keep-active",
            "--display-ime-policy=local",
            "--audio-source=output",
            "--mouse=sdk",
            "--keyboard=sdk",
            "--mouse-bind=bhsn:++++",
            "--max-fps=60",
            "--disable-screensaver",
            "--fullscreen",
            f"--window-title={self.DESKTOP_TITLE}",
        ]
        return self._spawn(args, role="desktop")

    def launch_app(self, serial: str, package: str) -> CommandResult:
        package = package.strip()
        if not package or " " in package:
            return CommandResult(False, "اسم الحزمة غير صالح.")
        args = [
            "-s", serial,
            "--new-display=1280x900",
            "--flex-display",
            "--keep-active",
            "--display-ime-policy=local",
            f"--start-app={package}",
            f"--window-title=PhoneDesk - {package}",
        ]
        return self._spawn(args)

    def _desktop_hwnd_windows(self) -> int | None:
        proc = self.desktop_process
        if not proc or proc.poll() is not None:
            return None

        user32 = ctypes.windll.user32
        found: list[int] = []
        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
                if user32.GetWindowTextLengthW(hwnd) > 0:
                    found.append(int(hwnd))
                    return False
            return True

        callback_ref = enum_proc_type(callback)
        user32.EnumWindows(callback_ref, 0)
        return found[0] if found else None

    def send_desktop_shortcut(self, action: str) -> CommandResult:
        if os.name != "nt":
            return CommandResult(False, "أزرار سطح المكتب العائمة مدعومة على Windows حاليًا.")

        hwnd = self._desktop_hwnd_windows()
        if not hwnd:
            return CommandResult(False, "نافذة PhoneDesk Desktop غير موجودة.")

        keymap = {
            "home": 0x48,
            "back": 0x42,
            "recent": 0x53,
            "notifications": 0x4E,
            "volume_up": 0x26,
            "volume_down": 0x28,
        }
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.06)

        key_up = 0x0002
        if action == "fullscreen":
            vk = 0x7A  # F11
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, key_up, 0)
            return CommandResult(True, "تم تبديل وضع ملء الشاشة.")

        vk = keymap.get(action)
        if vk is None:
            return CommandResult(False, f"أمر غير معروف: {action}")

        vk_lalt = 0xA4
        user32.keybd_event(vk_lalt, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, key_up, 0)
        user32.keybd_event(vk_lalt, 0, key_up, 0)
        return CommandResult(True, "تم إرسال أمر التحكم إلى سطح المكتب.")

    def stop_all(self) -> int:
        stopped = 0
        for proc in self.processes:
            if proc.poll() is None:
                proc.terminate()
                stopped += 1
        self.processes.clear()
        self.desktop_process = None
        return stopped
