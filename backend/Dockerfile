FROM python:3.11-slim

WORKDIR /app

# Install only minimal required system dependencies
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends libpq5 libpq-dev gcc python3-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Pre-install numpy and torch separately with pre-built wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
