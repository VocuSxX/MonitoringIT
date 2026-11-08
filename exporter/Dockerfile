FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

USER nobody
EXPOSE 9182
CMD ["python", "-m", "app.exporter"]