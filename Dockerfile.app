FROM python:3.13-slim

# ffmpeg, audio libs, build tools, and CJK fonts for subtitle rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.web.txt .
RUN pip install --no-cache-dir -r requirements.web.txt

COPY . .

EXPOSE 5000
CMD ["python", "server.py"]
