"""Compress GeoTIFFs in a folder using rasterio.

Two modes are available:

* ``lossless`` (default): DEFLATE compression with a predictor. Pixel values are
  preserved exactly, so the output is safe for analysis (e.g. reflectance math).
* ``jpeg``: 8-bit JPEG compression. Each band is linearly stretched from its
  min/max to 0-255 first, since JPEG cannot store 16-bit data. Nodata is kept
  in a separate mask rather than as a pixel value, because lossy JPEG would
  bleed into it. Much smaller files, but the original values are lost - use
  for previews/visualisation only.

Usage:
    python process_images.py                       # images/ -> images_compressed/
    python process_images.py in_dir out_dir --mode jpeg --quality 85
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
TIFF_SUFFIXES = {".tif", ".tiff"}


def find_tiffs(folder):
    # Match suffixes case-insensitively instead of globbing "*.tif" and "*.TIF"
    # separately, which returns duplicates on case-insensitive filesystems.
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in TIFF_SUFFIXES)


def valid_mask(band, nodata):
    """True where a pixel holds data: not nodata and, for floats, finite."""
    valid = np.ones(band.shape, dtype=bool)
    if np.issubdtype(band.dtype, np.floating):
        valid &= np.isfinite(band)
    if nodata is not None and not np.isnan(nodata):
        valid &= band != nodata
    return valid


def scale_to_byte(band, valid):
    """Linearly stretch the valid pixels of a band to 0-255."""
    scaled = np.zeros(band.shape, dtype=np.uint8)
    if not valid.any():
        return scaled

    values = band[valid].astype(np.float32)
    lo, hi = values.min(), values.max()
    if hi > lo:
        values -= lo
        values *= 255 / (hi - lo)
        scaled[valid] = np.round(values).astype(np.uint8)
    else:
        scaled[valid] = 255
    return scaled


def compress(src_path, dst_path, mode, quality):
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(driver="GTiff", tiled=True, blockxsize=512, blockysize=512)
        # A JPEG-compressed source carries photometric=ycbcr, which is only
        # valid with JPEG output; let each mode decide.
        profile.pop("photometric", None)

        if mode == "lossless":
            # Predictor 2 (horizontal differencing) suits integers, 3 suits floats.
            predictor = 3 if np.issubdtype(np.dtype(src.dtypes[0]), np.floating) else 2
            profile.update(compress="deflate", predictor=predictor, zlevel=9)
            with rasterio.open(dst_path, "w", **profile) as dst:
                for _, window in src.block_windows(1):
                    dst.write(src.read(window=window), window=window)
            return

        profile.update(dtype="uint8", compress="jpeg", jpeg_quality=quality, nodata=None)
        if src.count == 3:
            profile.update(photometric="ycbcr", interleave="pixel")
        # Store the mask inside the TIFF instead of a .msk sidecar file.
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(dst_path, "w", **profile) as dst:
                any_valid = np.zeros((src.height, src.width), dtype=bool)
                for band_index in range(1, src.count + 1):
                    band = src.read(band_index)
                    valid = valid_mask(band, src.nodata)
                    any_valid |= valid
                    dst.write(scale_to_byte(band, valid), band_index)
                dst.write_mask(any_valid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_dir", nargs="?", type=Path, default=SCRIPT_DIR / "images")
    parser.add_argument("output_dir", nargs="?", type=Path, default=SCRIPT_DIR / "images_compressed")
    parser.add_argument("--mode", choices=["lossless", "jpeg"], default="lossless")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality, 1-100 (jpeg mode only)")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files")
    args = parser.parse_args(argv)

    if not args.input_dir.is_dir():
        parser.error(f"input directory not found: {args.input_dir}")
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    if args.output_dir.resolve() == args.input_dir.resolve():
        # Writing a file while reading it would corrupt the original.
        parser.error("output directory must differ from the input directory")

    tiffs = find_tiffs(args.input_dir)
    if not tiffs:
        print(f"No .tif/.tiff files found in {args.input_dir}")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Compressing {len(tiffs)} file(s) to {args.output_dir} ({args.mode})")

    failures = 0
    for src_path in tiffs:
        dst_path = args.output_dir / src_path.name
        if dst_path.exists() and not args.overwrite:
            print(f"  skip  {src_path.name} (exists; use --overwrite)")
            continue
        # Write to a temporary name so an interrupted run never leaves a
        # truncated file that later runs would skip as already done.
        tmp_path = dst_path.with_name(f".{dst_path.name}.partial")
        try:
            compress(src_path, tmp_path, args.mode, args.quality)
            tmp_path.replace(dst_path)
        except Exception as e:
            failures += 1
            print(f"  FAIL  {src_path.name}: {e}")
            continue
        finally:
            tmp_path.unlink(missing_ok=True)
        before, after = src_path.stat().st_size / 1e6, dst_path.stat().st_size / 1e6
        print(f"  ok    {src_path.name} ({before:.1f} MB -> {after:.1f} MB)")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
