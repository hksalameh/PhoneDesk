from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import tempfile
from typing import IO, Iterable


# --new-display with --flex-display / --keep-active needs scrcpy 4.0+.
MIN_VIRTUAL_DISPLAY_VERSION = (4, 0)


@dataclass(slots=True)
class CommandResult:
    ok: bool
    output: str
    returncode: int = 0


@dataclass(slots=True)
class ScrcpySession:
    label: str
    process: subprocess.Popen
    log_path: str
    log_file: IO[bytes]


@dataclass(slots=True)
class SessionEnd:
    label: str
    returncode: int
    detail: str


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


def parse_scrcpy_version(text: str) -> tuple[int, int] | None:
    match = re.search(r"scrcpy\s+v?(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def error_summary(text: str, max_lines: int = 3) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    errors = [line for line in lines if "ERROR" in line]
    return "\n".join((errors or lines)[-max_lines:])


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
        # --brief prints one "package/activity" line per result; without it
        # Android prints a full ResolveInfo dump that has no such lines.
        result = run_command(
            [self.adb, "-s", serial, "shell", "cmd", "package", "query-activities", "--brief",
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
        self.sessions: list[ScrcpySession] = []
        self.desktop_process: subprocess.Popen | None = None

    @property
    def processes(self) -> list[subprocess.Popen]:
        return [session.process for session in self.sessions]

    def version(self) -> CommandResult:
        return run_command([self.scrcpy, "--version"], timeout=8)

    def _spawn(self, args: list[str], label: str, role: str | None = None) -> CommandResult:
        cmd = [self.scrcpy, *args]
        # scrcpy output goes to a file (not a pipe, which could fill up and
        # block scrcpy) so the real error can be shown if the session fails.
        log_file = tempfile.NamedTemporaryFile(prefix="phonedesk-", suffix=".log", delete=False)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                startupinfo=_startupinfo(),
                creationflags=_creationflags(),
            )
        except FileNotFoundError:
            self._discard_log(log_file)
            return CommandResult(False, "scrcpy غير موجود في PATH.", 127)
        except OSError as exc:
            self._discard_log(log_file)
            return CommandResult(False, str(exc), 1)

        self.sessions.append(ScrcpySession(label, proc, log_file.name, log_file))
        if role == "desktop":
            self.desktop_process = proc
        return CommandResult(True, f"جاري تشغيل {label} ...")

    def poll_finished(self) -> list[SessionEnd]:
        """Return sessions that ended since the last call, with scrcpy's error text."""
        ended: list[SessionEnd] = []
        running: list[ScrcpySession] = []
        for session in self.sessions:
            code = session.process.poll()
            if code is None:
                running.append(session)
                continue
            output = self._read_and_discard(session)
            detail = error_summary(output) if code != 0 else ""
            if session.process is self.desktop_process:
                self.desktop_process = None
            ended.append(SessionEnd(session.label, code, detail))
        self.sessions = running
        return ended

    def mirror_phone(self, serial: str, turn_screen_off: bool = False) -> CommandResult:
        # No --require-audio: if audio capture fails, scrcpy keeps the video.
        args = [
            "-s", serial,
            "--audio-source=output",
            "--window-title=PhoneDesk - Phone",
        ]
        if turn_screen_off:
            args.append("--turn-screen-off")
        return self._spawn(args, "عرض الهاتف")

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
        return self._spawn(args, "Samsung DeX", role="desktop")

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
        return self._spawn(args, f"التطبيق {package}")

    def stop_all(self) -> int:
        stopped = 0
        for session in self.sessions:
            if session.process.poll() is None:
                session.process.terminate()
                stopped += 1
        for session in self.sessions:
            try:
                session.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                session.process.kill()
                session.process.wait(timeout=3)
            self._read_and_discard(session)
        self.sessions.clear()
        self.desktop_process = None
        return stopped

    @staticmethod
    def _discard_log(log_file: IO[bytes]) -> None:
        log_file.close()
        try:
            os.remove(log_file.name)
        except OSError:
            pass

    @staticmethod
    def _read_and_discard(session: ScrcpySession) -> str:
        session.log_file.close()
        try:
            with open(session.log_path, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace")
        except OSError:
            text = ""
        try:
            os.remove(session.log_path)
        except OSError:
            pass
        return text
