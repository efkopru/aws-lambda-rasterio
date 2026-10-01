# Builds an AWS Lambda layer containing rasterio (with its bundled GDAL) and numpy.
#
# Building on the official Lambda base image guarantees the wheels match the
# Lambda runtime's Python version, glibc and CPU architecture.
ARG PYTHON_VERSION=3.12
FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

COPY requirements.txt package_layer.py /tmp/

# Lambda layers must place Python packages under python/ in the zip, which
# Lambda mounts at /opt/python.
RUN pip install --no-cache-dir --only-binary=:all: \
        -r /tmp/requirements.txt -t /layer/python \
    && python3 /tmp/package_layer.py /layer /layer.zip

# Running the container copies the finished zip into the mounted /out directory.
ENTRYPOINT ["cp", "/layer.zip", "/out/layer.zip"]
