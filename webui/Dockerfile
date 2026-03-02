FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV PORT=4842
EXPOSE 4842

# Production: gunicorn (no Flask dev-server warning)
CMD ["gunicorn", "--bind", "0.0.0.0:4842", "--workers", "1", "--threads", "2", "app:app"]
