import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

# The scripts live next to this folder rather than in an installable package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def write_tiff():
    """Write a small georeferenced GeoTIFF from a (bands, rows, cols) array."""

    def write(path, data, nodata=None, **creation_options):
        profile = dict(
            driver="GTiff", count=data.shape[0], height=data.shape[1], width=data.shape[2],
            dtype=data.dtype, nodata=nodata, crs="EPSG:32614",
            transform=from_origin(561885, 3787815, 30, 30), **creation_options,
        )
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data)
        return path

    return write


@pytest.fixture
def rng():
    return np.random.default_rng(0)
