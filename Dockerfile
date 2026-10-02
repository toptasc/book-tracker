FROM python:3.11-slim

WORKDIR /app

# Gerekli bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .

# SQLite klasörü için izinler ve varsayılan port
EXPOSE 5000

CMD ["python", "app.py"]