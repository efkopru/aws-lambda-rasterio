import numpy as np
import pytest
import rasterio

import process_images
from process_images import compress, find_tiffs, main, scale_to_byte, valid_mask


# --- find_tiffs -------------------------------------------------------------

def test_find_tiffs_matches_extensions_case_insensitively(tmp_path):
    for name in ["a.tif", "b.TIF", "c.tiff", "d.TIFF", "notes.txt", "e.tif.aux.xml"]:
        (tmp_path / name).touch()
    (tmp_path / "dir.tif").mkdir()

    assert [p.name for p in find_tiffs(tmp_path)] == ["a.tif", "b.TIF", "c.tiff", "d.TIFF"]


# --- valid_mask / scale_to_byte ---------------------------------------------

def test_valid_mask_excludes_nodata_value():
    band = np.array([[0, 5], [7, 0]], dtype="uint16")
    assert valid_mask(band, 0).tolist() == [[False, True], [True, False]]


def test_valid_mask_without_nodata_keeps_everything():
    band = np.array([[0, 5]], dtype="uint16")
    assert valid_mask(band, None).all()


def test_valid_mask_excludes_nan_and_inf_in_floats():
    band = np.array([[np.nan, 1.0, np.inf, -np.inf, 2.0]], dtype="float32")
    assert valid_mask(band, float("nan")).tolist() == [[False, True, False, False, True]]


def test_scale_to_byte_stretches_valid_range_to_full_byte_range():
    band = np.array([[100, 200, 300, 0]], dtype="uint16")
    valid = valid_mask(band, 0)

    scaled = scale_to_byte(band, valid)

    assert scaled.dtype == np.uint8
    assert scaled.tolist() == [[0, 128, 255, 0]]


def test_scale_to_byte_constant_band_maps_to_max():
    band = np.full((2, 2), 42, dtype="uint16")
    assert (scale_to_byte(band, np.ones_like(band, dtype=bool)) == 255).all()


def test_scale_to_byte_all_invalid_returns_zeros():
    band = np.full((2, 2), 42, dtype="uint16")
    assert (scale_to_byte(band, np.zeros_like(band, dtype=bool)) == 0).all()


# --- compress: lossless -----------------------------------------------------

@pytest.mark.parametrize("dtype", ["uint8", "uint16", "int16", "float32"])
def test_lossless_round_trip_is_exact(tmp_path, write_tiff, rng, dtype):
    data = (rng.random((2, 40, 60)) * 1000).astype(dtype)
    src = write_tiff(tmp_path / "src.tif", data, nodata=0)

    compress(src, tmp_path / "out.tif", "lossless", 85)

    with rasterio.open(src) as a, rasterio.open(tmp_path / "out.tif") as b:
        assert np.array_equal(a.read(), b.read())
        assert b.nodata == a.nodata
        assert b.crs == a.crs and b.transform == a.transform
        assert b.compression.value == "DEFLATE"
        assert b.profile["tiled"]


def test_lossless_preserves_nan(tmp_path, write_tiff, rng):
    data = rng.random((1, 20, 20)).astype("float32")
    data[0, :5] = np.nan
    src = write_tiff(tmp_path / "src.tif", data, nodata=float("nan"))

    compress(src, tmp_path / "out.tif", "lossless", 85)

    with rasterio.open(tmp_path / "out.tif") as out:
        assert np.array_equal(out.read(), data, equal_nan=True)


def test_lossless_accepts_jpeg_compressed_source(tmp_path, write_tiff, rng):
    data = rng.integers(0, 255, (3, 32, 32), dtype="uint8")
    src = write_tiff(tmp_path / "src.tif", data, compress="jpeg", photometric="ycbcr", interleave="pixel")

    compress(src, tmp_path / "out.tif", "lossless", 85)

    with rasterio.open(src) as a, rasterio.open(tmp_path / "out.tif") as b:
        assert np.array_equal(a.read(), b.read())


# --- compress: jpeg ---------------------------------------------------------

def test_jpeg_stores_nodata_as_mask_not_pixel_value(tmp_path, write_tiff, rng):
    data = rng.integers(1, 5000, (1, 64, 64), dtype="uint16")
    data[:, :, :16] = 0  # nodata strip
    src = write_tiff(tmp_path / "src.tif", data, nodata=0)

    compress(src, tmp_path / "out.tif", "jpeg", 85)

    with rasterio.open(tmp_path / "out.tif") as out:
        assert out.dtypes[0] == "uint8"
        assert out.nodata is None
        assert out.compression.value == "JPEG"
        mask = out.dataset_mask()
        # The mask is lossless, so it matches the source exactly even where
        # JPEG blurs pixel values across the boundary.
        assert np.array_equal(mask > 0, data[0] != 0)
    assert not (tmp_path / "out.tif.msk").exists(), "mask should be internal"


def test_jpeg_treats_nan_as_nodata(tmp_path, write_tiff, rng):
    data = (rng.random((1, 32, 32)) * 100).astype("float32")
    data[0, :8] = np.nan
    src = write_tiff(tmp_path / "src.tif", data, nodata=float("nan"))

    compress(src, tmp_path / "out.tif", "jpeg", 85)

    with rasterio.open(tmp_path / "out.tif") as out:
        mask = out.dataset_mask()
        assert (mask[:8] == 0).all() and (mask[8:] > 0).all()
        # NaN must not poison the stretch: valid pixels span the byte range.
        valid = out.read(1)[mask > 0]
        assert valid.min() <= 5 and valid.max() >= 250


def test_jpeg_three_band_uses_ycbcr(tmp_path, write_tiff, rng):
    data = rng.integers(0, 4000, (3, 32, 32), dtype="uint16")
    src = write_tiff(tmp_path / "src.tif", data)

    compress(src, tmp_path / "out.tif", "jpeg", 85)

    with rasterio.open(tmp_path / "out.tif") as out:
        assert out.count == 3
        assert out.profile["photometric"].lower() == "ycbcr"


# --- main (CLI) -------------------------------------------------------------

@pytest.fixture
def input_dir(tmp_path, write_tiff, rng):
    folder = tmp_path / "in"
    folder.mkdir()
    for name in ["a.tif", "b.TIF"]:
        write_tiff(folder / name, rng.integers(1, 1000, (1, 16, 16), dtype="uint16"))
    return folder


def test_main_compresses_every_file(tmp_path, input_dir):
    out = tmp_path / "out"

    assert main([str(input_dir), str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["a.tif", "b.TIF"]


def test_main_skips_existing_outputs_unless_overwrite(tmp_path, input_dir, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.tif").write_bytes(b"old")

    assert main([str(input_dir), str(out)]) == 0
    assert (out / "a.tif").read_bytes() == b"old"
    assert "skip  a.tif" in capsys.readouterr().out

    assert main([str(input_dir), str(out), "--overwrite"]) == 0
    with rasterio.open(out / "a.tif") as ds:
        assert ds.count == 1


def test_main_rejects_output_dir_equal_to_input_dir(input_dir):
    with pytest.raises(SystemExit) as exc:
        main([str(input_dir), str(input_dir), "--overwrite"])
    assert exc.value.code == 2


def test_main_rejects_missing_input_dir(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "nope"), str(tmp_path / "out")])
    assert exc.value.code == 2


@pytest.mark.parametrize("quality", ["0", "101"])
def test_main_rejects_out_of_range_quality(input_dir, tmp_path, quality):
    with pytest.raises(SystemExit) as exc:
        main([str(input_dir), str(tmp_path / "out"), "--mode", "jpeg", "--quality", quality])
    assert exc.value.code == 2


def test_main_returns_1_when_no_tiffs(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([str(empty), str(tmp_path / "out")]) == 1


def test_main_failure_leaves_no_output_or_partial_file(tmp_path, input_dir, capsys):
    (input_dir / "broken.tif").write_bytes(b"not a tiff")
    out = tmp_path / "out"

    assert main([str(input_dir), str(out)]) == 1

    assert sorted(p.name for p in out.iterdir()) == ["a.tif", "b.TIF"]
    assert "FAIL  broken.tif" in capsys.readouterr().out


def test_main_interrupted_write_leaves_no_partial_file(tmp_path, input_dir, monkeypatch):
    out = tmp_path / "out"

    def explode(src_path, dst_path, mode, quality):
        dst_path.write_bytes(b"half written")
        raise KeyboardInterrupt

    monkeypatch.setattr(process_images, "compress", explode)
    with pytest.raises(KeyboardInterrupt):
        main([str(input_dir), str(out)])

    assert list(out.iterdir()) == []
