# aws-lambda-rasterio

An AWS Lambda layer that provides [rasterio](https://rasterio.readthedocs.io/)
(with its bundled GDAL) and numpy, plus a helper script for compressing
GeoTIFFs.

## Build the layer

Requires Docker. The layer is built inside the official Lambda base image so
the binaries match the Lambda runtime.

```bash
cd rasterio-layer
./build.sh                # x86_64, Python 3.12 -> dist/layer-x86_64-py3.12.zip
./build.sh arm64 3.13     # Graviton, Python 3.13
```

The layer needs Python 3.12 or later (older Lambda runtimes use a glibc too
old for the rasterio wheels). Its Python version and architecture must match
the function that uses it.

After building, `build.sh` runs `smoke_test.py` in a clean Lambda image. The
test checks that rasterio can write and read a GeoTIFF and reproject
coordinates, and that the layer fits Lambda's 250 MB unzipped limit. CI runs
the same build for x86_64 and arm64 on every pull request; the zips are
available as workflow artifacts.

## Publish

```bash
aws lambda publish-layer-version \
  --layer-name rasterio \
  --zip-file fileb://dist/layer-x86_64-py3.12.zip \
  --compatible-runtimes python3.12 \
  --compatible-architectures x86_64
```

Direct uploads are limited to 50 MB. If the zip is larger, upload it to S3 and
use `--content s3Bucket=<bucket>,s3Key=<key>` instead.

`boto3` is not included because the Lambda runtime already provides it.

## Use it in a function

```python
import rasterio

def handler(event, context):
    # GDAL reads directly from S3 using the function's IAM role.
    with rasterio.open(f"s3://{event['bucket']}/{event['key']}") as src:
        return {"width": src.width, "height": src.height, "crs": str(src.crs)}
```

## Compress GeoTIFFs

`process_images.py` compresses every `.tif`/`.tiff` in a folder:

```bash
pip install -r rasterio-layer/requirements.txt
python rasterio-layer/process_images.py                     # images/ -> images_compressed/, lossless
python rasterio-layer/process_images.py in/ out/ --mode jpeg --quality 85
```

- `lossless` (default): DEFLATE + predictor. Pixel values are unchanged.
- `jpeg`: stretches each band to 8-bit and JPEG-compresses it. Much smaller,
  but the original values are lost, so use it only for previews.

## Sample data

The sample imagery is not stored in the repo. The script expects Landsat 9
Collection 2 Level-2 surface reflectance bands (`SR_B1`-`SR_B5`) of scene
`LC09_L2SP_027037_20250520_20250521_02_T1` in `rasterio-layer/images/`.

Download them from [USGS EarthExplorer](https://earthexplorer.usgs.gov/)
(free account), or from the public `usgs-landsat` requester-pays bucket:

```bash
aws s3 cp --request-payer requester \
  s3://usgs-landsat/collection02/level-2/standard/oli-tirs/2025/027/037/LC09_L2SP_027037_20250520_20250521_02_T1/ \
  rasterio-layer/images/ --recursive --exclude "*" --include "*_SR_B[1-5].TIF"
```
