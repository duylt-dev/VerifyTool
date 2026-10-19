"""The only subprocess boundary: adb discovery, commands and logcat (runtime spec §2)."""

import os
import re
import shutil
import subprocess
from pathlib import Path

from apkverify.errors import AdbError
from apkverify.model import DeviceInfo

_INCOMPATIBLE = (
    "Không cài được APK: bản đã cài ký bằng key khác. Gỡ app trên máy rồi chạy lại "
    "(tool không tự gỡ vì sẽ mất dữ liệu app)."
)


def parse_devices(text: str) -> list[tuple[str, str]]:
    devices = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and not line.startswith(("List of devices", "*")):
            devices.append((fields[0], fields[1]))
    return devices


def install_failure(text: str) -> str | None:
    if any(line.strip() == "Success" for line in text.splitlines()):
        return None
    match = re.search(r"Failure \[([^\]]+)\]", text)
    return match.group(1) if match else None


def find_adb() -> str:
    if exe := shutil.which("adb"):
        return exe
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if directory := os.environ.get(variable):
            candidate = Path(directory) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise AdbError("Không thấy adb trên PATH, $ANDROID_HOME/platform-tools hoặc $ANDROID_SDK_ROOT/platform-tools.")


def _run(command: list[str], timeout: float = 30) -> str:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        output = error.output or b""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        raise AdbError(
            f"Lệnh {' '.join(command)} quá {timeout:g} giây: " + "\n".join(output.splitlines()[-10:])
        ) from error
    except OSError as error:
        raise AdbError(f"Không chạy được lệnh {' '.join(command)}: {error}.") from error
    if "install" in command and "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in result.stdout:
        raise AdbError(_INCOMPATIBLE)
    if result.returncode:
        raise AdbError(
            f"Lệnh {' '.join(command)} lỗi ({result.returncode}): " + "\n".join(result.stdout.splitlines()[-10:])
        )
    return result.stdout


class Adb:
    def __init__(self, exe: str, serial: str) -> None:
        self.exe = exe
        self.serial = serial

    def _command(self, *args: str, timeout: float = 30) -> str:
        return _run([self.exe, "-s", self.serial, *args], timeout)

    def getprop(self, name: str) -> str:
        return self._command("shell", "getprop", name).strip()

    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            self.serial,
            self.getprop("ro.product.model"),
            self.getprop("ro.build.version.release"),
            self.serial.startswith("emulator-") or self.getprop("ro.kernel.qemu") == "1",
        )

    def install(self, apk: Path) -> None:
        output = self._command("install", "-r", str(apk), timeout=300)
        if failure := install_failure(output):
            raise AdbError(f"Không cài được APK: {self.exe} -s {self.serial} install -r {apk}: {failure}.")

    def clear_data(self, package: str) -> None:
        self._command("shell", "pm", "clear", package)

    def force_stop(self, package: str) -> None:
        """Kill the app process (no data loss) so the next launch is a cold start that runs splash ads."""
        self._command("shell", "am", "force-stop", package)

    def clear_log(self) -> None:
        self._command("logcat", "-c")

    def launch(self, package: str) -> None:
        self._command("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")

    def start_logcat(self) -> subprocess.Popen[str]:
        command = [self.exe, "-s", self.serial, "logcat", "-v", "epoch", "-s", "TESTERADSEVENT:D", "CHECKINITADS:D"]
        # Own process group: Ctrl+C in the terminal must reach only us. If logcat got the SIGINT too it could die
        # first, the session would see "logcat ended by itself" and skip the report (runtime-check-spec §1 step 8).
        if os.name == "nt":
            group: dict = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            group = {"start_new_session": True}
        try:
            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **group,
            )
        except OSError as error:
            raise AdbError(f"Không chạy được lệnh {' '.join(command)}: {error}.") from error

    def stop(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def check_logcat(self, proc: subprocess.Popen[str], log_path: Path) -> None:
        try:
            code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise AdbError(f"Lệnh {self.exe} -s {self.serial} logcat chưa kết thúc. Xem log: {log_path}.") from error
        if code:
            raise AdbError(f"Lệnh {self.exe} -s {self.serial} logcat lỗi ({code}). Xem log: {log_path}.")


def pick_device(exe: str, serial: str | None) -> Adb:
    devices = parse_devices(_run([exe, "devices"]))
    if serial is not None:
        state = dict(devices).get(serial, "không tìm thấy")
        if state != "device":
            raise AdbError(f"Thiết bị {serial} không sẵn sàng ({state}).")
        return Adb(exe, serial)
    usable = [name for name, state in devices if state == "device"]
    if not usable:
        raise AdbError("Không có thiết bị nào ở trạng thái 'device'. Mở emulator hoặc cắm máy và bật USB debugging.")
    if len(usable) > 1:
        raise AdbError(f"Có {len(usable)} thiết bị: {', '.join(usable)}. Chỉ rõ bằng --serial.")
    return Adb(exe, usable[0])
