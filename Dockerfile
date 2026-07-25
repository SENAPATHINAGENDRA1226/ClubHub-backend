FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables should be passed during run, but set defaults
ENV PORT=8000
ENV HOST=0.0.0.0

EXPOSE $PORT

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
