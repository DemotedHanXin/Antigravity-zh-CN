"""Collect actual installed license texts before freezing; fail on omissions."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys


def collect(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("PySide6-Essentials", "shiboken6", "PyInstaller"):
        package = distribution(name)
        found = 0
        for item in package.files or []:
            if any(part.lower().startswith(("license", "copying")) for part in item.parts):
                source = Path(package.locate_file(item))
                if source.is_file():
                    target = destination / name / Path(*item.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    found += 1
        if not found:
            raise RuntimeError(f"No bundled license texts found for {name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError(f"Python license is missing: {python_license}")
    shutil.copyfile(python_license, destination / "CPython-LICENSE.txt")
    additional = Path(__file__).resolve().parent / "licenses"
    for item in additional.glob("*.txt"):
        shutil.copyfile(item, destination / item.name)
    for name in ("LGPL-3.0-only.txt", "GPL-3.0-only.txt"):
        if not (destination / name).is_file():
            raise RuntimeError(f"Missing Qt open-source license: {name}")


if __name__ == "__main__":
    collect(Path(__file__).resolve().parents[1] / "build" / "licenses")
