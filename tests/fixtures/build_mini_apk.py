"""Rebuild the unsigned test APK with real Android tools (static-check-spec §5)."""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile


def _version(path: Path) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", path.parent.name))


def _sdk() -> Path:
    candidates = [Path(os.environ[name]) for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT") if os.environ.get(name)]
    candidates.extend((Path.home() / "Library/Android/sdk", Path.home() / "Android/Sdk"))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk")
    for path in candidates:
        if (path / "build-tools").is_dir():
            return path
    raise RuntimeError("Android SDK not found")


def _run(args: list[str | Path]) -> None:
    subprocess.run([str(arg) for arg in args], check=True, encoding="utf-8", errors="replace")


def build() -> None:
    root = Path(__file__).resolve().parent
    source = root / "mini_apk"
    sdk = _sdk()
    aapt_name, d8_name = ("aapt2.exe", "d8.bat") if os.name == "nt" else ("aapt2", "d8")
    aapt = max(sdk.glob(f"build-tools/*/{aapt_name}"), key=_version)
    d8 = max(sdk.glob(f"build-tools/*/{d8_name}"), key=_version)
    android = max(sdk.glob("platforms/android-*/android.jar"), key=_version)
    javac = shutil.which("javac")
    if javac is None:
        raise RuntimeError("javac not found")
    with tempfile.TemporaryDirectory(dir=root) as directory:
        work = Path(directory)
        resources = work / "resources.zip"
        apk = work / "mini.apk"
        classes, dex = work / "classes", work / "dex"
        classes.mkdir()
        dex.mkdir()
        _run([aapt, "compile", "--dir", source / "res", "-o", resources])
        _run(
            [
                aapt,
                "link",
                "-o",
                apk,
                "--manifest",
                source / "AndroidManifest.xml",
                "-I",
                android,
                "-A",
                source / "assets",
                "--min-sdk-version",
                "21",
                "--target-sdk-version",
                "35",
                "--version-code",
                "7",
                "--version-name",
                "1.0-mini",
                resources,
            ]
        )
        _run([javac, "--release", "11", "-encoding", "UTF-8", "-d", classes, source / "java/MiniAds.java"])
        _run([d8, "--min-api", "21", "--output", dex, *classes.rglob("*.class")])
        with ZipFile(apk, "a") as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        shutil.copyfile(apk, root / "mini.apk")


if __name__ == "__main__":
    build()
