import zipfile

from package_layer import main


def test_trims_unneeded_files_and_zips_layer(tmp_path, capsys):
    layer = tmp_path / "layer"
    pkg = layer / "python" / "pkg"
    for path, content in {
        pkg / "__init__.py": "x = 1",
        pkg / "__pycache__" / "mod.cpython-312.pyc": "cache",
        pkg / "tests" / "test_mod.py": "test",
        pkg / "testing" / "helpers.py": "kept: only 'tests' dirs are pruned",
        layer / "python" / "bin" / "rio": "#!/usr/bin/python",
        layer / "lib" / "libexpat.so.1": "elf",
    }.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    main(layer, tmp_path / "layer.zip")

    names = set(zipfile.ZipFile(tmp_path / "layer.zip").namelist())
    files = {n for n in names if not n.endswith("/")}
    assert files == {
        "python/pkg/__init__.py",
        "python/pkg/testing/helpers.py",
        "lib/libexpat.so.1",
    }
    assert all(n.startswith(("python/", "lib/")) for n in names)
    assert "Unzipped:" in capsys.readouterr().out


def test_requires_python_dir(tmp_path):
    import pytest

    with pytest.raises(SystemExit, match="not found"):
        main(tmp_path, tmp_path / "layer.zip")
