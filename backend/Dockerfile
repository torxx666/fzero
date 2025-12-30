FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# Install system dependencies
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libasound2-dev \
    build-essential \
    espeak-ng \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    echo "torch==2.4.0" > constraints.txt && \
    echo "torchvision==0.19.0" >> constraints.txt && \
    echo "torchaudio==2.4.0" >> constraints.txt && \
    pip install -r requirements.txt -c constraints.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
