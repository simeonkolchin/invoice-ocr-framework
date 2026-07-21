FROM python:3.11-slim

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        build-essential poppler-utils tesseract-ocr libgl1-mesa-glx \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]
