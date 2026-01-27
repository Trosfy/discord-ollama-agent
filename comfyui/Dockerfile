# ComfyUI Dockerfile for ARM64 (DGX Spark / Blackwell)
# Supports NVFP4 quantization for FLUX.2-dev
# Uses CUDA 13.0 for native Blackwell GPU acceleration
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_PATH=/opt/ComfyUI

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create venv
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip wheel setuptools

# Install PyTorch for ARM64 with CUDA 13.0 support (Blackwell)
# Use cu130 index for native NVFP4 tensor core acceleration
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_PATH}

# Install ComfyUI requirements
WORKDIR ${COMFYUI_PATH}
RUN pip install -r requirements.txt

# Install additional dependencies for FLUX
RUN pip install \
    transformers \
    accelerate \
    sentencepiece \
    safetensors \
    einops \
    aiohttp

# Create directories
RUN mkdir -p ${COMFYUI_PATH}/models/checkpoints \
    ${COMFYUI_PATH}/models/clip \
    ${COMFYUI_PATH}/models/vae \
    ${COMFYUI_PATH}/output \
    ${COMFYUI_PATH}/input

# Expose port
EXPOSE 8188

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/ || exit 1

# Start ComfyUI
CMD ["python3", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
