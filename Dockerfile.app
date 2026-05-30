FROM python:3.13-slim

# ffmpeg, audio libs, build tools
# fonts-noto-cjk     → zh-TW, zh-CN, ja, ko
# fonts-noto         → en, fr, de, and most Latin/Greek/Cyrillic scripts
# fonts-noto-extra   → ar and other complex scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    fonts-noto-cjk \
    fonts-noto \
    fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.web.txt .
RUN pip install --no-cache-dir -r requirements.web.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
