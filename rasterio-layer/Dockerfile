# Use the official AWS Lambda Python 3.9 base image
FROM public.ecr.aws/lambda/python:3.9

# COPY the requirements file into the /var/task/ directory.
# This is the working directory of the base Lambda image.
COPY requirements.txt .

# Create a directory for the layer's contents
# The structure /opt/python is required by Lambda for layers
RUN mkdir -p /opt/python

# Install the dependencies from requirements.txt into this directory
# Using --target ensures they are packaged for the layer
RUN pip install -r requirements.txt -t /opt/python

# The command for the container is not important as we only need the files
CMD ["/bin/sh"]