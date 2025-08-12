FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api /app
# Gunicorn+Uvicorn
EXPOSE 10000
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-b","0.0.0.0:10000","app:app","--timeout","120"]
