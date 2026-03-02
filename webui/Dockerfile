FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV PORT=4842
EXPOSE 4842

CMD ["python", "-u", "app.py"]
