# Dockerfile for Face Attendance app
# Uses Debian-based slim Python image and installs system deps for dlib/OpenCV

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system packages required to build dlib/opencv
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       cmake \
       git \
       wget \
       unzip \
       libglib2.0-0 \
       libsm6 \
       libxext6 \
       libxrender-dev \
       libssl-dev \
       libbz2-dev \
       libreadline-dev \
       libsqlite3-dev \
       libopenblas-dev \
       liblapack-dev \
       python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy app files
COPY . /app

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install Python requirements (including gunicorn)
RUN pip install -r requirements.txt

# Expose port used by Render/containers
EXPOSE 5000

# Use gunicorn to serve the Flask app; render will provide $PORT env var
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "3"]
