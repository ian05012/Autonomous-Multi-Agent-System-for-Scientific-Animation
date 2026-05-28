FROM python:3.11-slim

# ffmpeg for video composition, libsndfile for audio, build-essential for chromadb native bits
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.web.txt .
RUN pip install --no-cache-dir -r requirements.web.txt

COPY . .

EXPOSE 5000
CMD ["python", "server.py"]
