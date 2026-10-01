"""Check that a built layer zip fits Lambda's limits and that rasterio works.

Run inside the Lambda base image matching the layer's Python version and
architecture, so the bundled binaries are exercised for real:

    docker run --rm -v "$PWD:/work" --entrypoint python3 \
        public.ecr.aws/lambda/python:3.12 \
        /work/rasterio-layer/smoke_test.py /work/rasterio-layer/dist/layer-x86_64-py3.12.zip
"""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
MAX_UNZIPPED_BYTES = 250 * 1024 * 1024  # function + all layers
MAX_DIRECT_UPLOAD_BYTES = 50 * 1024 * 1024  # larger zips must go through S3

# Executed against the extracted layer only, as Lambda would load it from
# /opt/python. Writes and reads a raster, and reprojects a point, so GDAL's
# drivers and the bundled PROJ database are both exercised.
CHECK = """
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform

data = np.arange(64, dtype="uint16").reshape(8, 8)
profile = dict(driver="GTiff", width=8, height=8, count=1, dtype="uint16",
               crs="EPSG:32614", transform=from_origin(561885, 3787815, 30, 30),
               compress="deflate", tiled=True, blockxsize=16, blockysize=16)
with MemoryFile() as mem:
    with mem.open(**profile) as dst:
        dst.write(data, 1)
    with mem.open() as src:
        assert (src.read(1) == data).all(), "round-trip mismatch"
        assert src.crs.to_epsg() == 32614, src.crs

lon, lat = transform("EPSG:32614", "EPSG:4326", [561885], [3787815])
assert -99 < lon[0] < -98 and 34 < lat[0] < 35, (lon, lat)

print(f"rasterio {rasterio.__version__}, GDAL {rasterio.__gdal_version__}, numpy {np.__version__}")
"""


def main(zip_path):
    zip_path = Path(zip_path)
    failures = []

    with zipfile.ZipFile(zip_path) as zf:
        unzipped = sum(info.file_size for info in zf.infolist())
        names = zf.namelist()
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            # -I -S keep the interpreter's own site-packages off sys.path, so
            # only the layer's packages can satisfy the imports.
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", f"import sys; sys.path.insert(0, {tmp + '/python'!r})\n{CHECK}"],
                capture_output=True, text=True,
            )

    zipped = zip_path.stat().st_size
    print(f"Zipped:   {zipped / 1e6:.1f} MB")
    print(f"Unzipped: {unzipped / 1e6:.1f} MB")

    if not all(name.startswith("python/") for name in names):
        failures.append("every entry must live under python/ for Lambda to find it")
    if unzipped > MAX_UNZIPPED_BYTES:
        failures.append(f"unzipped size exceeds Lambda's {MAX_UNZIPPED_BYTES // 2**20} MiB limit")
    if zipped > MAX_DIRECT_UPLOAD_BYTES:
        print(f"Note: over the {MAX_DIRECT_UPLOAD_BYTES // 2**20} MiB direct-upload limit; publish via S3")

    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        failures.append(f"rasterio check failed:\n{result.stdout}{result.stderr}")

    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
