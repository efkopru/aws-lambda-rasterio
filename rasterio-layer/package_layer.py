"""Trim an installed layer directory and zip it.

Run inside the build image after ``pip install -t <layer_dir>/python``. Uses only
the standard library so it works in the minimal Lambda base image, which does
not ship ``find`` or ``zip``.

Usage: python package_layer.py <layer_dir> <output_zip>
"""

import shutil
import sys
import zipfile
from pathlib import Path

# Not needed at runtime: bytecode caches (Lambda recompiles), test suites, and
# console scripts whose shebangs point at the build image's interpreter.
PRUNE_DIRS = {"__pycache__", "tests"}


def trim(python_dir):
    removed = 0
    for path in sorted(python_dir.rglob("*"), reverse=True):
        if path.is_dir() and path.name in PRUNE_DIRS:
            removed += sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            shutil.rmtree(path)
    bin_dir = python_dir / "bin"
    if bin_dir.is_dir():
        shutil.rmtree(bin_dir)
    return removed


def build_zip(layer_dir, output_zip):
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(layer_dir.rglob("*")):
            zf.write(path, path.relative_to(layer_dir))


def main(layer_dir, output_zip):
    layer_dir, output_zip = Path(layer_dir), Path(output_zip)
    python_dir = layer_dir / "python"
    if not python_dir.is_dir():
        sys.exit(f"{python_dir} not found; install packages there first")

    removed = trim(python_dir)
    build_zip(layer_dir, output_zip)

    unzipped = sum(f.stat().st_size for f in layer_dir.rglob("*") if f.is_file())
    print(f"Trimmed {removed / 1e6:.1f} MB")
    print(f"Unzipped: {unzipped / 1e6:.1f} MB, zipped: {output_zip.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
