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

The Python version and architecture of the layer must match the function that
uses it.

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
