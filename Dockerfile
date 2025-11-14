# Dockerfile for Aurora QA demo
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

# docker build . -t aurora-qa && docker run -p 8000:8000 aurora-qa
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]