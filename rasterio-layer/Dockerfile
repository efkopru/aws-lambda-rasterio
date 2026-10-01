# Builds an AWS Lambda layer containing rasterio (with its bundled GDAL) and numpy.
#
# Building on the official Lambda base image guarantees the wheels match the
# Lambda runtime's Python version, glibc and CPU architecture.
ARG PYTHON_VERSION=3.12
FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

COPY requirements.txt /tmp/requirements.txt

# Lambda layers must place Python packages under python/ in the zip, which
# Lambda mounts at /opt/python.
RUN pip install --no-cache-dir --only-binary=:all: \
        -r /tmp/requirements.txt -t /layer/python \
    # Trim files that are not needed at runtime to keep the layer small.
    && find /layer/python -type d \( -name "__pycache__" -o -name "tests" -o -name "test" \) -prune -exec rm -rf {} + \
    && rm -rf /layer/python/bin \
    && cd /layer \
    && python -m zipfile -c /layer.zip python

# Running the container copies the finished zip into the mounted /out directory.
ENTRYPOINT ["cp", "/layer.zip", "/out/layer.zip"]
