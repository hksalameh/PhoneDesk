from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
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

    def list_launchable_packages(self, serial: str) -> CommandResult:
        result = run_command(
            [self.adb, "-s", serial, "shell", "cmd", "package", "query-activities",
             "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], timeout=45)
        if not result.ok:
            return result
        pattern = re.compile(r"^\s*([A-Za-z0-9_.$]+)/(?:[A-Za-z0-9_.$]+)\s*$")
        packages = {m.group(1) for line in result.output.splitlines() if (m := pattern.match(line))}
        return CommandResult(True, "\n".join(sorted(packages, key=str.lower)))



class ScrcpyManager:
    DESKTOP_TITLE = "PhoneDesk - Samsung DeX"

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
            "--new-display=1600x900/160",
            "--flex-display",
            "--keep-active",
            "--display-ime-policy=local",
            "--audio-source=output",
            "--mouse=sdk",
            "--keyboard=sdk",
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
            "--new-display=1280x800/160",
            "--flex-display",
            "--keep-active",
            "--display-ime-policy=local",
            f"--start-app={package}",
            f"--window-title=PhoneDesk - {package}",
        ]
        return self._spawn(args)

    def stop_all(self) -> int:
        stopped = 0
        for proc in self.processes:
            if proc.poll() is None:
                proc.terminate()
                stopped += 1
        self.processes.clear()
        self.desktop_process = None
        return stopped
