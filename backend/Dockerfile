FROM python:3.11-slim
WORKDIR /project
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /project/backend/requirements.txt
RUN pip install --default-timeout=180 --retries=10 --no-cache-dir -r /project/backend/requirements.txt
COPY backend /project/backend
COPY sample_documents /project/sample_documents
ENV PYTHONPATH=/project/backend
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
